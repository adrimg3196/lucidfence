package engine

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
)

func TestSeedDemoIdempotente(t *testing.T) {
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Now()
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	fs, _ := org.Fences()
	rs, _ := org.Routes()
	ps, _ := org.POIs()
	if len(fs) != 2 || fs[0].ID != "demo-hq" || fs[1].ID != "warehouse-poly" || len(rs) != 1 || len(ps) != 2 {
		t.Fatalf("demo: %d fences %d routes %d pois", len(fs), len(rs), len(ps))
	}
	_ = org.SaveFences(fs[:1])
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	if fs, _ = org.Fences(); len(fs) != 1 {
		t.Fatal("no debe sobrescribir geocercas existentes")
	}
}

// TestSeedDemoSiembraLaAutomatizacion: el modo demo arranca con riesgo y
// automatización visibles, no solo con datos.
func TestSeedDemoSiembraLaAutomatizacion(t *testing.T) {
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	t.Run("políticas", func(t *testing.T) { assertPoliticasDeLaDemo(t, org, now) })
	t.Run("alerta", func(t *testing.T) { assertAlertaDeLaDemo(t, org) })
	t.Run("ajustes", func(t *testing.T) { assertAjustesDeLaDemo(t, org) })
	t.Run("postura", func(t *testing.T) { assertPosturaDeLaSeed(t, org) })
}

func assertPoliticasDeLaDemo(t *testing.T, org *store.OrgStore, now time.Time) {
	t.Helper()
	ps, err := org.Policies()
	if err != nil {
		t.Fatal(err)
	}
	if len(ps) != 2 || ps[0].ID != "tpl-block-on-route-exit" || ps[1].ID != "tpl-locate-unknown-noncompliant" {
		t.Fatalf("dos plantillas activadas, en el orden del catálogo: %+v", ps)
	}
	for _, p := range ps {
		if !p.Enabled || p.Source != "template" || !p.CreatedAt.Equal(now) || !p.UpdatedAt.Equal(now) {
			t.Fatalf("la política demo nace activada y sellada: %+v", p)
		}
		if err := p.Validate(); err != nil {
			t.Fatalf("la política demo debe ser válida: %v", err)
		}
	}
}

func assertAlertaDeLaDemo(t *testing.T, org *store.OrgStore) {
	t.Helper()
	rs, err := org.Alerts()
	if err != nil {
		t.Fatal(err)
	}
	if len(rs) != 1 || rs[0].ID != "alert-riesgo-alto" || rs[0].Kind != alert.KindRiskAbove || rs[0].Threshold != 70 {
		t.Fatalf("una regla de riesgo alto: %+v", rs)
	}
	if !rs[0].Enabled {
		t.Fatalf("la regla demo nace activada: %+v", rs[0])
	}
}

func assertAjustesDeLaDemo(t *testing.T, org *store.OrgStore) {
	t.Helper()
	set, err := org.Settings()
	if err != nil {
		t.Fatal(err)
	}
	if set.Enforcement.Mode != settings.ModeObserve || set.Risk.OffHoursStart != 20 || set.Risk.OffHoursEnd != 7 {
		t.Fatalf("la demo arranca en observe con la jornada de fábrica: %+v", set)
	}
	// Sin contexto sembrado, zone_risk y shift_match serían siempre neutras
	// fuera de los tests: el bloque risk no tiene PUT propio en M2.
	if set.Risk.ZoneRisk["warehouse-poly"] != 0.5 || set.Risk.ShiftZones["dev-004"] != "demo-hq" {
		t.Fatalf("la demo siembra el contexto de riesgo: %+v", set.Risk)
	}
}

// assertPosturaDeLaSeed comprueba las tres posturas que la demo distingue:
// comprometida, sana explícita y desconocida.
func assertPosturaDeLaSeed(t *testing.T, org *store.OrgStore) {
	t.Helper()
	sd, err := simulation.LoadSeed(org.Path("seed.json"))
	if err != nil {
		t.Fatal(err)
	}
	post := map[string]device.Posture{}
	for _, d := range sd.Devices {
		post[d.ID] = d.Posture
	}
	assertPosturaComprometida(t, post["dev-004"])
	sana := post["dev-006"]
	if sana.Rooted == nil || *sana.Rooted || sana.OsqueryConfigValid == nil || !*sana.OsqueryConfigValid {
		t.Fatalf("dev-006 acredita una postura sana explícita: %+v", sana)
	}
	// dev-001 se queda sin postura a propósito: es el dispositivo del check
	// checkPostureUnknown de la batería M1, que exige posture:{} en la API.
	// device.Posture lleva un mapa, así que no se compara con ==.
	if u := post["dev-001"]; u.Rooted != nil || u.OSOutdated != nil || u.OsqueryConfigValid != nil || u.HardwareHealth != nil {
		t.Fatalf("dev-001 conserva la postura desconocida: %+v", u)
	}
}

func assertPosturaComprometida(t *testing.T, p device.Posture) {
	t.Helper()
	if p.Rooted == nil || !*p.Rooted || p.OSOutdated == nil || !*p.OSOutdated {
		t.Fatalf("dev-004 trae la postura comprometida de la demo: %+v", p)
	}
	if p.OsqueryConfigValid == nil || *p.OsqueryConfigValid {
		t.Fatalf("dev-004 tiene la configuración de osquery inválida: %+v", p)
	}
}

// TestSeedDemoNoResiembraLaAutomatizacion: SeedDemo nunca pisa lo que el
// operador ya tiene. Una colección vacía sí cuenta como "no hay nada", igual
// que en M1 con geocercas, rutas y POIs.
func TestSeedDemoNoResiembraLaAutomatizacion(t *testing.T) {
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	ps, _ := org.Policies()
	if err := org.SavePolicies(ps[:1]); err != nil {
		t.Fatal(err)
	}
	if err := org.SaveAlerts(nil); err != nil {
		t.Fatal(err)
	}
	set, _ := org.Settings()
	set.Enforcement.Mode = settings.ModeEnforce
	set.Risk.ZoneRisk = map[string]float64{"demo-hq": 0.9}
	set.Risk.ShiftZones = map[string]string{}
	if err := org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	if ps, _ = org.Policies(); len(ps) != 1 {
		t.Fatalf("no debe re-sembrar sobre políticas existentes: %+v", ps)
	}
	rs, _ := org.Alerts()
	if len(rs) != 1 || rs[0].ID != "alert-riesgo-alto" {
		t.Fatalf("un alerts.json vacío equivale a no tener nada: %+v", rs)
	}
	set, _ = org.Settings()
	if set.Enforcement.Mode != settings.ModeEnforce {
		t.Fatal("SeedDemo no puede devolver el motor a observe")
	}
	// El contexto de riesgo del operador manda: un zone_risk configurado
	// (aunque las zonas no sean las de la demo) impide la resiembra.
	if set.Risk.ZoneRisk["demo-hq"] != 0.9 || len(set.Risk.ZoneRisk) != 1 || len(set.Risk.ShiftZones) != 0 {
		t.Fatalf("SeedDemo no puede pisar el contexto de riesgo del operador: %+v", set.Risk)
	}
}
