package incident

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
)

var t0 = time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)

func sample(id string, status Status) Incident {
	return Incident{
		ID: id, DeviceID: "dev-1", DeviceName: "Tablet", Kind: KindGeofenceExit,
		Severity: "high", Title: "Fuera de geocerca", Recommendation: "Revisar",
		Status: status, Count: 1, Evidence: []string{"fence_state=outside"},
		OpenedAt: t0, UpdatedAt: t0, Timeline: []Entry{},
	}
}

func TestMergeAbreLosNuevosYRefrescaLosHechos(t *testing.T) {
	merged, opened, closed := Merge(nil, []Incident{sample("inc-a", StatusOpen)}, t0)
	if len(merged) != 1 || len(opened) != 1 || len(closed) != 0 {
		t.Fatalf("primera derivación: %d merged, %d opened, %d closed", len(merged), len(opened), len(closed))
	}
	if merged[0].Status != StatusOpen || merged[0].Count != 1 || !merged[0].OpenedAt.Equal(t0) {
		t.Fatalf("estado inicial: %+v", merged[0])
	}

	later := t0.Add(15 * time.Minute)
	next := sample("inc-a", StatusOpen)
	next.Severity = "critical"
	next.Evidence = []string{"fence_state=outside", "compliant=false"}
	merged2, opened2, closed2 := Merge(merged, []Incident{next}, later)
	if len(opened2) != 0 || len(closed2) != 0 {
		t.Fatalf("un incidente ya conocido no se vuelve a abrir: %d abiertos, %d cerrados", len(opened2), len(closed2))
	}
	got := merged2[0]
	if got.Severity != "critical" || len(got.Evidence) != 2 {
		t.Fatalf("los hechos derivados se refrescan: %+v", got)
	}
	if got.Count != 2 || !got.UpdatedAt.Equal(later) || !got.OpenedAt.Equal(t0) {
		t.Fatalf("contador de observaciones y marcas: %+v", got)
	}
}

func TestMergeConservaElCerradoAunqueLaCondicionSeVuelvaADerivar(t *testing.T) {
	merged, _, _ := Merge(nil, []Incident{sample("inc-a", StatusOpen)}, t0)
	resolved, err := merged[0].Transition(StatusClosed, "soc", "", "dispositivo recuperado", t0.Add(time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	again, opened, closed := Merge([]Incident{resolved}, []Incident{sample("inc-a", StatusOpen)}, t0.Add(2*time.Hour))
	if len(opened) != 0 || len(closed) != 0 {
		t.Fatalf("un cerrado no se reabre solo: %d abiertos, %d cerrados", len(opened), len(closed))
	}
	if again[0].Status != StatusClosed || again[0].ClosedAt == nil {
		t.Fatalf("sigue cerrado: %+v", again[0])
	}
	if len(again[0].Timeline) != 1 || again[0].Timeline[0].Actor != "soc" {
		t.Fatalf("la auditoría se conserva: %+v", again[0].Timeline)
	}
}

func TestMergeReabreLoQueElCicloHabiaCerradoCuandoLaCondicionVuelve(t *testing.T) {
	// Ciclo 1: la condición aparece y abre.
	primero, _, _ := Merge(nil, []Incident{sample("inc-a", StatusOpen)}, t0)
	// Ciclo 2: deja de observarse y el ciclo la cierra solo.
	segundo, _, cerrados := Merge(primero, nil, t0.Add(15*time.Minute))
	if len(cerrados) != 1 || segundo[0].Status != StatusClosed {
		t.Fatalf("el ciclo 2 cierra solo: %d cerrados, %+v", len(cerrados), segundo[0])
	}
	// Ciclo 3: vuelve a derivarse. Sin reapertura este par (dispositivo, tipo)
	// se quedaría mudo para siempre: el id es determinista y no caduca.
	vuelta := t0.Add(30 * time.Minute)
	tercero, abiertos, cerrados3 := Merge(segundo, []Incident{sample("inc-a", StatusOpen)}, vuelta)
	if len(abiertos) != 1 || abiertos[0].ID != "inc-a" || len(cerrados3) != 0 {
		t.Fatalf("la condición que vuelve reabre y se anuncia: %d abiertos, %d cerrados", len(abiertos), len(cerrados3))
	}
	got := tercero[0]
	if got.Status != StatusOpen || got.ClosedAt != nil || !got.OpenedAt.Equal(vuelta) || got.Count != 2 {
		t.Fatalf("reapertura: %+v", got)
	}
	last := got.Timeline[len(got.Timeline)-1]
	if len(got.Timeline) != 2 || last.Actor != ActorSystem || last.From != "closed" || last.To != "open" || last.Note == "" {
		t.Fatalf("la reapertura queda firmada por el sistema y conserva la auditoría: %+v", got.Timeline)
	}
}

func TestMergeCierraElAbiertoCuyaCondicionDesaparece(t *testing.T) {
	merged, _, _ := Merge(nil, []Incident{sample("inc-a", StatusOpen), sample("inc-b", StatusOpen)}, t0)
	later := t0.Add(30 * time.Minute)
	after, opened, closed := Merge(merged, []Incident{sample("inc-a", StatusOpen)}, later)
	if len(opened) != 0 || len(closed) != 1 || closed[0].ID != "inc-b" {
		t.Fatalf("solo inc-b se cierra: %d abiertos, cerrados %+v", len(opened), closed)
	}
	got, ok := FindByID(after, "inc-b")
	if !ok || got.Status != StatusClosed || got.ClosedAt == nil || !got.ClosedAt.Equal(later) {
		t.Fatalf("cierre automático: %+v", got)
	}
	last := got.Timeline[len(got.Timeline)-1]
	if last.Actor != ActorSystem || last.From != "open" || last.To != "closed" || last.Note == "" {
		t.Fatalf("entrada de auditoría del cierre automático: %+v", last)
	}
	if _, ok := FindByID(after, "inc-a"); !ok {
		t.Fatal("inc-a sigue vivo")
	}
}

func TestTransitionRechazaEstadoInvalidoYRepetido(t *testing.T) {
	inc := sample("inc-a", StatusOpen)
	if _, err := inc.Transition("resuelto", "soc", "", "", t0); !errors.Is(err, ErrInvalidStatus) {
		t.Fatalf("estado inventado: %v", err)
	}
	if _, err := inc.Transition(StatusOpen, "soc", "", "", t0); !errors.Is(err, ErrSameStatus) {
		t.Fatalf("transición al mismo estado: %v", err)
	}
}

func TestTransitionReconoceSinMutarElOriginal(t *testing.T) {
	inc := sample("inc-a", StatusOpen)
	ackAt := t0.Add(5 * time.Minute)
	acked, err := inc.Transition(StatusAck, "usr-1", " soc@acme.test ", " Investigando ", ackAt)
	if err != nil {
		t.Fatal(err)
	}
	if acked.AckedAt == nil || !acked.AckedAt.Equal(ackAt) || acked.ClosedAt != nil {
		t.Fatalf("sellos del reconocimiento: %+v", acked)
	}
	if acked.Assignee != "soc@acme.test" {
		t.Fatalf("asignado sin espacios sobrantes: %q", acked.Assignee)
	}
	entry := acked.Timeline[0]
	if entry.From != "open" || entry.To != "ack" || entry.Actor != "usr-1" || entry.Note != "Investigando" {
		t.Fatalf("auditoría: %+v", entry)
	}
	if len(inc.Timeline) != 0 {
		t.Fatal("Transition no puede mutar el incidente original")
	}
}

func TestTransitionCierraYLaReaperturaLimpiaLosSellos(t *testing.T) {
	acked, err := sample("inc-a", StatusOpen).
		Transition(StatusAck, "usr-1", "soc@acme.test", "Investigando", t0.Add(5*time.Minute))
	if err != nil {
		t.Fatal(err)
	}
	closedAt := t0.Add(time.Hour)
	done, err := acked.Transition(StatusClosed, "usr-2", "", "", closedAt)
	if err != nil {
		t.Fatal(err)
	}
	if done.ClosedAt == nil || !done.ClosedAt.Equal(closedAt) || done.AckedAt == nil {
		t.Fatalf("sellos del cierre: %+v", done)
	}
	if done.Assignee != "soc@acme.test" || len(done.Timeline) != 2 {
		t.Fatalf("el cierre conserva asignación y auditoría: %+v", done)
	}

	reopened, err := done.Transition(StatusOpen, "usr-2", "", "reincidencia", closedAt.Add(time.Minute))
	if err != nil {
		t.Fatal(err)
	}
	if reopened.ClosedAt != nil || reopened.AckedAt != nil || len(reopened.Timeline) != 3 {
		t.Fatalf("la reapertura limpia los dos sellos: %+v", reopened)
	}
}

func TestOrdenEstableYFindByID(t *testing.T) {
	crit := sample("inc-crit", StatusOpen)
	crit.Severity, crit.Title = "critical", "Zeta"
	low := sample("inc-low", StatusOpen)
	low.Severity, low.Title = "low", "Alfa"
	unknown := sample("inc-unknown", StatusOpen)
	unknown.Severity = "unknown"
	weird := sample("inc-weird", StatusOpen)
	weird.Severity = "urgentísima"
	done := sample("inc-done", StatusClosed)
	done.Severity = "critical"

	merged, _, _ := Merge([]Incident{done}, []Incident{low, weird, unknown, crit, done}, t0)
	ids := make([]string, 0, len(merged))
	for _, inc := range merged {
		ids = append(ids, inc.ID)
	}
	want := "inc-crit,inc-low,inc-unknown,inc-weird,inc-done"
	if strings.Join(ids, ",") != want {
		t.Fatalf("orden por estado, severidad, título e id: %s want %s", strings.Join(ids, ","), want)
	}
	if _, ok := FindByID(merged, "inc-nope"); ok {
		t.Fatal("id inexistente")
	}
}

func TestJSONEnSnakeCase(t *testing.T) {
	inc := sample("inc-a", StatusOpen)
	score := 91.5
	inc.RiskScore = &score
	b, err := json.Marshal(inc)
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	for _, want := range []string{
		`"device_id":"dev-1"`, `"device_name":"Tablet"`, `"risk_score":91.5`,
		`"opened_at":"2026-09-06T10:00:00Z"`, `"timeline":[]`,
		`"evidence":["fence_state=outside"]`, `"status":"open"`,
	} {
		if !strings.Contains(s, want) {
			t.Fatalf("JSON %s sin %s", s, want)
		}
	}
	if strings.Contains(s, "acked_at") || strings.Contains(s, "closed_at") {
		t.Fatalf("las marcas nulas se omiten: %s", s)
	}
}
