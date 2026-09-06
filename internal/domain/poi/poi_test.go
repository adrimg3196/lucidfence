package poi

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestValidateYGeoJSON(t *testing.T) {
	p := POI{ID: "poi-school-001", Name: "Colegio Público", Category: "school", Tags: []string{"education"}, Point: geo.Point{Lat: 40.418, Lng: -3.705}}
	if err := p.Validate(); err != nil {
		t.Fatal(err)
	}
	for name, bad := range map[string]POI{
		"id":       {ID: "POI 1", Name: "x", Category: "c", Point: geo.Point{}},
		"nombre":   {ID: "p", Category: "c"},
		"category": {ID: "p", Name: "x"},
		"coords":   {ID: "p", Name: "x", Category: "c", Point: geo.Point{Lng: 200}},
	} {
		if err := bad.Validate(); err == nil {
			t.Errorf("%s: debería fallar", name)
		}
	}
	if err := ValidateAll([]POI{p, p}); err == nil {
		t.Fatal("duplicado")
	}
	// Test ValidateAll with valid POIs
	if err := ValidateAll([]POI{p}); err != nil {
		t.Errorf("ValidateAll con POI válido: %v", err)
	}
	// Test ValidateAll with invalid POI
	invalid := POI{ID: "bad", Name: "x"}
	if err := ValidateAll([]POI{invalid}); err == nil {
		t.Fatal("ValidateAll debería detectar POI inválido")
	}
	fc := ToGeoJSON([]POI{p})
	feats := fc["features"].([]map[string]any)
	geom := feats[0]["geometry"].(map[string]any)
	coords := geom["coordinates"].([]float64)
	if fc["type"] != "FeatureCollection" || coords[0] != -3.705 || coords[1] != 40.418 {
		t.Fatalf("GeoJSON incorrecto: %v", fc)
	}
	if _, ok := FindByID([]POI{p}, "poi-school-001"); !ok {
		t.Fatal("FindByID")
	}
	// Test FindByID with non-existent POI
	if _, ok := FindByID([]POI{p}, "no-existe"); ok {
		t.Fatal("FindByID no debería encontrar POI inexistente")
	}
	// Test ToGeoJSON with empty slice
	fc = ToGeoJSON([]POI{})
	if fc["type"] != "FeatureCollection" {
		t.Fatal("GeoJSON vacío debería ser una FeatureCollection")
	}
}
