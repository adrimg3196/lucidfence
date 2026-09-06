// Package route modela rutas con corredor: una polilínea y una anchura en
// metros. Un dispositivo asignado está on_route si su distancia a la
// polilínea no supera el corredor.
package route

import (
	"errors"
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Route es una ruta con corredor.
type Route struct {
	ID        string         `json:"id"`
	Name      string         `json:"name"`
	CorridorM float64        `json:"corridor_m"`
	Waypoints []geo.Point    `json:"waypoints"`
	DeviceIDs []string       `json:"device_ids"`
	Color     string         `json:"color,omitempty"`
	Actions   []fence.Action `json:"actions"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
}

// DistanceM es la distancia del punto a la polilínea.
func (r Route) DistanceM(p geo.Point) float64 {
	return geo.DistanceToPolylineM(p, r.Waypoints)
}

// Validate comprueba id, nombre, corredor, waypoints y acciones (solo on_exit).
func (r Route) Validate() error {
	if !fence.IDPattern.MatchString(r.ID) {
		return fmt.Errorf("id %q inválido", r.ID)
	}
	if r.Name == "" {
		return errors.New("nombre obligatorio")
	}
	if r.CorridorM <= 0 {
		return errors.New("corredor debe ser > 0")
	}
	if len(r.Waypoints) < 2 {
		return errors.New("una ruta necesita al menos 2 waypoints")
	}
	for i, w := range r.Waypoints {
		if err := w.Valid(); err != nil {
			return fmt.Errorf("waypoint %d: %w", i, err)
		}
	}
	for i, a := range r.Actions {
		if a.When != fence.OnExit {
			return fmt.Errorf("acción %d: las rutas solo admiten on_exit", i)
		}
	}
	return nil
}

// ValidateAll valida y exige ids únicos.
func ValidateAll(rs []Route) error {
	seen := map[string]bool{}
	for _, r := range rs {
		if err := r.Validate(); err != nil {
			return fmt.Errorf("ruta %q: %w", r.ID, err)
		}
		if seen[r.ID] {
			return fmt.Errorf("id duplicado %q", r.ID)
		}
		seen[r.ID] = true
	}
	return nil
}

// ForDevice devuelve la primera ruta asignada al dispositivo.
func ForDevice(rs []Route, deviceID string) (Route, bool) {
	for _, r := range rs {
		for _, id := range r.DeviceIDs {
			if id == deviceID {
				return r, true
			}
		}
	}
	return Route{}, false
}

// FindByID busca una ruta.
func FindByID(rs []Route, id string) (Route, bool) {
	for _, r := range rs {
		if r.ID == id {
			return r, true
		}
	}
	return Route{}, false
}
