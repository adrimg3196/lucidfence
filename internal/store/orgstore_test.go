package store

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

func org(t *testing.T) *OrgStore {
	t.Helper()
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	return o
}

// Las colecciones round-trip se dividen en un test por tipo (en vez de un
// único test monolítico) para mantener la complejidad ciclomática de cada
// función por debajo del límite del proyecto (gocyclo ≤ 15).

func TestFencesVaciasYRoundTrip(t *testing.T) {
	o := org(t)
	fs, err := o.Fences()
	if err != nil || len(fs) != 0 {
		t.Fatalf("sin fichero → vacío: %v %v", err, fs)
	}
	want := []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500}}
	if err := o.SaveFences(want); err != nil {
		t.Fatal(err)
	}
	got, _ := o.Fences()
	if len(got) != 1 || got[0].ID != "demo-hq" || got[0].Center.Lat != 40.421 {
		t.Fatalf("fences: %+v", got)
	}
}

func TestRoutesRoundTrip(t *testing.T) {
	o := org(t)
	if err := o.SaveRoutes([]route.Route{{ID: "r1", Name: "R", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}}}); err != nil {
		t.Fatal(err)
	}
	if rs, _ := o.Routes(); len(rs) != 1 || rs[0].ID != "r1" {
		t.Fatal("routes")
	}
}

func TestPOIsRoundTrip(t *testing.T) {
	o := org(t)
	if err := o.SavePOIs([]poi.POI{{ID: "p1", Name: "P", Category: "c"}}); err != nil {
		t.Fatal(err)
	}
	if ps, _ := o.POIs(); len(ps) != 1 {
		t.Fatal("pois")
	}
}

func TestDevicesRoundTrip(t *testing.T) {
	o := org(t)
	if err := o.SaveDevices([]device.Device{{ID: "dev-1", Name: "Uno"}}); err != nil {
		t.Fatal(err)
	}
	if ds, _ := o.Devices(); len(ds) != 1 || ds[0].Name != "Uno" {
		t.Fatal("devices")
	}
}

func TestColeccionEnvoltorioSchemaVersion(t *testing.T) {
	o := org(t)
	want := []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500}}
	if err := o.SaveFences(want); err != nil {
		t.Fatal(err)
	}
	var raw map[string]any
	if err := ReadJSON(o.Path("fences.json"), &raw); err != nil || raw["schema_version"].(float64) != 1 {
		t.Fatalf("envoltorio schema_version: %v %v", err, raw)
	}
}

// Los logs append-only también se dividen por tipo, mismo motivo.

func TestAppendEventYRecentEvents(t *testing.T) {
	o := org(t)
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		if err := o.AppendEvent(transition.Transition{At: at, DeviceID: "dev-1", From: "none:unknown", To: "demo-hq:inside"}); err != nil {
			t.Fatal(err)
		}
	}
	evs, err := o.RecentEvents(2)
	if err != nil || len(evs) != 2 || evs[0].To != "demo-hq:inside" || !evs[0].At.Equal(at) {
		t.Fatalf("events: %v %+v", err, evs)
	}
}

func TestAppendActionYRecentActions(t *testing.T) {
	o := org(t)
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	if err := o.AppendAction(action.Result{Adapter: "simulation", OK: true, DeviceID: "dev-1", Action: action.Message, DryRun: true, At: at}); err != nil {
		t.Fatal(err)
	}
	acts, _ := o.RecentActions(10)
	if len(acts) != 1 || acts[0].Action != action.Message || !acts[0].DryRun {
		t.Fatalf("actions: %+v", acts)
	}
}

func TestAppendTrailFiltraPorDispositivoYLimita(t *testing.T) {
	o := org(t)
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		_ = o.AppendTrail("dev-1", geo.Point{Lat: float64(i)}, at.Add(time.Duration(i)*time.Minute))
	}
	_ = o.AppendTrail("dev-2", geo.Point{Lat: 9}, at)
	tr, _ := o.Trail("dev-1", 2)
	if len(tr) != 2 || tr[0].Point.Lat != 1 || tr[1].Point.Lat != 2 {
		t.Fatalf("trail: %+v", tr)
	}
}

func TestAppendStatsYRecentStats(t *testing.T) {
	o := org(t)
	_ = o.AppendStats(map[string]int{"devices_total": 6})
	st, _ := o.RecentStats(5)
	if len(st) != 1 {
		t.Fatal("stats")
	}
}
