// Package fence modela geocercas (círculo o polígono) y sus acciones por
// evento. Sin I/O. El borde del círculo es inclusivo; el del polígono queda
// indefinido por diseño (medida cero con GPS real).
package fence

import (
	"errors"
	"fmt"
	"regexp"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Kind es la forma de la geocerca.
type Kind string

// When es el evento que dispara una acción.
type When string

const (
	Circle  Kind = "circle"
	Polygon Kind = "polygon"

	OnEnter     When = "on_enter"
	OnExit      When = "on_exit"
	OnViolation When = "on_violation"
	OnUnknown   When = "on_unknown"
)

// IDPattern es el formato de los identificadores de dominio (slug).
var IDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,63}$`)

// Action es una acción ligada a un evento de geocerca.
type Action struct {
	Action  action.Action  `json:"action"`
	When    When           `json:"when"`
	Params  map[string]any `json:"params,omitempty"`
	Enabled bool           `json:"enabled"`
}

// Rules ajusta el comportamiento de la geocerca.
type Rules struct {
	ViolationIntervalCycles int `json:"violation_interval_cycles,omitempty"`
	DwellSeconds            int `json:"dwell_seconds,omitempty"`
}

// Fence es una geocerca.
type Fence struct {
	ID        string      `json:"id"`
	Name      string      `json:"name"`
	Kind      Kind        `json:"kind"`
	Center    *geo.Point  `json:"center,omitempty"`
	RadiusM   float64     `json:"radius_m,omitempty"`
	Polygon   []geo.Point `json:"polygon,omitempty"`
	Rules     Rules       `json:"rules"`
	Actions   []Action    `json:"actions"`
	CreatedAt time.Time   `json:"created_at"`
	UpdatedAt time.Time   `json:"updated_at"`
}

// Contains indica si el punto cae dentro de la geocerca.
func (f Fence) Contains(p geo.Point) bool {
	switch f.Kind {
	case Circle:
		return f.Center != nil && geo.HaversineM(p, *f.Center) <= f.RadiusM
	case Polygon:
		return geo.PointInPolygon(p, f.Polygon)
	}
	return false
}

// Validate comprueba id, nombre, forma, reglas y acciones.
func (f Fence) Validate() error {
	if !IDPattern.MatchString(f.ID) {
		return fmt.Errorf("id %q inválido: usa minúsculas, dígitos y guiones", f.ID)
	}
	if f.ID == "none" {
		return fmt.Errorf("id %q reservado", f.ID)
	}
	if f.Name == "" {
		return errors.New("nombre obligatorio")
	}
	if err := f.validateShape(); err != nil {
		return err
	}
	if f.Rules.ViolationIntervalCycles < 0 || f.Rules.DwellSeconds < 0 {
		return errors.New("las reglas no admiten valores negativos")
	}
	for i, a := range f.Actions {
		if _, err := action.Parse(string(a.Action)); err != nil {
			return fmt.Errorf("acción %d: %w", i, err)
		}
		switch a.When {
		case OnEnter, OnExit, OnViolation, OnUnknown:
		default:
			return fmt.Errorf("acción %d: evento %q desconocido", i, a.When)
		}
	}
	return nil
}

func (f Fence) validateShape() error {
	switch f.Kind {
	case Circle:
		if f.Center == nil {
			return errors.New("círculo sin centro")
		}
		if err := f.Center.Valid(); err != nil {
			return fmt.Errorf("centro: %w", err)
		}
		if f.RadiusM <= 0 {
			return errors.New("radio debe ser > 0")
		}
	case Polygon:
		if len(f.Polygon) < 3 {
			return geo.ErrEmptyPolygon
		}
		for i, p := range f.Polygon {
			if err := p.Valid(); err != nil {
				return fmt.Errorf("vértice %d: %w", i, err)
			}
		}
	default:
		return fmt.Errorf("tipo %q desconocido (circle|polygon)", f.Kind)
	}
	return nil
}

// ValidateAll valida cada geocerca y la unicidad de ids.
func ValidateAll(fs []Fence) error {
	seen := map[string]bool{}
	for _, f := range fs {
		if err := f.Validate(); err != nil {
			return fmt.Errorf("geocerca %q: %w", f.ID, err)
		}
		if seen[f.ID] {
			return fmt.Errorf("id duplicado %q", f.ID)
		}
		seen[f.ID] = true
	}
	return nil
}

// FindByID busca una geocerca.
func FindByID(fs []Fence, id string) (Fence, bool) {
	for _, f := range fs {
		if f.ID == id {
			return f, true
		}
	}
	return Fence{}, false
}

// ActionsFor devuelve las acciones habilitadas para un evento.
func (f Fence) ActionsFor(w When) []Action {
	var out []Action
	for _, a := range f.Actions {
		if a.Enabled && a.When == w {
			out = append(out, a)
		}
	}
	return out
}
