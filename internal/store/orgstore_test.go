package store

import (
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
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

func orgConEgress(t *testing.T, hosts []string, allowPrivate bool) *OrgStore {
	t.Helper()
	s, err := Open(t.TempDir(), WithDefaultEgress(settings.Egress{Hosts: hosts, AllowPrivate: allowPrivate}))
	if err != nil {
		t.Fatal(err)
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	return o
}

func TestSettingsSiembraEgressDesdeConfigSoloLaPrimeraVez(t *testing.T) {
	o := orgConEgress(t, []string{"SIEM.example.com", "ntfy.sh"}, true)
	first, err := o.Settings()
	if err != nil {
		t.Fatal(err)
	}
	if len(first.Egress.Hosts) != 2 || first.Egress.Hosts[0] != "siem.example.com" || !first.Egress.AllowPrivate {
		t.Fatalf("la primera lectura siembra egress desde config: %+v", first.Egress)
	}
	if _, err := os.Stat(o.Path("settings.json")); err != nil {
		t.Fatalf("la siembra debe dejar el fichero escrito: %v", err)
	}
	// A partir de aquí manda settings.json, no config.json.
	first.Egress = settings.Egress{Hosts: []string{"solo.example.com"}, AllowPrivate: false}
	if err := o.SaveSettings(first); err != nil {
		t.Fatal(err)
	}
	second, err := o.Settings()
	if err != nil {
		t.Fatal(err)
	}
	if len(second.Egress.Hosts) != 1 || second.Egress.Hosts[0] != "solo.example.com" || second.Egress.AllowPrivate {
		t.Fatalf("la segunda lectura no vuelve a sembrar: %+v", second.Egress)
	}
}

func TestSinOpcionDeEgressLaSiembraEsVacia(t *testing.T) {
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	set, err := o.Settings()
	if err != nil {
		t.Fatal(err)
	}
	if set.Egress.Hosts == nil || len(set.Egress.Hosts) != 0 || set.Egress.AllowPrivate {
		t.Fatalf("sin opción: allowlist vacía y no nil, sin redes privadas: %+v", set.Egress)
	}
}

// El histórico global es lo que consume el simulador what-if del motor (Task
// 17): TrailAll no puede caerse por una línea corrupta, no puede devolver el
// fichero entero y respeta el orden de escritura, que es el cronológico.

func escribirTrail(t *testing.T, o *OrgStore, lineas ...string) {
	t.Helper()
	if err := os.WriteFile(o.Path("trail.jsonl"), []byte(strings.Join(lineas, "\n")+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
}

func TestTrailAllDevuelveElHistoricoDeTodaLaFlotaEnOrden(t *testing.T) {
	o := org(t)
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	_ = o.AppendTrail("dev-1", geo.Point{Lat: 40.42, Lng: -3.70}, at)
	_ = o.AppendTrail("dev-2", geo.Point{Lat: 41.38, Lng: 2.17}, at.Add(time.Minute))
	_ = o.AppendTrail("dev-1", geo.Point{Lat: 40.43, Lng: -3.71}, at.Add(2*time.Minute))
	got, err := o.TrailAll(0)
	if err != nil || len(got) != 3 {
		t.Fatalf("histórico global: %v %+v", err, got)
	}
	if got[0].DeviceID != "dev-1" || got[1].DeviceID != "dev-2" || got[2].DeviceID != "dev-1" {
		t.Fatalf("el orden del fichero es el cronológico: %+v", got)
	}
	if !got[2].At.Equal(at.Add(2*time.Minute)) || got[1].Point.Lng != 2.17 {
		t.Fatalf("punto mal decodificado: %+v", got[2])
	}
}

func TestTrailAllSaltaLoQueNoSePuedeSimular(t *testing.T) {
	o := org(t)
	escribirTrail(t, o,
		`{"device_id":"dev-1","at":"2026-09-05T12:00:00Z","point":{"lat":40.42,"lng":-3.7}}`,
		`{corrupto`,
		`{"device_id":"","at":"2026-09-05T12:01:00Z","point":{"lat":40.42,"lng":-3.7}}`,
		`{"device_id":"dev-2","at":"2026-09-05T12:02:00Z"}`,
		`{"device_id":"dev-3","at":"2026-09-05T12:03:00Z","point":{"lat":91,"lng":-3.7}}`,
		`{"device_id":"dev-4","point":{"lat":40.42,"lng":-3.7}}`,
		`{"device_id":"dev-5","at":"2026-09-05T12:05:00Z","point":{"lat":40.5,"lng":-3.7}}`,
	)
	got, err := o.TrailAll(0)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0].DeviceID != "dev-1" || got[1].DeviceID != "dev-5" {
		t.Fatalf("corrupta, sin dispositivo, sin punto, con punto imposible y sin instante fuera: %+v", got)
	}
}

func TestTrailAllAplicaElLimiteYElTechoDuro(t *testing.T) {
	o := org(t)
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	lineas := make([]string, 0, MaxTrailPoints+10)
	for i := 0; i < MaxTrailPoints+10; i++ {
		lineas = append(lineas, fmt.Sprintf(`{"device_id":"dev-1","at":%q,"point":{"lat":40.42,"lng":-3.7}}`,
			at.Add(time.Duration(i)*time.Second).Format(time.RFC3339)))
	}
	escribirTrail(t, o, lineas...)
	ultimo := at.Add(time.Duration(MaxTrailPoints+9) * time.Second)

	todos, err := o.TrailAll(0)
	if err != nil || len(todos) != MaxTrailPoints {
		t.Fatalf("sin límite manda el techo duro: %v %d", err, len(todos))
	}
	if !todos[len(todos)-1].At.Equal(ultimo) {
		t.Fatalf("el techo se queda con los últimos puntos, no con los primeros: %v", todos[len(todos)-1].At)
	}
	tres, _ := o.TrailAll(3)
	if len(tres) != 3 || !tres[2].At.Equal(ultimo) {
		t.Fatalf("límite de 3: %+v", tres)
	}
	excesivo, _ := o.TrailAll(MaxTrailPoints * 2)
	if len(excesivo) != MaxTrailPoints {
		t.Fatalf("un límite por encima del techo cae al techo: %d", len(excesivo))
	}
}

func TestTrailAllSinFicheroDevuelveVacioNoError(t *testing.T) {
	o := org(t)
	got, err := o.TrailAll(0)
	if err != nil || len(got) != 0 {
		t.Fatalf("sin trail.jsonl: %v %+v", err, got)
	}
}

func TestTrailNoSeCaePorUnaLineaCorrupta(t *testing.T) {
	o := org(t)
	escribirTrail(t, o,
		`{"device_id":"dev-1","at":"2026-09-05T12:00:00Z","point":{"lat":1,"lng":1}}`,
		`{corrupto`,
		`{"device_id":"dev-1","at":"2026-09-05T12:01:00Z","point":{"lat":2,"lng":1}}`,
	)
	tr, err := o.Trail("dev-1", 10)
	if err != nil || len(tr) != 2 || tr[1].Point.Lat != 2 {
		t.Fatalf("el detalle de un dispositivo tampoco se cae: %v %+v", err, tr)
	}
}
