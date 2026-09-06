package engine

import (
	"context"
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

type cycleInput struct {
	fences []fence.Fence
	routes []route.Route
	// prevAll es devices.json tal cual se leyó (con su orden); prev lo
	// indexa por id para buscar el estado previo de cada dispositivo.
	prevAll []device.Device
	prev    map[string]device.Device
}

func (e *Engine) loadInput() (cycleInput, error) {
	fs, err := e.org.Fences()
	if err != nil {
		return cycleInput{}, err
	}
	rs, err := e.org.Routes()
	if err != nil {
		return cycleInput{}, err
	}
	ds, err := e.org.Devices()
	if err != nil {
		return cycleInput{}, err
	}
	return cycleInput{fences: fs, routes: rs, prevAll: ds, prev: device.Index(ds)}, nil
}

func fetchSafe(ctx context.Context, ad uem.Adapter) (ds []device.Device, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("pánico en el conector: %v", r)
		}
	}()
	return ad.FetchDevices(ctx)
}

func (e *Engine) fetchAll(ctx context.Context, st *CycleStats) []device.Device {
	var all []device.Device
	for _, name := range e.order {
		start := time.Now()
		ds, err := fetchSafe(ctx, e.adapters[name])
		h := ProviderHealth{LatencyMS: time.Since(start).Milliseconds(), Devices: len(ds)}
		if err != nil {
			h.Error = err.Error()
			if prev, ok := e.providers[name]; ok {
				h.LastOK = prev.LastOK
			}
			e.opts.Logger.Warn("proveedor", "name", name, "error", err)
		} else {
			now := e.opts.Now().UTC()
			h.OK, h.LastOK = true, &now
			all = append(all, ds...)
		}
		st.Providers[name] = h
	}
	return all
}

// staleDevices devuelve los dispositivos del ciclo anterior cuyo conector
// falló en este: se conservan tal cual en devices.json, sin evaluarlos ni
// planificar acciones para ellos, para que una caída pasajera del proveedor
// no borre su estado ni provoque transiciones espurias (ni un segundo
// on_enter) cuando vuelva a responder.
func staleDevices(in cycleInput, providers map[string]ProviderHealth, fetched []device.Device) []device.Device {
	seen := make(map[string]bool, len(fetched))
	for _, d := range fetched {
		seen[d.ID] = true
	}
	var out []device.Device
	for _, d := range in.prevAll {
		if h, ok := providers[d.Provider]; ok && !h.OK && !seen[d.ID] {
			out = append(out, d)
		}
	}
	return out
}

// evaluateDevice evalúa un dispositivo con recover: un fallo deja el
// dispositivo en evaluation_error con riesgo nulo y el ciclo sigue.
func (e *Engine) evaluateDevice(in cycleInput, cur *device.Device, now time.Time) (tr *transition.Transition, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("%v", r)
			cur.EvaluationError = err.Error()
			cur.Risk.Score = nil
		}
	}()
	if e.evalHook != nil {
		e.evalHook(cur)
	}
	var prev *device.Device
	if p, ok := in.prev[cur.ID]; ok {
		prev = &p
	}
	tr = transition.Evaluate(prev, cur, in.fences, now)
	cur.RouteState, cur.RouteID, cur.RouteDeviationM = device.Unassigned, "", nil
	if r, ok := route.ForDevice(in.routes, cur.ID); ok && cur.Location.Point != nil {
		d := r.DistanceM(*cur.Location.Point)
		cur.RouteID, cur.RouteDeviationM = r.ID, &d
		cur.RouteState = device.OnRoute
		if d > r.CorridorM {
			cur.RouteState = device.OffRoute
		}
	}
	return tr, nil
}

// processDevice evalúa un dispositivo, registra su trail y transición, y
// ejecuta las acciones planificadas; devuelve los resultados para que
// runCycle los persista y compute las estadísticas de ejecución.
func (e *Engine) processDevice(ctx context.Context, in cycleInput, cur *device.Device, now time.Time, st *CycleStats) []action.Result {
	tr, evalErr := e.evaluateDevice(in, cur, now)
	if evalErr != nil {
		st.EvaluationErrors++
	}
	switch cur.FenceState {
	case device.Inside:
		st.Inside++
	case device.Outside:
		st.Outside++
	default:
		st.Unknown++
	}
	if cur.Location.Point != nil {
		if err := e.org.AppendTrail(cur.ID, *cur.Location.Point, now); err != nil {
			e.logPersistenceError(st, "trail", cur.ID, err)
		}
	}
	if tr != nil {
		st.Transitions++
		if err := e.org.AppendEvent(*tr); err != nil {
			e.logPersistenceError(st, "event", cur.ID, err)
		}
	}
	var results []action.Result
	planned := append(PlanTransition(*cur, tr, in.fences), e.planStanding(*cur, in.fences)...)
	for _, p := range planned {
		if e.alreadyFired(p) {
			continue
		}
		st.ActionsPlanned++
		results = append(results, e.execute(ctx, p))
	}
	return results
}

func (e *Engine) runCycle(ctx context.Context) (CycleStats, error) {
	start := time.Now()
	now := e.opts.Now().UTC()
	st := CycleStats{At: now, Mode: e.opts.Mode, Providers: map[string]ProviderHealth{}}
	in, err := e.loadInput()
	if err != nil {
		return st, err
	}
	devices := e.fetchAll(ctx, &st)
	var results []action.Result
	for i := range devices {
		results = append(results, e.processDevice(ctx, in, &devices[i], now, &st)...)
	}
	st.DevicesTotal = len(devices)
	// devices.json guarda lo evaluado en este ciclo más los dispositivos de
	// los conectores caídos, que se conservan tal cual (ver staleDevices).
	devices = append(devices, staleDevices(in, st.Providers, devices)...)
	// Un fallo al guardar devices.json no puede borrar el rastro de las
	// acciones ya ejecutadas contra el conector: se cuenta como error de
	// persistencia (M1-R11), la auditoría y las estadísticas se escriben
	// igualmente y el error se sigue devolviendo como error del ciclo.
	saveErr := e.org.SaveDevices(devices)
	if saveErr != nil {
		e.logPersistenceError(&st, "devices", "", saveErr)
	}
	st.ActionsExecuted = len(results)
	for _, r := range results {
		if err := e.org.AppendAction(r); err != nil {
			e.logPersistenceError(&st, "action", r.DeviceID, err)
		}
	}
	st.DurationMS = time.Since(start).Milliseconds()
	if err := e.org.AppendStats(st); err != nil {
		e.logPersistenceError(&st, "stats", "", err)
	}
	return st, saveErr
}

// logPersistenceError registra un fallo de persistencia y lo cuenta en las
// estadísticas del ciclo; el ciclo sigue (M1-R11).
func (e *Engine) logPersistenceError(st *CycleStats, op, deviceID string, err error) {
	st.PersistenceErrors++
	e.opts.Logger.Warn("persistencia", "op", op, "device", deviceID, "error", err)
}
