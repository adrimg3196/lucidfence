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

// Planned es una acción decidida pero aún no ejecutada.
type Planned struct {
	Device  device.Device
	Action  fence.Action
	FenceID string
	Trigger string
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
				out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnExit)})
			}
		}
	}
	if to := fenceOfKey(tr.To); to != "" {
		if f, ok := fence.FindByID(fences, to); ok {
			for _, a := range f.ActionsFor(fence.OnEnter) {
				out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnEnter)})
			}
		}
	}
	if cur.FenceState == device.Unknown {
		for _, f := range fences {
			for _, a := range f.ActionsFor(fence.OnUnknown) {
				out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnUnknown)})
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
			out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnViolation)})
		}
	}
	return out
}

// alreadyFired deduplica por ciclo (dispositivo, acción, geocerca, trigger).
func (e *Engine) alreadyFired(p Planned) bool {
	key := fmt.Sprintf("%s|%s|%s|%s", p.Device.ID, p.Action.Action, p.FenceID, p.Trigger)
	if e.fired[key] {
		return true
	}
	e.fired[key] = true
	return false
}

// execute pasa por los guardarraíles y llama al conector del dispositivo.
func (e *Engine) execute(ctx context.Context, p Planned) action.Result {
	dryRun := e.guard.DryRun(p.Action.Action)
	ad, ok := e.adapters[p.Device.Provider]
	if !ok {
		return action.Result{Adapter: p.Device.Provider, OK: false, DeviceID: p.Device.ID, DeviceName: p.Device.Name, Action: p.Action.Action,
			DryRun: dryRun, Error: "sin conector para el proveedor", At: e.opts.Now().UTC(), FenceID: p.FenceID, Trigger: p.Trigger}
	}
	res := ad.Execute(ctx, p.Device, p.Action.Action, p.Action.Params, dryRun)
	res.DryRun, res.FenceID, res.Trigger = dryRun, p.FenceID, p.Trigger
	if res.At.IsZero() {
		res.At = e.opts.Now().UTC()
	}
	return res
}
