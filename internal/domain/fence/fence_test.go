package fence

import (
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func circle() Fence {
	return Fence{ID: "demo-hq", Name: "Demo HQ", Kind: Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
		Actions: []Action{{Action: action.Message, When: OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido"}}}}
}

func polygon() Fence {
	return Fence{ID: "warehouse-poly", Name: "Almacén", Kind: Polygon,
		Polygon: []geo.Point{{Lat: 40.40, Lng: -3.72}, {Lat: 40.40, Lng: -3.70}, {Lat: 40.41, Lng: -3.70}, {Lat: 40.41, Lng: -3.72}}}
}

func TestContainsCirculoBordeInclusivo(t *testing.T) {
	f := circle()
	if !f.Contains(geo.Point{Lat: 40.421, Lng: -3.708}) {
		t.Fatal("centro dentro")
	}
	if f.Contains(geo.Point{Lat: 40.43, Lng: -3.708}) {
		t.Fatal("a 1 km debe estar fuera")
	}
	// ~500 m al norte: 500/111194.93 grados de latitud.
	edge := geo.Point{Lat: 40.421 + 500.0/111194.93, Lng: -3.708}
	if !f.Contains(edge) {
		t.Fatal("el borde exacto es inclusivo (<=)")
	}
}

func TestContainsPoligono(t *testing.T) {
	f := polygon()
	if !f.Contains(geo.Point{Lat: 40.405, Lng: -3.71}) || f.Contains(geo.Point{Lat: 40.42, Lng: -3.71}) {
		t.Fatal("pertenencia al polígono incorrecta")
	}
	if (Fence{Kind: "hexagon"}).Contains(geo.Point{}) {
		t.Fatal("tipo desconocido nunca contiene")
	}
}

func TestValidate(t *testing.T) {
	cases := map[string]Fence{
		"id inválido":           {ID: "Demo HQ", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10},
		"id reservado none":     {ID: "none", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10},
		"sin nombre":            {ID: "a", Kind: Circle, Center: &geo.Point{}, RadiusM: 10},
		"círculo sin centro":    {ID: "a", Name: "x", Kind: Circle, RadiusM: 10},
		"radio cero":            {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 0},
		"centro fuera de rango": {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{Lat: 95}, RadiusM: 10},
		"polígono corto":        {ID: "a", Name: "x", Kind: Polygon, Polygon: []geo.Point{{}, {}}},
		"tipo desconocido":      {ID: "a", Name: "x", Kind: "hexagon"},
		"acción desconocida":    {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10, Actions: []Action{{Action: "explode", When: OnEnter}}},
		"when desconocido":      {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10, Actions: []Action{{Action: action.Lock, When: "sometimes"}}},
		"intervalo negativo":    {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10, Rules: Rules{ViolationIntervalCycles: -1}},
	}
	for name, f := range cases {
		if err := f.Validate(); err == nil {
			t.Errorf("%s: debería fallar", name)
		}
	}
	if err := circle().Validate(); err != nil {
		t.Fatal(err)
	}
	if err := polygon().Validate(); err != nil {
		t.Fatal(err)
	}
}

func TestValidateAllIDsUnicos(t *testing.T) {
	err := ValidateAll([]Fence{circle(), circle()})
	if err == nil || !strings.Contains(err.Error(), "duplicado") {
		t.Fatalf("esperaba error de id duplicado, got %v", err)
	}
	if err := ValidateAll([]Fence{circle(), polygon()}); err != nil {
		t.Fatal(err)
	}
}

func TestFindByIDYActionsFor(t *testing.T) {
	fs := []Fence{circle(), polygon()}
	if f, ok := FindByID(fs, "warehouse-poly"); !ok || f.Name != "Almacén" {
		t.Fatal("FindByID")
	}
	if _, ok := FindByID(fs, "nope"); ok {
		t.Fatal("no debería encontrar")
	}
	f := circle()
	f.Actions = append(f.Actions, Action{Action: action.Lock, When: OnExit, Enabled: false})
	if got := f.ActionsFor(OnEnter); len(got) != 1 || got[0].Action != action.Message {
		t.Fatalf("ActionsFor(on_enter)=%v", got)
	}
	if got := f.ActionsFor(OnExit); len(got) != 0 {
		t.Fatal("las deshabilitadas no cuentan")
	}
}
