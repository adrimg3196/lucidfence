package policy

import "github.com/adrimg3196/lucidfence/internal/domain/action"

// Templates construye cinco políticas nuevas en cada llamada.
func Templates() []Policy {
	ps := []Policy{routeExit(), rootedOutside(), deviation500(), offShiftOutside(), unknownNonCompliant()}
	for i := range ps {
		ps[i].Enabled = true
		ps[i].Source = "template"
		ps[i].TemplateID = ps[i].ID
	}
	return ps
}

// TemplateByID devuelve una política independiente del catálogo.
func TemplateByID(id string) (Policy, bool) { return FindByID(Templates(), id) }

func routeExit() Policy {
	return Policy{
		ID: "tpl-block-on-route-exit", Name: "Avisar al salir de la ruta", Severity: "high",
		Description: "Notificar a seguridad y avisar en el dispositivo al salir de la ruta asignada; no bloquea.",
		When:        []Condition{{Field: "signal:route_state.route_state", Op: OpEq, Value: "off_route"}},
		Actions: []Action{
			{Action: action.Notify, Params: map[string]any{"channel": "security", "msg": "Comercial fuera de ruta asignada"}},
			{Action: action.Message, Params: map[string]any{"text": "Has salido de tu ruta. Contacta con tu responsable."}},
		},
	}
}

func rootedOutside() Policy {
	return Policy{
		ID: "tpl-wipe-rooted-outside", Name: "Borrar si está rooteado y fuera de geocerca", Severity: "critical",
		Description: "Root o jailbreak fuera de geocerca: candidato a borrado y aviso al CISO, sin ejecución aquí.",
		When:        []Condition{{Field: "fence_state", Op: OpEq, Value: "outside"}, {Field: "signal:device_health.rooted", Op: OpEq, Value: true}},
		Actions: []Action{
			{Action: action.Notify, Params: map[string]any{"channel": "ciso", "msg": "CRÍTICO: rooteado fuera de geocerca"}},
			{Action: action.Wipe},
		},
	}
}

func deviation500() Policy {
	return Policy{
		ID: "tpl-ciso-deviation-500", Name: "Avisar al CISO si la desviación supera 500 m", Severity: "high",
		Description: "Desviación de ruta mayor de 500 m: notificación sin acción destructiva.",
		When:        []Condition{{Field: "signal:route_state.route_state", Op: OpEq, Value: "off_route"}, {Field: "signal:route_state.route_deviation_m", Op: OpGt, Value: 500}},
		Actions:     []Action{{Action: action.Notify, Params: map[string]any{"channel": "ciso", "msg": "Comercial con desviación de ruta > 500 m"}}},
	}
}

func offShiftOutside() Policy {
	return Policy{
		ID: "tpl-isolate-offshift-outside", Name: "Aislar fuera de turno y fuera de geocerca", Severity: "high",
		Description: "Fuera de geocerca y de un turno conocido: candidatos a bloqueo y aviso a seguridad.",
		When: []Condition{
			{Field: "fence_state", Op: OpEq, Value: "outside"},
			{Field: "signal:shift_match.shift_known", Op: OpEq, Value: true},
			{Field: "signal:shift_match.shift_match", Op: OpEq, Value: false},
		},
		Actions: []Action{
			{Action: action.Notify, Params: map[string]any{"channel": "security", "msg": "Fuera de geocerca fuera de turno"}},
			{Action: action.Lock},
		},
	}
}

func unknownNonCompliant() Policy {
	return Policy{
		ID: "tpl-locate-unknown-noncompliant", Name: "Localizar si se pierde la ubicación y no es conforme", Severity: "medium",
		Description: "Ubicación perdida y no conformidad observada: candidatos a localización y aviso.",
		When:        []Condition{{Field: "fence_state", Op: OpEq, Value: "unknown"}, {Field: "compliant", Op: OpEq, Value: false}},
		Actions: []Action{
			{Action: action.Locate},
			{Action: action.Notify, Params: map[string]any{"channel": "security", "msg": "Ubicación perdida en dispositivo no conforme"}},
		},
	}
}
