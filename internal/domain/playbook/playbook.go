// Package playbook modela el SOAR de LucidFence (spec §6.5): un playbook son
// condiciones (la misma gramática que las políticas) más acciones, y toda
// acción destructiva pasa por un handoff con aprobación humana. Sin I/O.
//
// A diferencia de legacy/lucidfence/core/soar.py, aquí no hay un motor de
// operadores propio: 2.0 tiene una sola gramática de reglas
// (internal/domain/policy), con las mismas ocho operaciones y el mismo
// resolutor de campos, de modo que el editor de playbooks es el de políticas.
package playbook

import (
	"fmt"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// Playbook es una respuesta automatizada: si todas las condiciones de When se
// cumplen (AND), sus acciones se planifican para el dispositivo.
type Playbook struct {
	ID          string             `json:"id"`
	Name        string             `json:"name"`
	Description string             `json:"description"`
	When        []policy.Condition `json:"when"`
	Actions     []policy.Action    `json:"actions"`
	Enabled     bool               `json:"enabled"`
	Severity    string             `json:"severity"`
	CreatedAt   time.Time          `json:"created_at"`
	UpdatedAt   time.Time          `json:"updated_at"`
}

// Validate es el espejo de SOARPlaybook.validate() de 1.x: id con formato de
// slug, nombre, condiciones compilables y al menos una acción del catálogo.
// La gramática NO se reimplementa aquí: cada condición y cada acción se
// validan con los Validate de policy, y este método solo antepone el playbook
// al error. Así el operador desconocido y la acción fuera de action.All se
// explican con las mismas palabras en políticas y en playbooks.
// La severidad se valida además contra risk.Severities, porque en 2.0 es la
// que clasifica el hallazgo en la bandeja y en las notificaciones.
func (p Playbook) Validate() error {
	if !fence.IDPattern.MatchString(p.ID) {
		return fmt.Errorf("id %q inválido: usa minúsculas, dígitos y guiones", p.ID)
	}
	if strings.TrimSpace(p.Name) == "" {
		return fmt.Errorf("playbook %q: nombre vacío", p.ID)
	}
	if len(p.When) == 0 {
		return fmt.Errorf("playbook %q: 'when' debe ser una lista no vacía de condiciones", p.ID)
	}
	for i, c := range p.When {
		if err := c.Validate(); err != nil {
			return fmt.Errorf("playbook %q: condición %d: %w", p.ID, i, err)
		}
	}
	if len(p.Actions) == 0 {
		return fmt.Errorf("playbook %q: sin acciones", p.ID)
	}
	for i, a := range p.Actions {
		if err := a.Validate(); err != nil {
			return fmt.Errorf("playbook %q: acción %d: %w", p.ID, i, err)
		}
	}
	if !validSeverity(p.Severity) {
		return fmt.Errorf("playbook %q: severidad %q inválida (%s)", p.ID, p.Severity, strings.Join(risk.Severities, "|"))
	}
	return nil
}

// validSeverity acepta solo las cuatro severidades puntuables, igual que en
// policy: "unknown" es lo que devuelve un veredicto fallido, no algo que un
// humano declare en un playbook. El homónimo de policy no es exportado, pero
// el catálogo (risk.Severities) sí es el mismo, así que no pueden divergir.
func validSeverity(s string) bool {
	for _, v := range risk.Severities {
		if v == s {
			return true
		}
	}
	return false
}

// ValidateAll valida cada playbook y la unicidad de ids.
func ValidateAll(ps []Playbook) error {
	seen := make(map[string]bool, len(ps))
	for _, p := range ps {
		if err := p.Validate(); err != nil {
			return err
		}
		if seen[p.ID] {
			return fmt.Errorf("id de playbook duplicado %q", p.ID)
		}
		seen[p.ID] = true
	}
	return nil
}

// FindByID busca un playbook por id.
func FindByID(ps []Playbook, id string) (Playbook, bool) {
	for _, p := range ps {
		if p.ID == id {
			return p, true
		}
	}
	return Playbook{}, false
}

// Match es un playbook que casó con el sujeto. MatchedFields lleva los campos
// de las condiciones que se cumplieron, para auditoría: es el estilo
// c7n:MatchedFilters que ya usaba legacy/lucidfence/core/soar.py.
type Match struct {
	PlaybookID    string          `json:"playbook_id"`
	Name          string          `json:"name"`
	Severity      string          `json:"severity"`
	Actions       []policy.Action `json:"actions"`
	MatchedFields []string        `json:"matched_fields"`
}

// matchFields aplica AND sobre todas las condiciones y devuelve los campos que
// casaron. Un playbook sin condiciones nunca casa: un 'when' vacío no puede
// significar "todos los dispositivos".
func (p Playbook) matchFields(s policy.Subject) ([]string, bool) {
	if len(p.When) == 0 {
		return nil, false
	}
	fields := make([]string, 0, len(p.When))
	for _, c := range p.When {
		if !c.Match(s) {
			return nil, false
		}
		fields = append(fields, c.Field)
	}
	return fields, true
}

// MatchAll devuelve las coincidencias en el orden del fichero, saltando los
// playbooks deshabilitados. Las acciones son copias profundas: quien las
// ejecuta puede añadir params sin tocar el playbook guardado.
func MatchAll(ps []Playbook, s policy.Subject) []Match {
	var out []Match
	for _, p := range ps {
		// Un playbook que no valida no produce candidatos, igual que en
		// policy.MatchAll: si su acción cae fuera de action.All, Destructive()
		// la da por no destructiva y llegaría al adapter sin pasar por el gate
		// humano de §6.5. Quien escribe (T20) y quien siembra (T7) validan, pero
		// el fichero del disco se puede editar a mano.
		if !p.Enabled || p.Validate() != nil {
			continue
		}
		fields, ok := p.matchFields(s)
		if !ok {
			continue
		}
		out = append(out, Match{
			PlaybookID:    p.ID,
			Name:          p.Name,
			Severity:      p.Severity,
			Actions:       cloneActions(p.Actions),
			MatchedFields: fields,
		})
	}
	return out
}

func cloneActions(as []policy.Action) []policy.Action {
	if as == nil {
		return nil
	}
	out := make([]policy.Action, len(as))
	for i, a := range as {
		out[i] = policy.Action{Action: a.Action, Params: cloneParams(a.Params)}
	}
	return out
}

func cloneParams(m map[string]any) map[string]any {
	if m == nil {
		return nil
	}
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = cloneValue(v)
	}
	return out
}

// cloneValue copia los valores que el JSON de un playbook puede contener:
// escalares (por valor), listas y objetos anidados.
func cloneValue(v any) any {
	switch t := v.(type) {
	case []any:
		out := make([]any, len(t))
		for i, e := range t {
			out[i] = cloneValue(e)
		}
		return out
	case []string:
		out := make([]string, len(t))
		copy(out, t)
		return out
	case map[string]any:
		return cloneParams(t)
	}
	return v
}
