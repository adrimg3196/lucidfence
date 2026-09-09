package store

import (
	"os"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

func TestPoliciesVaciasYRoundTrip(t *testing.T) {
	o := org(t)
	ps, err := o.Policies()
	if err != nil || len(ps) != 0 {
		t.Fatalf("sin fichero → lista vacía, nunca error: %v %v", err, ps)
	}
	want := []policy.Policy{{ID: "pol-riesgo", Name: "Riesgo alto", Enabled: true, Severity: "high",
		When:    []policy.Condition{{Field: "risk_score", Op: policy.OpGte, Value: 80.0}},
		Actions: []policy.Action{{Action: action.Notify, Params: map[string]any{"channel": "security"}}}}}
	if err := o.SavePolicies(want); err != nil {
		t.Fatal(err)
	}
	got, err := o.Policies()
	if err != nil || len(got) != 1 || got[0].ID != "pol-riesgo" || got[0].When[0].Op != policy.OpGte {
		t.Fatalf("policies: %v %+v", err, got)
	}
}

func TestPlaybooksVaciosYRoundTrip(t *testing.T) {
	o := org(t)
	if ps, err := o.Playbooks(); err != nil || len(ps) != 0 {
		t.Fatalf("sin fichero → vacío: %v %v", err, ps)
	}
	if err := o.SavePlaybooks([]playbook.Playbook{{ID: "pb-1", Name: "Aislar", Enabled: true, Severity: "high"}}); err != nil {
		t.Fatal(err)
	}
	if ps, _ := o.Playbooks(); len(ps) != 1 || ps[0].ID != "pb-1" {
		t.Fatalf("playbooks: %+v", ps)
	}
}

func TestAlertsVaciasYRoundTrip(t *testing.T) {
	o := org(t)
	if rs, err := o.Alerts(); err != nil || len(rs) != 0 {
		t.Fatalf("sin fichero → vacío: %v %v", err, rs)
	}
	rule := alert.Rule{ID: "al-1", Name: "Batería baja", Kind: alert.KindBatteryBelow,
		Threshold: 15, Severity: "medium", Enabled: true}
	if err := o.SaveAlerts([]alert.Rule{rule}); err != nil {
		t.Fatal(err)
	}
	if rs, _ := o.Alerts(); len(rs) != 1 || rs[0].Kind != alert.KindBatteryBelow || rs[0].Threshold != 15 {
		t.Fatalf("alerts: %+v", rs)
	}
}

func TestIncidentsVaciosYRoundTrip(t *testing.T) {
	o := org(t)
	if is, err := o.Incidents(); err != nil || len(is) != 0 {
		t.Fatalf("sin fichero → vacío: %v %v", err, is)
	}
	at := time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)
	in := incident.Incident{ID: "inc-1", DeviceID: "dev-1", Kind: incident.KindGeofenceExit,
		Severity: "high", Status: incident.StatusOpen, Count: 1, OpenedAt: at, UpdatedAt: at,
		Timeline: []incident.Entry{{At: at, Actor: "engine", To: "open"}}}
	if err := o.SaveIncidents([]incident.Incident{in}); err != nil {
		t.Fatal(err)
	}
	got, _ := o.Incidents()
	if len(got) != 1 || got[0].Status != incident.StatusOpen || !got[0].OpenedAt.Equal(at) || len(got[0].Timeline) != 1 {
		t.Fatalf("incidents: %+v", got)
	}
	if got[0].ClosedAt != nil {
		t.Fatalf("un puntero ausente debe seguir siendo nil tras el round-trip: %+v", got[0])
	}
}

func TestHandoffsVaciosYRoundTrip(t *testing.T) {
	o := org(t)
	if hs, err := o.Handoffs(); err != nil || len(hs) != 0 {
		t.Fatalf("sin fichero → vacío: %v %v", err, hs)
	}
	h := playbook.Handoff{ID: "ho-dev-1-pb-1-lock", DeviceID: "dev-1", PlaybookID: "pb-1",
		Action: action.Lock, Status: playbook.HandoffPending,
		RequestedAt: time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)}
	if err := o.SaveHandoffs([]playbook.Handoff{h}); err != nil {
		t.Fatal(err)
	}
	got, _ := o.Handoffs()
	if len(got) != 1 || got[0].Status != playbook.HandoffPending || got[0].DecidedAt != nil {
		t.Fatalf("handoffs: %+v", got)
	}
}

func TestColeccionesDeM2LlevanSchemaVersion1(t *testing.T) {
	o := org(t)
	if err := o.SavePolicies([]policy.Policy{{ID: "p"}}); err != nil {
		t.Fatal(err)
	}
	if err := o.SavePlaybooks([]playbook.Playbook{{ID: "b"}}); err != nil {
		t.Fatal(err)
	}
	if err := o.SaveAlerts([]alert.Rule{{ID: "a"}}); err != nil {
		t.Fatal(err)
	}
	if err := o.SaveIncidents([]incident.Incident{{ID: "i"}}); err != nil {
		t.Fatal(err)
	}
	if err := o.SaveHandoffs([]playbook.Handoff{{ID: "h"}}); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"policies.json", "playbooks.json", "alerts.json", "incidents.json", "handoffs.json"} {
		var raw map[string]any
		if err := ReadJSON(o.Path(name), &raw); err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if raw["schema_version"] != float64(1) {
			t.Fatalf("%s: schema_version %v", name, raw["schema_version"])
		}
	}
}

func TestGuardarListaNilEscribeListaVacia(t *testing.T) {
	o := org(t)
	if err := o.SaveIncidents(nil); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(o.Path("incidents.json"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "null") {
		t.Fatalf("items nunca puede serializarse como null: %s", raw)
	}
	if is, err := o.Incidents(); err != nil || len(is) != 0 {
		t.Fatalf("releer: %v %+v", err, is)
	}
}

func TestSavePoliciesNoPierdeElFicheroPrevioSiFallaLaSerializacion(t *testing.T) {
	o := org(t)
	if err := o.SavePolicies([]policy.Policy{{ID: "buena"}}); err != nil {
		t.Fatal(err)
	}
	roto := []policy.Policy{{ID: "rota", Actions: []policy.Action{{Action: action.Notify,
		Params: map[string]any{"canal": make(chan int)}}}}}
	if err := o.SavePolicies(roto); err == nil {
		t.Fatal("un valor no serializable debe fallar antes del rename")
	}
	got, err := o.Policies()
	if err != nil || len(got) != 1 || got[0].ID != "buena" {
		t.Fatalf("el fichero previo debe seguir intacto: %v %+v", err, got)
	}
	entries, _ := os.ReadDir(o.Dir())
	if len(entries) != 1 {
		t.Fatalf("no deben quedar temporales: %v", entries)
	}
}

func TestPermisosDeLasColeccionesDeM2(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("permisos POSIX")
	}
	o := org(t)
	if err := o.SavePolicies([]policy.Policy{{ID: "p"}}); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Stat(o.Path("policies.json"))
	if err != nil || fi.Mode().Perm() != 0o600 {
		t.Fatalf("policies.json: %v %o", err, fi.Mode().Perm())
	}
	di, err := os.Stat(o.Dir())
	if err != nil || di.Mode().Perm() != 0o700 {
		t.Fatalf("directorio de la org: %v %o", err, di.Mode().Perm())
	}
}

func TestSettingsRoundTripYValidacion(t *testing.T) {
	o := org(t)
	s, err := o.Settings()
	if err != nil || s.Enforcement.Mode != settings.ModeObserve {
		t.Fatalf("primera lectura: %v %+v", err, s.Enforcement)
	}
	s.Enforcement.Mode = settings.ModeEnforce
	s.Enforcement.LiveActions = []action.Action{action.Message}
	s.UpdatedAt = time.Date(2026, 9, 6, 11, 0, 0, 0, time.UTC)
	if err := o.SaveSettings(s); err != nil {
		t.Fatal(err)
	}
	back, err := o.Settings()
	if err != nil || back.Enforcement.Mode != settings.ModeEnforce || len(back.Enforcement.LiveActions) != 1 {
		t.Fatalf("round-trip: %v %+v", err, back.Enforcement)
	}
	if !back.UpdatedAt.Equal(s.UpdatedAt) {
		t.Fatalf("updated_at se guarda tal cual llega: %v", back.UpdatedAt)
	}
	s.Enforcement.Mode = "paranoico"
	if err := o.SaveSettings(s); err == nil {
		t.Fatal("SaveSettings debe rechazar unos ajustes inválidos")
	}
	if again, _ := o.Settings(); again.Enforcement.Mode != settings.ModeEnforce {
		t.Fatal("el rechazo no puede haber tocado el fichero")
	}
}

func TestSettingsCorruptoNoSeReSiembraEncima(t *testing.T) {
	o := org(t)
	if err := os.WriteFile(o.Path("settings.json"), []byte("{esto no es json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := o.Settings(); err == nil {
		t.Fatal("un settings.json corrupto es un error, no una excusa para volver a los valores de fábrica")
	}
	raw, err := os.ReadFile(o.Path("settings.json"))
	if err != nil || !strings.Contains(string(raw), "esto no es json") {
		t.Fatalf("el fichero del operador no puede sobrescribirse: %v %s", err, raw)
	}
}

func TestEscriturasConcurrentesDesde20Goroutines(t *testing.T) {
	o := org(t)
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			switch i % 4 {
			case 0:
				_ = o.SavePolicies([]policy.Policy{{ID: "p"}})
			case 1:
				_ = o.SaveIncidents([]incident.Incident{{ID: "i"}})
			case 2:
				s, _ := o.Settings()
				_ = o.SaveSettings(s)
			case 3:
				_, _ = o.Handoffs()
			}
		}(i)
	}
	wg.Wait()
	if ps, err := o.Policies(); err != nil || len(ps) != 1 {
		t.Fatalf("tras la concurrencia el fichero debe seguir siendo legible: %v %+v", err, ps)
	}
	if s, err := o.Settings(); err != nil || s.SchemaVersion != settings.SchemaVersion {
		t.Fatalf("settings tras la concurrencia: %v %+v", err, s)
	}
}
