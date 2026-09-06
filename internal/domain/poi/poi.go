// Package poi modela puntos de interés que dan contexto al riesgo (colegios,
// hospitales, zonas restringidas). Se exportan como GeoJSON para el mapa.
package poi

import (
	"errors"
	"fmt"

	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// POI es un punto de interés.
type POI struct {
	ID       string            `json:"id"`
	Name     string            `json:"name"`
	Category string            `json:"category"`
	Tags     []string          `json:"tags,omitempty"`
	Point    geo.Point         `json:"point"`
	Metadata map[string]string `json:"metadata,omitempty"`
}

// Validate comprueba id, nombre, categoría y coordenadas.
func (p POI) Validate() error {
	if !fence.IDPattern.MatchString(p.ID) {
		return fmt.Errorf("id %q inválido", p.ID)
	}
	if p.Name == "" {
		return errors.New("nombre obligatorio")
	}
	if p.Category == "" {
		return errors.New("categoría obligatoria")
	}
	if err := p.Point.Valid(); err != nil {
		return err
	}
	return nil
}

// ValidateAll valida y exige ids únicos.
func ValidateAll(ps []POI) error {
	seen := map[string]bool{}
	for _, p := range ps {
		if err := p.Validate(); err != nil {
			return fmt.Errorf("poi %q: %w", p.ID, err)
		}
		if seen[p.ID] {
			return fmt.Errorf("id duplicado %q", p.ID)
		}
		seen[p.ID] = true
	}
	return nil
}

// FindByID busca un POI.
func FindByID(ps []POI, id string) (POI, bool) {
	for _, p := range ps {
		if p.ID == id {
			return p, true
		}
	}
	return POI{}, false
}

// ToGeoJSON construye una FeatureCollection (coordenadas [lng, lat]).
func ToGeoJSON(ps []POI) map[string]any {
	features := make([]map[string]any, 0, len(ps))
	for _, p := range ps {
		features = append(features, map[string]any{
			"type":       "Feature",
			"properties": map[string]any{"id": p.ID, "name": p.Name, "category": p.Category, "tags": p.Tags, "metadata": p.Metadata},
			"geometry":   map[string]any{"type": "Point", "coordinates": []float64{p.Point.Lng, p.Point.Lat}},
		})
	}
	return map[string]any{"type": "FeatureCollection", "features": features}
}
