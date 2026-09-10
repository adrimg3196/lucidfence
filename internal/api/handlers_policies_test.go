package api

import (
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
)

// policyBody es el cuerpo mínimo válido del recurso. Las claves son
// exactamente los tags JSON de policy.Policy porque decodeJSON rechaza campos
// desconocidos, y no lleva created_at ni updated_at a propósito: el editor
// tampoco los manda y los sellos los pone el servidor.
func policyBody(id string) map[string]any {
	return map[string]any{
		"id": id, "name": "Aviso al salir de la geocerca",
		"description": "Notifica a seguridad cuando el dispositivo sale de su geocerca.",
		"when":        []map[string]any{{"field": "fence_state", "op": "eq", "value": "outside"}},
		"actions": []map[string]any{{"action": "notify",
			"params": map[string]any{"channel": "security", "msg": "fuera de geocerca"}}},
		"enabled": true, "severity": "high",
	}
}

// policyUnknownState es la candidata del replay: condiciona sobre fence_state,
// que la simulación reconstruye del histórico, así que el resultado no queda
// marcado como aproximación y los números son comprobables.
func policyUnknownState(id string) map[string]any {
	p := policyBody(id)
	p["when"] = []map[string]any{{"field": "fence_state", "op": "eq", "value": "unknown"}}
	return p
}

// num lee un entero de la respuesta JSON (encoding/json los entrega float64).
func num(out map[string]any, key string) int {
	v, _ := out[key].(float64)
	return int(v)
}

// strList convierte una lista JSON en []string, fallando con un mensaje útil
// si el campo no tiene la forma esperada.
func strList(t *testing.T, v any) []string {
	t.Helper()
	raw, ok := v.([]any)
	if !ok {
		t.Fatalf("se esperaba una lista: %v", v)
	}
	out := make([]string, 0, len(raw))
	for _, it := range raw {
		s, ok := it.(string)
		if !ok {
			t.Fatalf("se esperaba texto en la lista: %v", it)
		}
		out = append(out, s)
	}
	return out
}

// TestPoliciesCRUDYValidacion delega cada paso en una función con nombre
// propio (como TestFencesCRUDYValidacion de M1): un closure anidado en t.Run
// cuenta para la complejidad ciclomática de quien lo contiene. body se comparte
// y se muta entre pasos porque los mapas se pasan por referencia.
func TestPoliciesCRUDYValidacion(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	body := policyBody("pol-salida")
	var createdAt string
	t.Run("create", func(t *testing.T) { createdAt = checkPolicyCreate(t, e, body) })
	t.Run("duplicada", func(t *testing.T) { checkPolicyDuplicada(t, e, body) })
	t.Run("op inventado", func(t *testing.T) { checkPolicyOpInventado(t, e) })
	t.Run("lista", func(t *testing.T) { checkPolicyLista(t, e) })
	t.Run("update conserva created_at", func(t *testing.T) { checkPolicyUpdate(t, e, body, createdAt) })
	t.Run("id que no coincide", func(t *testing.T) { checkPolicyIDNoCoincide(t, e) })
	t.Run("inexistente", func(t *testing.T) { checkPolicyInexistente(t, e) })
	t.Run("delete", func(t *testing.T) { checkPolicyDelete(t, e) })
}

func checkPolicyCreate(t *testing.T, e *testEnv, body map[string]any) string {
	t.Helper()
	res, out := e.do("POST", "/api/v1/policies", body, true)
	if res.StatusCode != 201 || out["id"] != "pol-salida" {
		t.Fatalf("create: %d %v", res.StatusCode, out)
	}
	createdAt, _ := out["created_at"].(string)
	updatedAt, _ := out["updated_at"].(string)
	if createdAt == "" || updatedAt == "" {
		t.Fatalf("create sin sellos: %v", out)
	}
	return createdAt
}

func checkPolicyDuplicada(t *testing.T, e *testEnv, body map[string]any) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/policies", body, true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("duplicada: %d %v", res.StatusCode, out)
	}
}

// checkPolicyOpInventado fija el caso dorado del esqueleto: el 400 nombra la
// política y el operador rechazado, que es lo que el editor necesita para
// señalar la fila del formulario.
func checkPolicyOpInventado(t *testing.T, e *testEnv) {
	t.Helper()
	bad := policyBody("pol-rota")
	bad["when"] = []map[string]any{{"field": "risk_score", "op": "casi", "value": 80}}
	res, out := e.do("POST", "/api/v1/policies", bad, true)
	msg, _ := out["error"].(string)
	if res.StatusCode != 400 || out["code"] != "invalid" || !strings.Contains(msg, "pol-rota") {
		t.Fatalf("op inventado: %d %v", res.StatusCode, out)
	}
	if !strings.Contains(msg, "casi") {
		t.Fatalf("el mensaje debe nombrar el operador rechazado: %q", msg)
	}
}

func checkPolicyLista(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/policies", nil, true)
	items, _ := out["items"].([]any)
	if res.StatusCode != 200 || len(items) != 1 || num(out, "total") != 1 {
		t.Fatalf("lista: %d %v", res.StatusCode, out)
	}
}

func checkPolicyUpdate(t *testing.T, e *testEnv, body map[string]any, createdAt string) {
	t.Helper()
	body["name"] = "Aviso revisado"
	body["enabled"] = false
	res, out := e.do("PUT", "/api/v1/policies/pol-salida", body, true)
	if res.StatusCode != 200 || out["name"] != "Aviso revisado" || out["enabled"] != false {
		t.Fatalf("update: %d %v", res.StatusCode, out)
	}
	if out["created_at"] != createdAt {
		t.Fatalf("el PUT debía conservar created_at %q: %v", createdAt, out)
	}
	if out["updated_at"] == "" {
		t.Fatalf("update sin updated_at: %v", out)
	}
}

func checkPolicyIDNoCoincide(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("PUT", "/api/v1/policies/pol-salida", policyBody("pol-otra"), true)
	msg, _ := out["error"].(string)
	if res.StatusCode != 400 || out["code"] != "invalid" || !strings.Contains(msg, "no coincide") {
		t.Fatalf("id que no coincide: %d %v", res.StatusCode, out)
	}
}

func checkPolicyInexistente(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/policies/pol-fantasma", nil, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("inexistente: %d %v", res.StatusCode, out)
	}
}

func checkPolicyDelete(t *testing.T, e *testEnv) {
	t.Helper()
	if res, _ := e.do("DELETE", "/api/v1/policies/pol-salida", nil, true); res.StatusCode != 204 {
		t.Fatalf("delete: %d", res.StatusCode)
	}
	if res, _ := e.do("GET", "/api/v1/policies/pol-salida", nil, true); res.StatusCode != 404 {
		t.Fatal("la política borrada sigue respondiendo")
	}
}

// TestPoliciesRespetanElRolDeQuienLlama recorre la matriz de §6.3 sobre las
// ocho rutas: policy:read lo tiene hasta un viewer (la simulación incluida,
// porque no escribe nada) y policy:write solo admin y owner.
func TestPoliciesRespetanElRolDeQuienLlama(t *testing.T) {
	e := newRoleEnv(t)
	e.as(auth.Owner)
	if res, out := e.do("POST", "/api/v1/policies", policyBody("pol-salida"), true); res.StatusCode != 201 {
		t.Fatalf("owner crea: %d %v", res.StatusCode, out)
	}
	e.as(auth.Viewer)
	for _, ruta := range []string{"/api/v1/policies", "/api/v1/policies/pol-salida",
		"/api/v1/policies/templates", "/api/v1/policies/fields"} {
		if res, out := e.do("GET", ruta, nil, true); res.StatusCode != 200 {
			t.Fatalf("viewer GET %s: %d %v", ruta, res.StatusCode, out)
		}
	}
	replay := map[string]any{"policy": policyUnknownState("pol-candidata")}
	if res, out := e.do("POST", "/api/v1/policies/replay", replay, true); res.StatusCode != 200 {
		t.Fatalf("viewer simula: %d %v", res.StatusCode, out)
	}
	for _, m := range []struct{ method, path string }{
		{"POST", "/api/v1/policies"},
		{"PUT", "/api/v1/policies/pol-salida"},
		{"DELETE", "/api/v1/policies/pol-salida"},
	} {
		res, out := e.do(m.method, m.path, policyBody("pol-salida"), true)
		if res.StatusCode != 403 || out["code"] != "forbidden" {
			t.Fatalf("viewer %s %s: %d %v", m.method, m.path, res.StatusCode, out)
		}
	}
}

// TestPoliciesMutacionConCookieSinCSRFEs403 cubre la otra mitad de §6.2: la
// capacidad no basta si la mutación llega por cookie sin la cabecera.
func TestPoliciesMutacionConCookieSinCSRFEs403(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	req, err := newRequest(e, "POST", "/api/v1/policies")
	if err != nil {
		t.Fatal(err)
	}
	req.AddCookie(e.cookie)
	if res, out := send(e, req); res.StatusCode != 403 || out["code"] != "csrf" {
		t.Fatalf("sin CSRF: %d %v", res.StatusCode, out)
	}
}

// TestPolicyTemplatesDevuelveLasCincoConIdsEstables: el editor las ofrece de un
// clic, así que los ids no pueden bailar y cada una tiene que explicar qué hace.
func TestPolicyTemplatesDevuelveLasCincoConIdsEstables(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	res, out := e.do("GET", "/api/v1/policies/templates", nil, true)
	items, _ := out["items"].([]any)
	if res.StatusCode != 200 || len(items) != 5 || num(out, "total") != 5 {
		t.Fatalf("templates: %d %v", res.StatusCode, out)
	}
	got := make([]string, 0, len(items))
	for _, it := range items {
		m, _ := it.(map[string]any)
		id, _ := m["id"].(string)
		if desc, _ := m["description"].(string); desc == "" {
			t.Fatalf("la plantilla %q va sin descripción", id)
		}
		if tpl, _ := m["template_id"].(string); tpl != id {
			t.Fatalf("plantilla %q con template_id %q", id, tpl)
		}
		got = append(got, id)
	}
	want := make([]string, 0, 5)
	for _, p := range policy.Templates() {
		want = append(want, p.ID)
	}
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("ids %v, esperados %v", got, want)
	}
}

// TestPolicyFieldsEsElUnicoVocabularioDelEditor es el test que impide duplicar
// el catálogo en TypeScript: si alguien añade un campo en policy.Fields y no
// llega a la ruta, o al revés, esto falla.
func TestPolicyFieldsEsElUnicoVocabularioDelEditor(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	res, out := e.do("GET", "/api/v1/policies/fields", nil, true)
	if res.StatusCode != 200 {
		t.Fatalf("fields: %d %v", res.StatusCode, out)
	}
	if got := strings.Join(strList(t, out["fields"]), ","); got != strings.Join(policy.Fields, ",") {
		t.Fatalf("fields %q, esperados %q", got, strings.Join(policy.Fields, ","))
	}
	ops := make([]string, 0, len(policy.Ops))
	for _, op := range policy.Ops {
		ops = append(ops, string(op))
	}
	if got := strings.Join(strList(t, out["ops"]), ","); got != strings.Join(ops, ",") {
		t.Fatalf("ops %q, esperados %q", got, strings.Join(ops, ","))
	}
}

// seedTrail deja un dispositivo en el inventario y tres posiciones en el
// histórico. No hay transiciones en events.jsonl, así que la simulación sitúa
// los tres puntos en fence_state unknown, que es con lo que arranca el motor.
func seedTrail(t *testing.T, e *testEnv) {
	t.Helper()
	at := time.Date(2026, 9, 5, 9, 0, 0, 0, time.UTC)
	d := device.Device{ID: "dev-001", Name: "Tablet Campo A1", Platform: "android", Provider: "fake",
		FenceState: device.Unknown, RouteState: device.Unassigned,
		Risk:         device.Verdict{Reasons: []string{}, MatchedPolicies: []string{}},
		LastReportAt: at}
	if err := e.org.SaveDevices([]device.Device{d}); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 3; i++ {
		if err := e.org.AppendTrail("dev-001", geo.Point{Lat: 40.4205, Lng: -3.7085}, at.Add(time.Duration(i)*time.Minute)); err != nil {
			t.Fatal(err)
		}
	}
}

// TestPolicyReplaySimulaUnaCandidataQueNoEstaGuardada es el what-if completo:
// una política que el store no conoce, un limit disparatado que se acota en vez
// de fallar, y la comprobación de que simular no guarda nada.
func TestPolicyReplaySimulaUnaCandidataQueNoEstaGuardada(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	seedTrail(t, e)
	body := map[string]any{"policy": policyUnknownState("pol-candidata"), "limit": 1000000}
	res, out := e.do("POST", "/api/v1/policies/replay", body, true)
	if res.StatusCode != 200 || out["policy_id"] != "pol-candidata" {
		t.Fatalf("replay: %d %v", res.StatusCode, out)
	}
	if num(out, "points_evaluated") != 3 || num(out, "devices_evaluated") != 1 || num(out, "firings") != 3 {
		t.Fatalf("resumen: %v", out)
	}
	byDevice, _ := out["by_device"].(map[string]any)
	byAction, _ := out["by_action"].(map[string]any)
	if byDevice["dev-001"] != 3.0 || byAction["notify"] != 3.0 {
		t.Fatalf("desglose: %v %v", byDevice, byAction)
	}
	if out["approximation"] != false {
		t.Fatalf("fence_state se reconstruye del histórico, no es aproximación: %v", out["notes"])
	}
	if !strings.Contains(fmt.Sprintf("%v", out["notes"]), "solo lectura") {
		t.Fatalf("las notas deben declarar que no se ejecutó nada: %v", out["notes"])
	}
	if _, lista := e.do("GET", "/api/v1/policies", nil, true); num(lista, "total") != 0 {
		t.Fatalf("simular no puede guardar la candidata: %v", lista)
	}
}

// TestPolicyReplayRechazaUnaCandidataInvalida: el 400 llega de la validación de
// la API, antes de tocar el disco, y nombra la política igual que el CRUD.
func TestPolicyReplayRechazaUnaCandidataInvalida(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	bad := policyBody("pol-sin-condiciones")
	bad["when"] = []map[string]any{}
	res, out := e.do("POST", "/api/v1/policies/replay", map[string]any{"policy": bad}, true)
	msg, _ := out["error"].(string)
	if res.StatusCode != 400 || out["code"] != "invalid" || !strings.Contains(msg, "pol-sin-condiciones") {
		t.Fatalf("candidata inválida: %d %v", res.StatusCode, out)
	}
}

// TestPoliciesErroresInternosNoFiltranRutasNiSePierden convierte primero
// policies.json y luego devices.json en directorios para forzar fallos reales
// de lectura: el cuerpo dice "error interno" y el detalle (con la ruta absoluta
// del store) queda solo en el log, con el paso que lo produjo.
func TestPoliciesErroresInternosNoFiltranRutasNiSePierden(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	if err := os.Mkdir(e.org.Path("policies.json"), 0o755); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("GET", "/api/v1/policies", nil, true)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("500 error interno esperado: %d %v", res.StatusCode, out)
	}
	if strings.Contains(fmt.Sprintf("%v", out), e.org.Dir()) {
		t.Fatalf("el cuerpo filtra la ruta del store: %v", out)
	}
	if !strings.Contains(e.logs.String(), "policies.list") || !strings.Contains(e.logs.String(), e.org.Dir()) {
		t.Fatalf("el error real debe quedar en el log: %s", e.logs.String())
	}
	if err := os.Mkdir(e.org.Path("devices.json"), 0o755); err != nil {
		t.Fatal(err)
	}
	res, out = e.do("POST", "/api/v1/policies/replay", map[string]any{"policy": policyUnknownState("pol-candidata")}, true)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("replay con el inventario ilegible: %d %v", res.StatusCode, out)
	}
	if !strings.Contains(e.logs.String(), "policies.replay") {
		t.Fatalf("el log debe nombrar el paso que falló: %s", e.logs.String())
	}
}
