package engine

import (
	"context"
	"fmt"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

// Aplicación de los guardarraíles de la spec §5.4 sobre una acción ya
// planificada: guardrails.go decide, guardrails_cooldown.go recuerda y aquí se
// aplica el orden completo. alreadyFired es el primer paso (el dedupe por
// ciclo, que necesita el estado del ciclo y por eso no cabe en Decide); apply
// consulta a Decide y enruta el veredicto (bloqueada → se audita, suprimida →
// solo cuenta, permitida → se ejecuta y arma el cooldown); stamp es el único
// sitio que sella el dry_run del resultado auditado; execute es la única
// llamada del motor a un conector con esa marca. Va en un fichero guardrails*
// a propósito: es lo que protege el patrón de CODEOWNERS (spec §9.2) y lo que
// vigila internal/arch.

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
