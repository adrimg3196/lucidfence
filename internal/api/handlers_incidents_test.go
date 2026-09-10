package api

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
)

var incidentT0 = time.Date(2026, 9, 5, 10, 0, 0, 0, time.UTC)

func newIncident(id, deviceID, deviceName, severity string, status incident.Status) incident.Incident {
	return incident.Incident{
		ID: id, DeviceID: deviceID, DeviceName: deviceName, Kind: incident.KindGeofenceExit,
		Severity: severity, Title: "Fuera de geocerca", Recommendation: "Revisar la ubicación",
		FenceID: "demo-hq", Status: status, Count: 1, Evidence: []string{"fence_state=outside"},
		OpenedAt: incidentT0, UpdatedAt: incidentT0, Timeline: []incident.Entry{},
	}
}

// seedIncidents deja la cartera que usan todos los casos: dos abiertos (uno
// critical con un título que obliga a entrecomillar en CSV) y uno cerrado con
// sello, para que el MTTR sea una medida real.
func seedIncidents(t *testing.T, e *testEnv) {
	t.Helper()
	first := newIncident("inc-geofence_exit-dev-001", "dev-001", "Tablet Campo A1", "critical", incident.StatusOpen)
	first.Title = `Tablet "Uno", fuera de geocerca`
	second := newIncident("inc-geofence_exit-dev-002", "dev-002", "Móvil Reparto B7", "high", incident.StatusOpen)
	third := newIncident("inc-geofence_exit-dev-003", "dev-003", "iPad Recepción", "medium", incident.StatusClosed)
	closedAt := incidentT0.Add(30 * time.Minute)
	third.ClosedAt = &closedAt
	if err := e.org.SaveIncidents([]incident.Incident{first, second, third}); err != nil {
		t.Fatal(err)
	}
}

// getRaw hace un GET autenticado y devuelve el cuerpo sin interpretar: la
// exportación responde CSV y e.do solo sabe leer JSON.
func getRaw(t *testing.T, e *testEnv, path string) (*http.Response, string) {
	t.Helper()
	req, err := newRequest(e, "GET", path)
	if err != nil {
		t.Fatal(err)
	}
	if e.cookie != nil {
		req.AddCookie(e.cookie)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	_ = res.Body.Close()
	return res, string(raw)
}

func TestIncidentsListaFiltraPorEstadoYDispositivo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedIncidents(t, e)
	cases := []struct {
		query string
		want  int
	}{
		{"", 3},
		{"?status=open", 2},
		{"?status=closed", 1},
		{"?device_id=dev-002", 1},
		{"?status=open&device_id=dev-001", 1},
		{"?status=cerrado", 0},
		{"?device_id=dev-999", 0},
	}
	for _, c := range cases {
		res, out := e.do("GET", "/api/v1/incidents"+c.query, nil, true)
		if res.StatusCode != 200 {
			t.Fatalf("lista %q: %d %v", c.query, res.StatusCode, out)
		}
		items, _ := out["items"].([]any)
		if len(items) != c.want || out["total"] != float64(c.want) {
			t.Fatalf("lista %q: %d elementos y total %v, want %d", c.query, len(items), out["total"], c.want)
		}
	}
	_, out := e.do("GET", "/api/v1/incidents", nil, true)
	first := out["items"].([]any)[0].(map[string]any)
	if first["id"] != "inc-geofence_exit-dev-001" || first["severity"] != "critical" {
		t.Fatalf("la lista conserva el orden del store (estado y severidad primero): %v", first)
	}
}

func TestIncidentPatchReconoceYSellaLaAuditoria(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedIncidents(t, e)
	body := map[string]any{"status": "ack", "assignee": " soc@acme.test ", "note": " Triaje en curso "}
	res, out := e.do("PATCH", "/api/v1/incidents/inc-geofence_exit-dev-001", body, true)
	if res.StatusCode != 200 || out["status"] != "ack" {
		t.Fatalf("reconocimiento: %d %v", res.StatusCode, out)
	}
	if out["acked_at"] != "2026-09-05T12:00:00Z" || out["closed_at"] != nil {
		t.Fatalf("ack sella acked_at y no toca closed_at: %v", out)
	}
	if out["assignee"] != "soc@acme.test" {
		t.Fatalf("el asignado llega sin espacios sobrantes: %v", out["assignee"])
	}
	timeline, _ := out["timeline"].([]any)
	if len(timeline) != 1 {
		t.Fatalf("una entrada de auditoría por transición: %v", timeline)
	}
	entry := timeline[0].(map[string]any)
	if entry["actor"] != "adri@example.com" || entry["from"] != "open" || entry["to"] != "ack" || entry["note"] != "Triaje en curso" {
		t.Fatalf("la auditoría dice quién hizo qué: %v", entry)
	}
	res, out = e.do("GET", "/api/v1/incidents/inc-geofence_exit-dev-001", nil, true)
	if res.StatusCode != 200 || out["status"] != "ack" || out["assignee"] != "soc@acme.test" {
		t.Fatalf("el cambio se persiste: %d %v", res.StatusCode, out)
	}
}

func TestIncidentPatchEstadoInvalidoProhibidoEInexistente(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedIncidents(t, e)
	path := "/api/v1/incidents/inc-geofence_exit-dev-001"

	res, out := e.do("PATCH", path, map[string]any{"status": "resuelto"}, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("un estado que no existe es entrada mal formada: %d %v", res.StatusCode, out)
	}
	detail, _ := out["detail"].(map[string]any)
	if detail["field"] != "status" {
		t.Fatalf("el 400 nombra el campo: %v", out)
	}

	res, out = e.do("PATCH", path, map[string]any{}, true)
	if res.StatusCode != 400 || out["error"] != "status es obligatorio" {
		t.Fatalf("cuerpo sin estado: %d %v", res.StatusCode, out)
	}

	res, out = e.do("PATCH", path, map[string]any{"status": "open"}, true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("transición prohibida (ya estaba abierto): %d %v", res.StatusCode, out)
	}

	res, out = e.do("PATCH", "/api/v1/incidents/inc-no-existe", map[string]any{"status": "ack"}, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("id inexistente: %d %v", res.StatusCode, out)
	}
}

func TestIncidentAnalyticsSinCerradosDevuelveMTTRNulo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	res, out := e.do("GET", "/api/v1/incidents/analytics", nil, true)
	if res.StatusCode != 200 || out["total"] != float64(0) {
		t.Fatalf("cartera vacía: %d %v", res.StatusCode, out)
	}
	v, has := out["mttr_seconds"]
	if !has {
		t.Fatalf("mttr_seconds viaja siempre en la respuesta: %v", out)
	}
	if v != nil {
		t.Fatalf("sin ningún cerrado el MTTR es nulo, jamás 0: %v", v)
	}
	if days, _ := out["by_day"].([]any); len(days) != 30 {
		t.Fatalf("la serie diaria no cambia de forma con la cartera vacía: %d días", len(days))
	}

	seedIncidents(t, e)
	res, out = e.do("GET", "/api/v1/incidents/analytics", nil, true)
	if res.StatusCode != 200 || out["total"] != float64(3) || out["open"] != float64(2) || out["closed"] != float64(1) {
		t.Fatalf("contadores por estado: %d %v", res.StatusCode, out)
	}
	sev, _ := out["by_severity"].(map[string]any)
	if sev["critical"] != float64(1) || sev["high"] != float64(1) {
		t.Fatalf("reparto por severidad: %v", sev)
	}
	if out["mttr_seconds"] != float64(1800) {
		t.Fatalf("el cerrado sellado sí es una medida (30 min): %v", out["mttr_seconds"])
	}
}

func TestIncidentExportCSVEscapaYSeDescarga(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedIncidents(t, e)
	res, raw := getRaw(t, e, "/api/v1/incidents/export")
	if res.StatusCode != 200 {
		t.Fatalf("export: %d %s", res.StatusCode, raw)
	}
	if ct := res.Header.Get("Content-Type"); !strings.Contains(ct, "text/csv") {
		t.Fatalf("Content-Type: %q", ct)
	}
	if cd := res.Header.Get("Content-Disposition"); cd != `attachment; filename="incidentes-2026-09-05.csv"` {
		t.Fatalf("Content-Disposition: %q", cd)
	}
	lines := strings.Split(strings.TrimRight(raw, "\n"), "\n")
	if len(lines) != 4 {
		t.Fatalf("cabecera más tres filas: %q", raw)
	}
	if !strings.HasPrefix(lines[0], "id,dispositivo_id,dispositivo,tipo,severidad,estado,titulo") {
		t.Fatalf("cabecera en español: %q", lines[0])
	}
	if !strings.Contains(lines[1], `"Tablet ""Uno"", fuera de geocerca"`) {
		t.Fatalf("comillas dobladas y campo entrecomillado (RFC 4180): %q", lines[1])
	}
	res, raw = getRaw(t, e, "/api/v1/incidents/export?status=closed")
	if res.StatusCode != 200 || strings.Count(strings.TrimRight(raw, "\n"), "\n") != 1 {
		t.Fatalf("el filtro también se aplica a la exportación: %d %q", res.StatusCode, raw)
	}
}

func TestIncidentesRespetanElRolDeQuienLlama(t *testing.T) {
	e := newRoleEnv(t)
	seedIncidents(t, e)
	path := "/api/v1/incidents/inc-geofence_exit-dev-001"

	e.as(auth.Operator)
	res, out := e.do("PATCH", path, map[string]any{"status": "ack", "note": "Lo miro yo"}, true)
	if res.StatusCode != 200 || out["status"] != "ack" {
		t.Fatalf("un operator reconoce incidentes (incident:write): %d %v", res.StatusCode, out)
	}
	entry := out["timeline"].([]any)[0].(map[string]any)
	if entry["actor"] != "operator@example.com" {
		t.Fatalf("el actor de la auditoría es quien llama: %v", entry)
	}

	e.as(auth.Viewer)
	if res, out := e.do("GET", "/api/v1/incidents", nil, true); res.StatusCode != 200 {
		t.Fatalf("un viewer lee la bandeja: %d %v", res.StatusCode, out)
	}
	if res, out := e.do("PATCH", path, map[string]any{"status": "closed"}, true); res.StatusCode != 403 || out["code"] != "forbidden" {
		t.Fatalf("un viewer no muta incidentes: %d %v", res.StatusCode, out)
	}
	if res, _ := getRaw(t, e, "/api/v1/incidents/export"); res.StatusCode != 403 {
		t.Fatalf("un viewer no tiene report:export: %d", res.StatusCode)
	}

	e.as(auth.Auditor)
	res2, raw := getRaw(t, e, "/api/v1/incidents/export")
	if res2.StatusCode != 200 || !strings.HasPrefix(raw, "id,dispositivo_id") {
		t.Fatalf("el auditor sí exporta (report:export): %d %q", res2.StatusCode, raw)
	}
}

// TestIncidentsListErrorInternoNoFiltraRutas convierte incidents.json en un
// directorio para forzar un fallo real del store: el 500 lleva "error interno"
// y nunca la ruta absoluta del fichero de la organización (spec §11).
func TestIncidentsListErrorInternoNoFiltraRutas(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	if err := os.Mkdir(e.org.Path("incidents.json"), 0o755); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("GET", "/api/v1/incidents", nil, true)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("500 error interno esperado: %d %v", res.StatusCode, out)
	}
	if strings.Contains(fmt.Sprintf("%v", out), e.org.Dir()) {
		t.Fatalf("el cuerpo filtra la ruta del store: %v", out)
	}
}
