// Playbooks de fábrica, portados de DEFAULT_PLAYBOOKS
// (legacy/lucidfence/core/soar.py) y traducidos a la gramática 2.0. Los tres
// de 1.x que dependían del inventario de CVE por app (soar-cve-critical,
// soar-cve-outside, soar-cve-epss-high) no se portan en M2: 2.0 no tiene aún
// señal de vulnerabilidades por aplicación y un playbook que nunca casa es
// ruido en la bandeja. El severity_min de 1.x se expresa como una condición
// más sobre el campo `severity` del veredicto.
package playbook

import (
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// Defaults construye los playbooks de fábrica. Cada llamada devuelve valores
// nuevos (no hay catálogo mutable de paquete), así que quien los reciba puede
// editarlos. CreatedAt/UpdatedAt quedan a cero: las sella quien los persiste.
func Defaults() []Playbook {
	return []Playbook{
		pbNoncompliantOutside(),
		pbLocateUnknown(),
		pbOffrouteCritical(),
	}
}

// pbNoncompliantOutside es soar-rooted-outside de 1.x: no conforme y fuera de
// perímetro. El lock es destructivo, así que abre handoff en vez de ejecutarse.
func pbNoncompliantOutside() Playbook {
	return Playbook{
		ID:          "soar-noncompliant-outside",
		Name:        "No conforme y fuera de geocerca",
		Description: "Dispositivo no conforme fuera de su geocerca: bloqueo con aprobación humana y aviso al SOC.",
		When: []policy.Condition{
			{Field: "compliant", Op: policy.OpEq, Value: false},
			{Field: "fence_state", Op: policy.OpEq, Value: "outside"},
		},
		Actions: []policy.Action{
			{Action: action.Lock, Params: map[string]any{"reason": "noncompliant_outside"}},
			{Action: action.Notify, Params: map[string]any{
				"channel": "soc",
				"msg":     "Dispositivo no conforme fuera de geocerca",
			}},
		},
		Enabled:  true,
		Severity: risk.SeverityHigh,
	}
}

// pbLocateUnknown recoge el locate de soar-cve-outside de 1.x aplicado al caso
// que 2.0 sí observa: el dispositivo deja de reportar posición.
func pbLocateUnknown() Playbook {
	return Playbook{
		ID:          "soar-locate-unknown",
		Name:        "Localizar cuando se pierde la ubicación",
		Description: "Sin señal de ubicación fiable: forzar localización y avisar al SOC (posible robo o manipulación).",
		When: []policy.Condition{
			{Field: "fence_state", Op: policy.OpEq, Value: "unknown"},
		},
		Actions: []policy.Action{
			{Action: action.Locate},
			{Action: action.Notify, Params: map[string]any{
				"channel": "soc",
				"msg":     "Ubicación desconocida: se solicita localización",
			}},
		},
		Enabled:  true,
		Severity: risk.SeverityMedium,
	}
}

// pbOffrouteCritical traduce el severity_min="critical" de 1.x a una condición
// sobre el veredicto: fuera de ruta y con riesgo crítico, solo aviso.
func pbOffrouteCritical() Playbook {
	return Playbook{
		ID:          "soar-offroute-critical",
		Name:        "Fuera de ruta con riesgo crítico",
		Description: "Dispositivo fuera del corredor de su ruta con veredicto crítico: avisar al CISO sin tocar el dispositivo.",
		When: []policy.Condition{
			{Field: "route_state", Op: policy.OpEq, Value: "off_route"},
			{Field: "severity", Op: policy.OpEq, Value: risk.SeverityCritical},
		},
		Actions: []policy.Action{
			{Action: action.Notify, Params: map[string]any{
				"channel": "ciso",
				"msg":     "Dispositivo fuera de ruta con riesgo crítico",
			}},
		},
		Enabled:  true,
		Severity: risk.SeverityCritical,
	}
}
