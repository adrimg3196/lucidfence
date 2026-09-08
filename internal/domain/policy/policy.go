package policy

import (
	"errors"
	"fmt"
	"slices"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// Ops enumera los ocho comparadores en orden estable; no modificar.
var Ops = []Op{OpEq, OpNe, OpGt, OpGte, OpLt, OpLte, OpIn, OpContains}

// Action es un candidato declarativo, nunca una ejecución.
// Params contiene valores JSON; los resultados de matching son independientes.
type Action struct {
	Action action.Action  `json:"action"`
	Params map[string]any `json:"params,omitempty"`
}

// Policy es una conjunción explícita y sus acciones candidatas.
type Policy struct {
	ID          string      `json:"id"`
	Name        string      `json:"name"`
	Description string      `json:"description,omitempty"`
	When        []Condition `json:"when"`
	Actions     []Action    `json:"actions"`
	Enabled     bool        `json:"enabled"`
	Severity    string      `json:"severity"`
	Source      string      `json:"source,omitempty"`
	TemplateID  string      `json:"template_id,omitempty"`
	CreatedAt   time.Time   `json:"created_at"`
	UpdatedAt   time.Time   `json:"updated_at"`
}

// ParseOp exige un operador declarado.
func ParseOp(s string) (Op, error) {
	if slices.Contains(Ops, Op(s)) {
		return Op(s), nil
	}
	return "", fmt.Errorf("operador desconocido %q (eq|ne|gt|gte|lt|lte|in|contains)", s)
}

// Validate valida una condición independiente para otros consumidores del dominio.
func (c Condition) Validate() error {
	if !validField(c.Field) {
		return fmt.Errorf("campo %q desconocido o sin 'field'", c.Field)
	}
	if _, err := ParseOp(string(c.Op)); err != nil {
		return fmt.Errorf("campo %q: %w", c.Field, err)
	}
	if err := validateValue(c.Value, c.Op); err != nil {
		return fmt.Errorf("campo %q: %w", c.Field, err)
	}
	return nil
}

// Validate comprueba una acción sin ejecutarla.
func (a Action) Validate() error {
	if _, err := action.Parse(string(a.Action)); err != nil {
		return err
	}
	if _, err := jsonCopy(a.Params); err != nil {
		return fmt.Errorf("acción %q params JSON inválidos: %w", a.Action, err)
	}
	return nil
}

// Validate exige una política completa.
func (p Policy) Validate() error {
	if err := p.validate(); err != nil {
		return fmt.Errorf("política %q: %w", p.ID, err)
	}
	return nil
}

func (p Policy) validate() error {
	if !fence.IDPattern.MatchString(p.ID) {
		return fmt.Errorf("id %q inválido: usa minúsculas, dígitos y guiones", p.ID)
	}
	if strings.TrimSpace(p.Name) == "" {
		return errors.New("nombre obligatorio")
	}
	if len(p.When) == 0 {
		return errors.New("'when' debe ser una lista no vacía")
	}
	for i, c := range p.When {
		if err := c.Validate(); err != nil {
			return fmt.Errorf("condición %d: %w", i, err)
		}
	}
	if len(p.Actions) == 0 {
		return errors.New("'actions' debe ser una lista no vacía")
	}
	for i, a := range p.Actions {
		if err := a.Validate(); err != nil {
			return fmt.Errorf("acción %d: %w", i, err)
		}
	}
	if !slices.Contains(risk.Severities, p.Severity) {
		return fmt.Errorf("severidad %q inválida (%s)", p.Severity, strings.Join(risk.Severities, "|"))
	}
	return nil
}

// ValidateAll valida una lista y la unicidad de IDs.
func ValidateAll(ps []Policy) error {
	if ps == nil {
		return errors.New("se requiere una lista de políticas, no null")
	}
	seen := make(map[string]bool, len(ps))
	for _, p := range ps {
		if err := p.Validate(); err != nil {
			return err
		}
		if seen[p.ID] {
			return fmt.Errorf("id de política duplicado %q", p.ID)
		}
		seen[p.ID] = true
	}
	return nil
}

// FindByID busca sin I/O.
func FindByID(ps []Policy, id string) (Policy, bool) {
	for _, p := range ps {
		if p.ID == id {
			return p, true
		}
	}
	return Policy{}, false
}

func validField(field string) bool {
	if slices.Contains(Fields, field) {
		return true
	}
	rest, ok := strings.CutPrefix(field, "signal:")
	name, key, found := strings.Cut(rest, ".")
	return ok && found && strings.TrimSpace(name) != "" && strings.TrimSpace(key) != ""
}
