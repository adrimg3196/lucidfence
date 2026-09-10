package engine

import (
	"fmt"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
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

// Disparadores propios del motor. Los de geocerca son los cuatro fence.When
// (on_enter, on_exit, on_violation, on_unknown); estos tres nombran las
// órdenes que no nacen de un evento de geocerca.
const (
	TriggerPolicy    = "policy"
	TriggerRouteExit = "route_exit"
	TriggerDwell     = "dwell"
)

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

// fromFence convierte una acción de geocerca en una acción planificada. El
// disparador y la severidad los pone quien planifica: la misma acción on_enter
// sale como "on_enter" desde la transición y como "dwell" desde planDwell.
func fromFence(cur device.Device, a fence.Action, fenceID, trigger, severity string) Planned {
	return Planned{Device: cur, Action: a.Action, Params: a.Params,
		FenceID: fenceID, Trigger: trigger, Severity: severity}
}

// PlanTransition decide las acciones de geocerca para una transición: on_exit
// de la de origen, on_enter de la de destino y on_unknown al perder la
// ubicación.
//
// Dos reglas que no son negociables:
//
//   - una geocerca con rules.dwell_seconds > 0 NO emite su on_enter aquí; lo
//     emite planDwell cuando la estancia supera el umbral.
//   - on_unknown jamás emite una acción destructiva: perder señal no es
//     evidencia y no justifica lock, wipe, reboot ni clear_passcode
//     (legacy/lucidfence/core/engine.py::_fire_actions).
func PlanTransition(cur device.Device, tr *transition.Transition, fences []fence.Fence) []Planned {
	if tr == nil {
		return nil
	}
	var out []Planned
	if from := fenceOfKey(tr.From); from != "" {
		if f, ok := fence.FindByID(fences, from); ok {
			for _, a := range f.ActionsFor(fence.OnExit) {
				out = append(out, fromFence(cur, a, f.ID, string(fence.OnExit), risk.SeverityMedium))
			}
		}
	}
	if to := fenceOfKey(tr.To); to != "" {
		if f, ok := fence.FindByID(fences, to); ok && f.Rules.DwellSeconds <= 0 {
			for _, a := range f.ActionsFor(fence.OnEnter) {
				out = append(out, fromFence(cur, a, f.ID, string(fence.OnEnter), risk.SeverityMedium))
			}
		}
	}
	if cur.FenceState == device.Unknown {
		for _, f := range fences {
			for _, a := range f.ActionsFor(fence.OnUnknown) {
				if a.Action.Destructive() {
					continue
				}
				out = append(out, fromFence(cur, a, f.ID, string(fence.OnUnknown), risk.SeverityMedium))
			}
		}
	}
	return out
}

// deviationText formatea la desviación como 1.x ("742.5 m").
func deviationText(m *float64) string {
	if m == nil {
		return "distancia desconocida"
	}
	return fmt.Sprintf("%.1f m", *m)
}

// routeActions devuelve las acciones on_exit habilitadas de la ruta o, si la
// ruta no declara ninguna, el notify de respaldo de 1.x
// (engine.py::_fire_route_exit): la salida del corredor nunca es silenciosa.
// Una ruta que declara acciones y las tiene todas apagadas no dispara nada: el
// operador las apagó a propósito.
func routeActions(r route.Route, deviationM *float64) []fence.Action {
	if len(r.Actions) == 0 {
		return []fence.Action{{Action: action.Notify, When: fence.OnExit, Enabled: true,
			Params: map[string]any{
				"channel": "security",
				"msg":     "Desviación de ruta: " + deviationText(deviationM) + " fuera del corredor",
			}}}
	}
	var out []fence.Action
	for _, a := range r.Actions {
		if a.Enabled && a.When == fence.OnExit {
			out = append(out, a)
		}
	}
	return out
}

// planRoute emite las acciones on_exit de la ruta cuando el dispositivo acaba
// de salirse de su corredor. Es independiente de la geocerca: salirse sin
// cambiar de geocerca dispara igual, que era el caso que 1.x tuvo que
// arreglar. Solo en la transición: seguir fuera no reemite en cada ciclo, y la
// primera vez que se ve un dispositivo no es una salida.
func planRoute(prev *device.Device, cur device.Device, routes []route.Route) []Planned {
	if prev == nil || cur.RouteState != device.OffRoute {
		return nil
	}
	if prev.RouteState != device.OnRoute && prev.RouteState != device.Unassigned {
		return nil
	}
	r, ok := route.ForDevice(routes, cur.ID)
	if !ok {
		return nil
	}
	var out []Planned
	for _, a := range routeActions(r, cur.RouteDeviationM) {
		out = append(out, Planned{Device: cur, Action: a.Action, Params: a.Params,
			RouteID: r.ID, Trigger: TriggerRouteExit, Severity: risk.SeverityMedium})
	}
	return out
}

// plan reúne todas las órdenes candidatas de un dispositivo, en el orden de
// 1.x: políticas, salida de corredor, transición de geocerca, dwell y
// violación sostenida. El orden importa porque el dedupe conserva la primera
// de cada cubo (dispositivo|acción|geocerca): así una orden que pidió una
// política queda registrada con su policy_id en vez de con el evento de
// geocerca que la habría pedido igual.
func (e *Engine) plan(in cycleInput, prev, cur *device.Device, tr *transition.Transition) []Planned {
	out := e.planPolicies(cur, subjectFor(*cur), in.policies)
	out = append(out, planRoute(prev, *cur, in.routes)...)
	out = append(out, PlanTransition(*cur, tr, in.fences)...)
	out = append(out, e.planDwell(*cur, in.fences)...)
	return append(out, e.planStanding(*cur, in.fences)...)
}
