package api

import (
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// playbookBrecha es el playbook de fábrica de T6 (soar-noncompliant-outside)
// escrito como cuerpo de la API: no conforme y fuera de geocerca, con un
// lock (destructivo, abre handoff) y un aviso al SOC.
func playbookBrecha() map[string]any {
	return map[string]any{
		"id": "pb-brecha", "name": "Brecha de perímetro",
		"description": "Dispositivo no conforme fuera de su geocerca.",
		"when": []map[string]any{
			{"field": "compliant", "op": "eq", "value": false},
			{"field": "fence_state", "op": "eq", "value": "outside"},
		},
		"actions": []map[string]any{
			{"action": "lock", "params": map[string]any{"reason": "noncompliant_outside"}},
			{"action": "notify", "params": map[string]any{"channel": "soc"}},
		},
		"enabled": true, "severity": "high",
	}
}

func TestPlaybooksCRUDYValidacion(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	t.Run("crear", func(t *testing.T) { checkPlaybookCrear(t, e) })
	t.Run("duplicado", func(t *testing.T) { checkPlaybookDuplicado(t, e) })
	t.Run("condición inválida", func(t *testing.T) { checkPlaybookCondicionInvalida(t, e) })
	t.Run("acción fuera del enum", func(t *testing.T) { checkPlaybookAccionInvalida(t, e) })
	t.Run("lista y detalle", func(t *testing.T) { checkPlaybookListaYDetalle(t, e) })
	t.Run("actualizar", func(t *testing.T) { checkPlaybookActualizar(t, e) })
	t.Run("borrar", func(t *testing.T) { checkPlaybookBorrar(t, e) })
}

func checkPlaybookCrear(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/playbooks", playbookBrecha(), true)
	if res.StatusCode != 201 || out["id"] != "pb-brecha" || out["created_at"] == "" || out["updated_at"] == "" {
		t.Fatalf("crear: %d %v", res.StatusCode, out)
	}
	if len(out["when"].([]any)) != 2 || len(out["actions"].([]any)) != 2 {
		t.Fatalf("condiciones y acciones se guardan enteras: %v", out)
	}
}

func checkPlaybookDuplicado(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/playbooks", playbookBrecha(), true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("duplicado: %d %v", res.StatusCode, out)
	}
}

func checkPlaybookCondicionInvalida(t *testing.T, e *testEnv) {
	t.Helper()
	body := playbookBrecha()
	body["id"] = "pb-malo"
	body["when"] = []map[string]any{{"field": "risk_score", "op": "nope", "value": 80}}
	res, out := e.do("POST", "/api/v1/playbooks", body, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("condición inválida: %d %v", res.StatusCode, out)
	}
	if !strings.Contains(out["error"].(string), "operador desconocido") {
		t.Fatalf("el 400 explica qué operación falla: %v", out)
	}
}

func checkPlaybookAccionInvalida(t *testing.T, e *testEnv) {
	t.Helper()
	body := playbookBrecha()
	body["id"] = "pb-retire"
	body["actions"] = []map[string]any{{"action": "retire"}}
	res, out := e.do("POST", "/api/v1/playbooks", body, true)
	if res.StatusCode != 400 || !strings.Contains(out["error"].(string), "retire") {
		t.Fatalf("acción que 2.0 no porta: %d %v", res.StatusCode, out)
	}
}

func checkPlaybookListaYDetalle(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/playbooks", nil, true)
	if res.StatusCode != 200 || out["total"].(float64) != 1 {
		t.Fatalf("lista: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/playbooks/pb-brecha", nil, true)
	if res.StatusCode != 200 || out["severity"] != "high" || out["enabled"] != true {
		t.Fatalf("detalle: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/playbooks/pb-nope", nil, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("inexistente: %d %v", res.StatusCode, out)
	}
}

func checkPlaybookActualizar(t *testing.T, e *testEnv) {
	t.Helper()
	body := playbookBrecha()
	body["name"] = "Brecha de perímetro (revisada)"
	body["enabled"] = false
	res, out := e.do("PUT", "/api/v1/playbooks/pb-brecha", body, true)
	if res.StatusCode != 200 || out["name"] != "Brecha de perímetro (revisada)" || out["enabled"] != false {
		t.Fatalf("actualizar: %d %v", res.StatusCode, out)
	}
	if out["created_at"] == "" {
		t.Fatalf("un PUT sin created_at no borra la fecha de alta: %v", out)
	}
	res, out = e.do("PUT", "/api/v1/playbooks/pb-otro", body, true)
	if res.StatusCode != 404 {
		t.Fatalf("actualizar inexistente: %d %v", res.StatusCode, out)
	}
}

func checkPlaybookBorrar(t *testing.T, e *testEnv) {
	t.Helper()
	if res, _ := e.do("DELETE", "/api/v1/playbooks/pb-brecha", nil, true); res.StatusCode != 204 {
		t.Fatalf("borrar: %d", res.StatusCode)
	}
	if res, _ := e.do("GET", "/api/v1/playbooks/pb-brecha", nil, true); res.StatusCode != 404 {
		t.Fatal("borrado")
	}
}

// TestPlaybooksLecturaPolicyReadEscrituraPlaybookWrite comprueba la matriz
// §6.3 contra el middleware: viewer lee (policy:read) pero no escribe, y
// operator escribe (playbook:write, que la matriz sí le da, a diferencia de
// policy:write). Usa el entorno por roles de T18: newRoleEnv siembra un
// usuario por rol y e.as cambia la sesión de e.do, así que aquí no hace falta
// e.setup (que solo crea owners) ni ningún ayudante nuevo.
func TestPlaybooksLecturaPolicyReadEscrituraPlaybookWrite(t *testing.T) {
	e := newRoleEnv(t)
	e.as(auth.Viewer)
	if res, out := e.do("GET", "/api/v1/playbooks", nil, true); res.StatusCode != 200 {
		t.Fatalf("un viewer lee playbooks: %d %v", res.StatusCode, out)
	}
	res, out := e.do("POST", "/api/v1/playbooks", playbookBrecha(), true)
	if res.StatusCode != 403 || out["code"] != "forbidden" {
		t.Fatalf("un viewer no escribe playbooks: %d %v", res.StatusCode, out)
	}
	e.as(auth.Operator)
	res, out = e.do("POST", "/api/v1/playbooks", playbookBrecha(), true)
	if res.StatusCode != 201 || out["id"] != "pb-brecha" {
		t.Fatalf("un operator sí escribe playbooks: %d %v", res.StatusCode, out)
	}
	if res, _ = e.do("DELETE", "/api/v1/playbooks/pb-brecha", nil, true); res.StatusCode != 204 {
		t.Fatalf("el borrado usa la misma capacidad que la escritura: %d", res.StatusCode)
	}
}
