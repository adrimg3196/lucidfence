package engine

import (
	"context"
	"fmt"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

// Planned es una acción decidida pero aún no ejecutada. Es plana (acción y
// parámetros sueltos, no un fence.Action) para poder transportar acciones de
// geocerca, de ruta, de política y de playbook con la misma forma: T14 rellena
// RouteID y PolicyID, T16 PlaybookID.
type Planned struct {
	Device device.Device
	Action action.Action
	Params map[string]any

	FenceID    string
	RouteID    string
	PolicyID   string
	PlaybookID string
	Trigger    string
	Severity   string
}

// fenceOfKey extrae el id de geocerca de una clave de transición con
// gramática "<id>:<estado>" (p. ej. "demo-hq:inside", "none:unknown"). Los
// ids de geocerca siguen fence.IDPattern, que nunca admite ":", así que
// SplitN con límite 2 basta y "none" (sin geocerca) se traduce a "".
func fenceOfKey(key string) string {
	id := strings.SplitN(key, ":", 2)[0]
	if id == "none" {
		return ""
	}
	return id
}

// fromFence convierte una acción de geocerca en una acción planificada.
func fromFence(cur device.Device, a fence.Action, fenceID string, when fence.When) Planned {
	return Planned{Device: cur, Action: a.Action, Params: a.Params, FenceID: fenceID, Trigger: string(when)}
}

// PlanTransition decide las acciones de geocerca para una transición:
// on_enter de la geocerca destino, on_exit de la de origen y on_unknown al
// perder la ubicación.
func PlanTransition(cur device.Device, tr *transition.Transition, fences []fence.Fence) []Planned {
	if tr == nil {
		return nil
	}
	var out []Planned
	if from := fenceOfKey(tr.From); from != "" {
		if f, ok := fence.FindByID(fences, from); ok {
			for _, a := range f.ActionsFor(fence.OnExit) {
				out = append(out, fromFence(cur, a, f.ID, fence.OnExit))
			}
		}
	}
	if to := fenceOfKey(tr.To); to != "" {
		if f, ok := fence.FindByID(fences, to); ok {
			for _, a := range f.ActionsFor(fence.OnEnter) {
				out = append(out, fromFence(cur, a, f.ID, fence.OnEnter))
			}
		}
	}
	if cur.FenceState == device.Unknown {
		for _, f := range fences {
			for _, a := range f.ActionsFor(fence.OnUnknown) {
				out = append(out, fromFence(cur, a, f.ID, fence.OnUnknown))
			}
		}
	}
	return out
}

// planStanding dispara on_violation cada N ciclos mientras el dispositivo
// siga fuera; estar dentro resetea el contador de esa geocerca.
func (e *Engine) planStanding(cur device.Device, fences []fence.Fence) []Planned {
	var out []Planned
	for _, f := range fences {
		acts := f.ActionsFor(fence.OnViolation)
		key := cur.ID + "|" + f.ID
		if cur.FenceState != device.Outside || len(acts) == 0 {
			delete(e.violations, key)
			continue
		}
		e.violations[key]++
		interval := f.Rules.ViolationIntervalCycles
		if interval < 1 {
			interval = 1
		}
		if e.violations[key]%interval != 0 {
			continue
		}
		for _, a := range acts {
			out = append(out, fromFence(cur, a, f.ID, fence.OnViolation))
		}
	}
	return out
}

// alreadyFired es el primer guardarraíl de la spec §5.4: el dedupe por ciclo.
// La clave es la de 1.x (device|action|fence), sin el trigger, para que una
// misma condición no dispare la misma orden dos veces por dos caminos (p. ej.
// on_enter y una política) en el mismo ciclo.
func (e *Engine) alreadyFired(p Planned) bool {
	key := fmt.Sprintf("%s|%s|%s", p.Device.ID, p.Action, p.FenceID)
	if e.fired[key] {
		return true
	}
	e.fired[key] = true
	return false
}

// stamp marca el resultado con la procedencia de la acción planificada y con
// el dry-run que fijó el guardarraíl: el conector no es fuente de verdad de
// ninguno de los dos.
func stamp(res action.Result, p Planned, dryRun bool) action.Result {
	res.DryRun = dryRun
	res.FenceID, res.RouteID, res.PolicyID, res.PlaybookID = p.FenceID, p.RouteID, p.PolicyID, p.PlaybookID
	res.Trigger, res.Severity = p.Trigger, p.Severity
	return res
}

// apply pasa la acción por los guardarraíles y, si la dejan, la ejecuta.
// El segundo valor dice si hay que registrarla: lo bloqueado se registra (es
// la auditoría de un intento parado), lo suprimido no deja más rastro que el
// contador del ciclo.
func (e *Engine) apply(ctx context.Context, p Planned, st *CycleStats) (action.Result, bool) {
	g := e.Guardrails()
	dec := g.Decide(p.Device, p.Action)
	switch {
	case dec.Blocked:
		st.ActionsBlocked++
		e.opts.Logger.Warn("acción bloqueada", "device", p.Device.ID, "action", p.Action, "code", dec.Code)
		return stamp(action.Result{Adapter: p.Device.Provider, OK: false, Blocked: true, ErrorType: dec.Code,
			Error: dec.Reason, DeviceID: p.Device.ID, DeviceName: p.Device.Name, Action: p.Action,
			Params: p.Params, At: e.opts.Now().UTC()}, p, false), true
	case !dec.Allow:
		st.ActionsSuppressed++
		e.opts.Logger.Info("acción suprimida", "device", p.Device.ID, "action", p.Action, "code", dec.Code)
		return action.Result{}, false
	}
	res := e.execute(ctx, p, dec.DryRun)
	st.ActionsExecuted++
	if err := g.Record(p.Device, p.Action, res); err != nil {
		e.logPersistenceError(st, "cooldown", p.Device.ID, err)
	}
	return res, true
}

// execute llama al conector con el dry-run que decidió el guardarraíl.
func (e *Engine) execute(ctx context.Context, p Planned, dryRun bool) action.Result {
	ad, ok := e.adapters[p.Device.Provider]
	if !ok {
		return stamp(action.Result{Adapter: p.Device.Provider, OK: false, DeviceID: p.Device.ID,
			DeviceName: p.Device.Name, Action: p.Action, Params: p.Params, ErrorType: "no_adapter",
			Error: "sin conector para el proveedor", At: e.opts.Now().UTC()}, p, true)
	}
	res := ad.Execute(ctx, p.Device, p.Action, p.Params, dryRun)
	if res.At.IsZero() {
		res.At = e.opts.Now().UTC()
	}
	return stamp(res, p, dryRun)
}
