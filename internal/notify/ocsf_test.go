package notify

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/google/go-cmp/cmp"
)

func handoffPendiente() *playbook.Handoff {
	return &playbook.Handoff{
		ID: "ho-dev-7-pb-cuarentena-lock", DeviceID: "dev-7", DeviceName: "Tablet almacén",
		PlaybookID: "pb-cuarentena", PlaybookName: "Cuarentena de dispositivo en riesgo",
		Action: action.Lock, Severity: "critical", Status: playbook.HandoffPending,
		Reason:      "risk_score gte 80; fence_state eq outside",
		RequestedAt: time.Date(2026, 8, 29, 9, 31, 0, 0, time.UTC),
	}
}

func eventosDorados() map[string]Event {
	cerrado := incidenteAbierto()
	cerrado.Status = incident.StatusClosed
	cerrado.Count = 4
	cerrado.UpdatedAt = time.Date(2026, 8, 29, 10, 15, 0, 0, time.UTC)

	reabierto := incidenteAbierto()
	reabierto.Status = ""

	return map[string]Event{
		"incidente_abierto": eventoAbierto(),
		"handoff_pendiente": {
			Kind: EventHandoffPending, At: time.Date(2026, 8, 29, 9, 31, 0, 0, time.UTC),
			DeliveryID: "dlv-0002", Handoff: handoffPendiente(),
		},
		"incidente_cerrado": {
			Kind: EventIncidentClosed, At: time.Date(2026, 8, 29, 10, 15, 0, 0, time.UTC),
			DeliveryID: "dlv-0003", Incident: cerrado,
		},
		"transicion_desconocida": {
			Kind: "incident.reopened", At: time.Date(2026, 8, 29, 10, 20, 0, 0, time.UTC),
			DeliveryID: "dlv-0004", Incident: reabierto,
		},
	}
}

// normalizar pasa el mapa por JSON para que los enteros de Go y los números del
// fichero dorado se comparen como el mismo float64.
func normalizar(t *testing.T, v any) map[string]any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

func TestDetectionFindingCoincideConElFicheroDorado(t *testing.T) {
	raw, err := os.ReadFile("testdata/ocsf_golden.json")
	if err != nil {
		t.Fatalf("leer fichero dorado: %v", err)
	}
	var dorado map[string]map[string]any
	if err := json.Unmarshal(raw, &dorado); err != nil {
		t.Fatalf("fichero dorado inválido: %v", err)
	}
	eventos := eventosDorados()
	if len(dorado) != len(eventos) {
		t.Fatalf("el fichero dorado tiene %d casos y el test %d", len(dorado), len(eventos))
	}
	for nombre, ev := range eventos {
		quiero, hay := dorado[nombre]
		if !hay {
			t.Fatalf("falta el caso %q en el fichero dorado", nombre)
		}
		got := normalizar(t, DetectionFinding(ev))
		if diff := cmp.Diff(quiero, got); diff != "" {
			t.Fatalf("caso %q (-dorado +obtenido):\n%s", nombre, diff)
		}
	}
}

func TestSeverityIDDesconocidaEsCeroNuncaUno(t *testing.T) {
	casos := map[string]int{
		"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5,
		"HIGH": 4, "  Critical  ": 5,
		"unknown": 0, "": 0, "   ": 0, "fatal": 0, "severa": 0,
	}
	for entrada, quiero := range casos {
		if got := SeverityID(entrada); got != quiero {
			t.Fatalf("SeverityID(%q) = %d, esperado %d", entrada, got, quiero)
		}
	}
	// El evento sin ninguna fuente que declare severidad tampoco es benigno.
	ev := Event{Kind: EventAlertFired, Firing: &alert.Firing{RuleID: "r1", DeviceID: "dev-1"}}
	if ev.Severity() != SeverityUnknown {
		t.Fatalf("severidad ausente = %q, esperada %q", ev.Severity(), SeverityUnknown)
	}
	if got := DetectionFinding(ev)["severity_id"]; got != 0 {
		t.Fatalf("severity_id de lo desconocido = %v, esperado 0", got)
	}
	if got := DetectionFinding(ev)["severity"]; got != "Unknown" {
		t.Fatalf("severity de lo desconocido = %v, esperado \"Unknown\"", got)
	}
}

// clavesProhibidas recorre el mapa completo buscando cualquier nombre de campo
// de ubicación, a cualquier profundidad.
func clavesProhibidas(t *testing.T, v any, ruta string) {
	t.Helper()
	prohibidas := map[string]bool{
		"lat": true, "lng": true, "latitude": true, "longitude": true,
		"location": true, "coordinates": true, "point": true, "address": true,
		"trail": true, "last_location": true,
	}
	switch tipo := v.(type) {
	case map[string]any:
		for k, sub := range tipo {
			if prohibidas[strings.ToLower(k)] {
				t.Fatalf("clave de ubicación %q en %s", k, ruta)
			}
			clavesProhibidas(t, sub, ruta+"."+k)
		}
	case []any:
		for _, sub := range tipo {
			clavesProhibidas(t, sub, ruta+"[]")
		}
	}
}

func TestEventosNuncaLlevanCoordenadas(t *testing.T) {
	envenenados := map[string]any{
		"lat": 41.403629, "lng": 2.174356,
		"location": "Carrer de Mallorca 401, Barcelona",
	}
	inc := incidenteAbierto()
	inc.Evidence = []string{"41.403629, 2.174356", "Carrer de Mallorca 401, Barcelona"}
	inc.Timeline = []incident.Entry{{
		At: time.Date(2026, 8, 29, 9, 5, 0, 0, time.UTC), Actor: "sistema",
		Note: "visto en 41.403629, 2.174356",
	}}
	ho := handoffPendiente()
	ho.Params = envenenados
	res := &action.Result{
		Adapter: "simulation", OK: true, DeviceID: "dev-7", DeviceName: "Tablet almacén",
		Action: action.Message, Params: envenenados, Severity: "medium",
		At: time.Date(2026, 8, 29, 9, 40, 0, 0, time.UTC),
	}

	eventos := []Event{
		{Kind: EventIncidentOpened, At: inc.UpdatedAt, DeliveryID: "d1", Incident: inc},
		{Kind: EventHandoffPending, At: ho.RequestedAt, DeliveryID: "d2", Handoff: ho},
		{Kind: EventActionExecuted, At: res.At, DeliveryID: "d3", Action: res},
	}
	fugas := []string{"41.403629", "2.174356", "Mallorca", "\"lat\"", "\"lng\"", "\"location\""}
	// El sobre nativo declara el tamaño de las colecciones envenenadas, nunca su
	// contenido: es lo que sustituye a mandar el incidente entero como 1.x.
	nativo, err := NativePayload(eventos[0])
	if err != nil {
		t.Fatal(err)
	}
	for _, contador := range []string{`"evidence_count":2`, `"timeline_count":1`} {
		if !strings.Contains(string(nativo), contador) {
			t.Fatalf("falta %s en el sobre nativo: %s", contador, nativo)
		}
	}
	for _, ev := range eventos {
		clavesProhibidas(t, normalizar(t, DetectionFinding(ev)), ev.Kind)
		for _, formato := range []string{"native", "ocsf"} {
			cuerpo, err := PayloadFor(formato, ev)
			if err != nil {
				t.Fatal(err)
			}
			for _, fuga := range fugas {
				if strings.Contains(string(cuerpo), fuga) {
					t.Fatalf("%s/%s: fuga %q en %s", ev.Kind, formato, fuga, cuerpo)
				}
			}
		}
	}
}

func TestOCSFPayloadEsDeterministaYDesnudo(t *testing.T) {
	ev := eventoAbierto()
	primero, err := OCSFPayload(ev)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 100; i++ {
		otro, err := OCSFPayload(eventoAbierto())
		if err != nil {
			t.Fatal(err)
		}
		if string(otro) != string(primero) {
			t.Fatalf("serialización %d difiere:\n%s\n%s", i, primero, otro)
		}
	}
	if !strings.HasPrefix(string(primero), `{"activity_id":1,`) {
		t.Fatalf("las claves deberían ir ordenadas: %s", primero)
	}
	if strings.Contains(string(primero), `"incident"`) || strings.Contains(string(primero), `"product":"LucidFence"`) {
		t.Fatalf("el evento OCSF no lleva el sobre nativo: %s", primero)
	}
}
