package simulation

import (
	"context"
	"math"
	"path/filepath"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestDefaultSeedValida(t *testing.T) {
	s := DefaultSeed()
	if err := s.Validate(); err != nil {
		t.Fatal(err)
	}
	if len(s.Devices) != 6 || s.Devices[0].ID != "dev-001" || s.Devices[0].Inventory.Model == "" {
		t.Fatalf("seed: %+v", s.Devices)
	}
}

func TestSeedValidateRechazaDuplicadosYSinWaypoints(t *testing.T) {
	s := Seed{Devices: []SeedDevice{{ID: "a", Name: "A", Platform: "android", Waypoints: []geo.Point{{}}}, {ID: "a", Name: "B", Platform: "ios", Waypoints: []geo.Point{{}}}}}
	if err := s.Validate(); err == nil {
		t.Fatal("id duplicado")
	}
	s = Seed{Devices: []SeedDevice{{ID: "a", Name: "A", Platform: "android"}}}
	if err := s.Validate(); err == nil {
		t.Fatal("sin waypoints")
	}
}

func TestPosition(t *testing.T) {
	wps := []geo.Point{{Lat: 0, Lng: 0}, {Lat: 3, Lng: 3}}
	if p := Position(wps, 0); p != wps[0] {
		t.Fatalf("tick 0: %v", p)
	}
	if p := Position(wps, 1); math.Abs(p.Lat-1) > 1e-9 || math.Abs(p.Lng-1) > 1e-9 {
		t.Fatalf("tick 1 = 1/3 del segmento: %v", p)
	}
	if p := Position(wps, 3); p != wps[1] {
		t.Fatalf("tick 3 = segundo waypoint: %v", p)
	}
	if p := Position(wps, 6); p != wps[0] {
		t.Fatalf("tick 6 vuelve al inicio: %v", p)
	}
	if p := Position(nil, 5); p.Lat != 40.4168 {
		t.Fatalf("sin waypoints → Madrid: %v", p)
	}
}

func TestFetchDevicesMueveYRellena(t *testing.T) {
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	a := New(DefaultSeed(), func() time.Time { return now })
	ds, err := a.FetchDevices(context.Background())
	if err != nil || len(ds) != 6 {
		t.Fatalf("%v %d", err, len(ds))
	}
	d := ds[0]
	if d.Provider != "simulation" || d.Location.Source != "simulation" || d.Location.Point == nil || *d.Location.AccuracyM != 12 || !d.LastReportAt.Equal(now) || d.ProviderRefs["simulation"] != "dev-001" {
		t.Fatalf("campos: %+v", d)
	}
	if d.Inventory.Model != "Samsung Galaxy Tab Active5" || d.Inventory.BatteryLevel == nil {
		t.Fatalf("inventario: %+v", d.Inventory)
	}
	first := *ds[1].Location.Point
	ds2, _ := a.FetchDevices(context.Background())
	if *ds2[1].Location.Point == first {
		t.Fatal("dev-002 debe moverse entre ticks")
	}
	if a.Tick() != 2 {
		t.Fatalf("tick=%d", a.Tick())
	}
}

func TestExecuteSimulaSinErrores(t *testing.T) {
	a := New(DefaultSeed(), time.Now)
	ds, _ := a.FetchDevices(context.Background())
	for _, act := range action.All {
		r := a.Execute(context.Background(), ds[0], act, map[string]any{"text": "hola"}, true)
		if !r.OK || !r.Simulated || !r.DryRun || r.Adapter != "simulation" || r.DeviceID != "dev-001" || r.CommandID == "" || r.At.IsZero() {
			t.Fatalf("%s: %+v", act, r)
		}
	}
	if !a.Capabilities().Supports(action.Wipe) || !a.Capabilities().Location {
		t.Fatal("capacidades")
	}
	if c := a.TestConnection(context.Background()); !c.OK || c.Verified != "simulated" {
		t.Fatalf("%+v", c)
	}
}

func TestLoadSaveSeedYNewFromConfig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "seed.json")
	if _, err := LoadSeed(path); err == nil {
		t.Fatal("fichero ausente debe fallar")
	}
	if err := SaveSeed(path, DefaultSeed()); err != nil {
		t.Fatal(err)
	}
	s, err := LoadSeed(path)
	if err != nil || len(s.Devices) != 6 {
		t.Fatal(err)
	}
	ad, err := NewFromConfig(map[string]any{"seed_path": path}, nil)
	if err != nil || ad.Name() != Name {
		t.Fatal(err)
	}
	if _, err := NewFromConfig(map[string]any{"seed_path": filepath.Join(t.TempDir(), "nope.json")}, nil); err == nil {
		t.Fatal("seed_path inexistente debe fallar")
	}
	if ad, err := NewFromConfig(nil, nil); err != nil || ad == nil {
		t.Fatal("sin seed_path usa la seed por defecto")
	}
}
