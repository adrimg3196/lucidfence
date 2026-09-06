package route

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func sample() Route {
	return Route{ID: "route-centro", Name: "Ruta Comercial Centro", CorridorM: 300, DeviceIDs: []string{"dev-002"},
		Waypoints: []geo.Point{{Lat: 40.43, Lng: -3.69}, {Lat: 40.42, Lng: -3.71}},
		Actions:   []fence.Action{{Action: action.Notify, When: fence.OnExit, Enabled: true, Params: map[string]any{"msg": "fuera de ruta"}}}}
}

func TestDistanceMYForDevice(t *testing.T) {
	r := sample()
	if d := r.DistanceM(geo.Point{Lat: 40.43, Lng: -3.69}); d > 0.01 {
		t.Fatalf("waypoint sobre la ruta: %v", d)
	}
	if d := r.DistanceM(geo.Point{Lat: 40.44, Lng: -3.69}); d < 1000 {
		t.Fatalf("1 km al norte: %v", d)
	}
	if got, ok := ForDevice([]Route{r}, "dev-002"); !ok || got.ID != "route-centro" {
		t.Fatal("ForDevice")
	}
	if _, ok := ForDevice([]Route{r}, "dev-001"); ok {
		t.Fatal("dev-001 no tiene ruta")
	}
}

func TestValidate(t *testing.T) {
	bad := map[string]Route{
		"id":        {ID: "Ruta", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}},
		"nombre":    {ID: "r", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}},
		"corredor":  {ID: "r", Name: "x", CorridorM: 0, Waypoints: []geo.Point{{}, {Lat: 1}}},
		"waypoints": {ID: "r", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}}},
		"coords":    {ID: "r", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 99}}},
		"when":      {ID: "r", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}, Actions: []fence.Action{{Action: action.Notify, When: fence.OnEnter}}},
	}
	for name, r := range bad {
		if err := r.Validate(); err == nil {
			t.Errorf("%s: debería fallar", name)
		}
	}
	if err := sample().Validate(); err != nil {
		t.Fatal(err)
	}
	if err := ValidateAll([]Route{sample(), sample()}); err == nil {
		t.Fatal("ids duplicados")
	}
	// Test ValidateAll with valid routes
	if err := ValidateAll([]Route{sample()}); err != nil {
		t.Errorf("ValidateAll con ruta válida: %v", err)
	}
	// Test ValidateAll with invalid route
	invalid := Route{ID: "bad", Name: "x", CorridorM: 0, Waypoints: []geo.Point{{}, {Lat: 1}}}
	if err := ValidateAll([]Route{invalid}); err == nil {
		t.Fatal("ValidateAll debería detectar ruta inválida")
	}
	// Test FindByID
	if got, ok := FindByID([]Route{sample()}, "route-centro"); !ok || got.ID != "route-centro" {
		t.Fatal("FindByID")
	}
	if _, ok := FindByID([]Route{sample()}, "no-existe"); ok {
		t.Fatal("FindByID no debería encontrar ruta inexistente")
	}
}
