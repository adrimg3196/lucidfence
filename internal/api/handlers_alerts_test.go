package api

import (
	"errors"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

var alertT0 = time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)

func ptrB(v bool) *bool { return &v }

func alertBody(id string) map[string]any {
	return map[string]any{"id": id, "name": "Riesgo alto", "kind": "risk_above",
		"threshold": 80, "severity": "high", "enabled": true}
}

// seedAlertFleet deja un dispositivo que dispara las dos reglas del caso de
// evaluate: riesgo 90 (por encima de 80) e incumplimiento explícito.
func seedAlertFleet(t *testing.T, e *testEnv) {
	t.Helper()
	d := device.Device{
		ID: "dev-001", Name: "Tablet Campo A1", Platform: "android", Provider: "fake",
		Compliant: ptrB(false), FenceState: device.Inside, RouteState: device.Unassigned,
		Risk:         device.Verdict{Score: ptrF(90), Severity: "critical", Reasons: []string{}, MatchedPolicies: []string{}},
		LastReportAt: alertT0,
	}
	if err := e.org.SaveDevices([]device.Device{d}); err != nil {
		t.Fatal(err)
	}
}

func TestAlertsCRUDCompleto(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	body := alertBody("r-riesgo")

	res, out := e.do("POST", "/api/v1/alerts", body, true)
	if res.StatusCode != 201 || out["id"] != "r-riesgo" || out["created_at"] != "2026-09-05T12:00:00Z" {
		t.Fatalf("create: %d %v", res.StatusCode, out)
	}
	if res, out := e.do("POST", "/api/v1/alerts", body, true); res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("duplicado: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/alerts", nil, true)
	if res.StatusCode != 200 || out["total"] != float64(1) {
		t.Fatalf("lista: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/alerts/r-riesgo", nil, true)
	if res.StatusCode != 200 || out["kind"] != "risk_above" || out["threshold"] != float64(80) {
		t.Fatalf("detalle: %d %v", res.StatusCode, out)
	}
}

// TestAlertsUpdateYDeleteCierranElCiclo separa el PUT y el DELETE del alta en
// TestAlertsCRUDCompleto: juntar las siete comprobaciones en una sola función
// pasaba de la complejidad ciclomática máxima (16 > 15, golangci-lint), y unir
// alta, lectura, actualización y borrado en un test no aporta nada que dos
// funciones con su propio arranque no den ya.
func TestAlertsUpdateYDeleteCierranElCiclo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	body := alertBody("r-riesgo")
	if res, out := e.do("POST", "/api/v1/alerts", body, true); res.StatusCode != 201 {
		t.Fatalf("create: %d %v", res.StatusCode, out)
	}
	body["name"] = "Riesgo alto (revisado)"
	res, out := e.do("PUT", "/api/v1/alerts/r-riesgo", body, true)
	if res.StatusCode != 200 || out["name"] != "Riesgo alto (revisado)" || out["created_at"] != "2026-09-05T12:00:00Z" {
		t.Fatalf("update conserva created_at: %d %v", res.StatusCode, out)
	}
	if res, _ := e.do("DELETE", "/api/v1/alerts/r-riesgo", nil, true); res.StatusCode != 204 {
		t.Fatalf("delete: %d", res.StatusCode)
	}
	if res, _ := e.do("GET", "/api/v1/alerts/r-riesgo", nil, true); res.StatusCode != 404 {
		t.Fatal("la regla borrada ya no está")
	}
}

func TestAlertsUmbralYTipoInvalidosNombranElCampo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	cases := []struct {
		name string
		mut  func(map[string]any)
		want string
	}{
		{"umbral negativo", func(b map[string]any) { b["threshold"] = -1 }, "umbral inválido"},
		{"umbral fuera de escala", func(b map[string]any) { b["threshold"] = 101 }, "umbral inválido"},
		{"tipo desconocido", func(b map[string]any) { b["kind"] = "cosa" }, "tipo de alerta desconocido"},
		{"severidad inventada", func(b map[string]any) { b["severity"] = "urgente" }, "severidad"},
		{"id con espacios", func(b map[string]any) { b["id"] = "Regla 1" }, "id"},
	}
	for _, c := range cases {
		body := alertBody("r-mala")
		c.mut(body)
		res, out := e.do("POST", "/api/v1/alerts", body, true)
		if res.StatusCode != 400 || out["code"] != "invalid" {
			t.Fatalf("%s: %d %v", c.name, res.StatusCode, out)
		}
		if msg, _ := out["error"].(string); !strings.Contains(msg, c.want) {
			t.Fatalf("%s: el 400 debe nombrar el campo (%q): %q", c.name, c.want, msg)
		}
	}
	if rs, err := e.org.Alerts(); err != nil || len(rs) != 0 {
		t.Fatalf("ninguna regla inválida se guarda: %v %v", rs, err)
	}
}

// seedAlertsForEvaluate deja el dispositivo de seedAlertFleet con las dos
// reglas del caso de evaluate ya dadas de alta (riesgo y cumplimiento).
func seedAlertsForEvaluate(t *testing.T, e *testEnv) {
	t.Helper()
	seedAlertFleet(t, e)
	if res, out := e.do("POST", "/api/v1/alerts", alertBody("r-riesgo"), true); res.StatusCode != 201 {
		t.Fatalf("regla de riesgo: %d %v", res.StatusCode, out)
	}
	comp := alertBody("r-cumplimiento")
	comp["name"], comp["kind"], comp["threshold"] = "Incumplimiento", "noncompliant", 0
	if res, out := e.do("POST", "/api/v1/alerts", comp, true); res.StatusCode != 201 {
		t.Fatalf("regla de cumplimiento: %d %v", res.StatusCode, out)
	}
}

func TestAlertsEvaluateDevuelveDisparosSinPersistirNiEntregar(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedAlertsForEvaluate(t, e)

	res, out := e.do("POST", "/api/v1/alerts/evaluate", nil, true)
	if res.StatusCode != 200 || out["count"] != float64(2) || out["rules_evaluated"] != float64(2) {
		t.Fatalf("las dos reglas disparan sobre el dispositivo: %d %v", res.StatusCode, out)
	}
	firings, _ := out["firings"].([]any)
	first := firings[0].(map[string]any)
	if first["rule_id"] != "r-riesgo" || first["device_id"] != "dev-001" || first["reason"] != "riesgo 90 (umbral 80)" {
		t.Fatalf("primer disparo: %v", first)
	}
}

// TestAlertsEvaluateNoPersisteNiEntrega separa la comprobación de que la
// vista previa no toca disco de la del contenido de la respuesta anterior:
// las dos juntas en una sola función pasaban de la complejidad ciclomática
// máxima (16 > 15, golangci-lint).
func TestAlertsEvaluateNoPersisteNiEntrega(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedAlertsForEvaluate(t, e)
	before, err := os.ReadFile(e.org.Path("alerts.json"))
	if err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(e.org.Path("alerts.json"))
	if err != nil {
		t.Fatal(err)
	}

	if res, out := e.do("POST", "/api/v1/alerts/evaluate", nil, true); res.StatusCode != 200 {
		t.Fatalf("evaluate: %d %v", res.StatusCode, out)
	}

	after, err := os.ReadFile(e.org.Path("alerts.json"))
	if err != nil {
		t.Fatal(err)
	}
	info2, err := os.Stat(e.org.Path("alerts.json"))
	if err != nil {
		t.Fatal(err)
	}
	if string(after) != string(before) || !info2.ModTime().Equal(info.ModTime()) {
		t.Fatal("la vista previa no reescribe alerts.json")
	}
	if _, err := os.Stat(e.org.Path("deliveries.jsonl")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("la vista previa no entrega nada: %v", err)
	}
}

func TestAlertsEscrituraExigeAlertWrite(t *testing.T) {
	e := newRoleEnv(t)
	e.as(auth.Operator)
	if res, out := e.do("POST", "/api/v1/alerts", alertBody("r-riesgo"), true); res.StatusCode != 201 {
		t.Fatalf("un operator crea reglas: %d %v", res.StatusCode, out)
	}
	e.as(auth.Viewer)
	if res, out := e.do("GET", "/api/v1/alerts", nil, true); res.StatusCode != 200 {
		t.Fatalf("un viewer lee las reglas (incident:read): %d %v", res.StatusCode, out)
	}
	if res, out := e.do("POST", "/api/v1/alerts", alertBody("r-otra"), true); res.StatusCode != 403 {
		t.Fatalf("un viewer no crea reglas: %d %v", res.StatusCode, out)
	}
	if res, out := e.do("PUT", "/api/v1/alerts/r-riesgo", alertBody("r-riesgo"), true); res.StatusCode != 403 {
		t.Fatalf("un viewer no edita reglas: %d %v", res.StatusCode, out)
	}
	if res, out := e.do("DELETE", "/api/v1/alerts/r-riesgo", nil, true); res.StatusCode != 403 {
		t.Fatalf("un viewer no borra reglas: %d %v", res.StatusCode, out)
	}
	if res, out := e.do("POST", "/api/v1/alerts/evaluate", nil, true); res.StatusCode != 403 {
		t.Fatalf("la vista previa también es alert:write: %d %v", res.StatusCode, out)
	}
}
