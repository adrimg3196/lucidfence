package engine

import (
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// signalsOf reconstruye las señales tipadas a partir de las que el ciclo ya
// publicó en el dispositivo. device.Device las guarda como
// map[string]map[string]any para que domain/device no importe domain/risk; la
// conversión es exacta porque risk.Signal es map[string]any.
func signalsOf(d device.Device) risk.Signals {
	if len(d.Signals) == 0 {
		return nil
	}
	out := make(risk.Signals, len(d.Signals))
	for name, s := range d.Signals {
		out[name] = risk.Signal(s)
	}
	return out
}

// subjectFor compone el sujeto que evalúan las políticas (aquí) y los
// playbooks (T16): el dispositivo tal como quedó en este ciclo, su veredicto y
// las señales que lo respaldan.
func subjectFor(d device.Device) policy.Subject {
	return policy.NewSubject(d, d.Risk, signalsOf(d))
}

// planPolicies emite una orden por acción de cada política que casa y deja en
// cur.Risk.MatchedPolicies los ids en el orden del fichero, que es lo que el
// detalle de dispositivo enseña para explicar qué reglas dispararon.
//
// El FenceID de la orden es la geocerca en la que está el dispositivo (vacío si
// está fuera): es el cubo de dedupe de 1.x (_dedupe_action usa inside_fence),
// así que dos políticas que piden la misma acción sobre el mismo dispositivo se
// colapsan en una sola ejecución, y una política no repite una orden que ya
// pidió la propia geocerca.
//
// Un dispositivo cuya evaluación falló no dispara ninguna política: sin
// veredicto no hay evidencia, y 1.x ya dejaba fired_policies vacío cuando el
// evaluador reventaba.
func (e *Engine) planPolicies(cur *device.Device, subject policy.Subject, ps []policy.Policy) []Planned {
	if cur.EvaluationError != "" {
		return nil
	}
	ms := policy.MatchAll(ps, subject)
	ids := make([]string, 0, len(ms))
	for _, m := range ms {
		ids = append(ids, m.PolicyID)
	}
	cur.Risk.MatchedPolicies = ids
	if len(ms) == 0 {
		return nil
	}
	e.opts.Logger.Debug("políticas casadas", "device", cur.ID, "policies", ids)
	var out []Planned
	for _, m := range ms {
		for _, a := range m.Actions {
			out = append(out, Planned{Device: *cur, Action: a.Action, Params: a.Params,
				FenceID: cur.InsideFence, PolicyID: m.PolicyID,
				Trigger: TriggerPolicy, Severity: m.Severity})
		}
	}
	return out
}
