package api

import "testing"

// TestFencesCRUDYValidacion delega cada paso en una función con nombre
// propio (como TestSetupLoginMeLogout): un closure anidado en t.Run cuenta
// para la complejidad ciclomática de la función que lo contiene, así que la
// única forma de mantener cada paso bajo el umbral de gocyclo (15) es una
// función de nivel superior por paso. body se comparte y se muta entre pasos
// (igual que en el caso original de una sola función) porque los mapas se
// pasan por referencia.
func TestFencesCRUDYValidacion(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	body := map[string]any{"id": "hq", "name": "HQ", "kind": "circle", "center": map[string]float64{"lat": 40.42, "lng": -3.71}, "radius_m": 300,
		"actions": []map[string]any{{"action": "message", "when": "on_enter", "enabled": true, "params": map[string]any{"text": "hola"}}}}
	t.Run("create", func(t *testing.T) { checkFenceCreate(t, e, body) })
	t.Run("duplicado", func(t *testing.T) { checkFenceDuplicado(t, e, body) })
	t.Run("inválida", func(t *testing.T) { checkFenceInvalida(t, e) })
	t.Run("lista", func(t *testing.T) { checkFenceLista(t, e) })
	t.Run("update", func(t *testing.T) { checkFenceUpdate(t, e, body) })
	t.Run("update inexistente", func(t *testing.T) { checkFenceUpdateInexistente(t, e, body) })
	t.Run("delete", func(t *testing.T) { checkFenceDelete(t, e) })
	t.Run("borrada", func(t *testing.T) { checkFenceBorrada(t, e) })
	t.Run("route", func(t *testing.T) { checkRouteCreate(t, e) })
	t.Run("poi", func(t *testing.T) { checkPOICreate(t, e) })
	t.Run("geojson", func(t *testing.T) { checkPOIGeoJSON(t, e) })
}

func checkFenceCreate(t *testing.T, e *testEnv, body map[string]any) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/fences", body, true)
	if res.StatusCode != 201 || out["id"] != "hq" || out["created_at"] == "" {
		t.Fatalf("create: %d %v", res.StatusCode, out)
	}
}

func checkFenceDuplicado(t *testing.T, e *testEnv, body map[string]any) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/fences", body, true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("duplicado: %d %v", res.StatusCode, out)
	}
}

func checkFenceInvalida(t *testing.T, e *testEnv) {
	t.Helper()
	bad := map[string]any{"id": "HQ 2", "name": "", "kind": "circle", "radius_m": 0}
	res, out := e.do("POST", "/api/v1/fences", bad, true)
	if res.StatusCode != 400 || out["code"] != "invalid" || out["error"] == "" {
		t.Fatalf("inválida: %d %v", res.StatusCode, out)
	}
}

func checkFenceLista(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/fences", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 1 {
		t.Fatalf("lista: %v", out)
	}
}

func checkFenceUpdate(t *testing.T, e *testEnv, body map[string]any) {
	t.Helper()
	body["name"] = "HQ renombrada"
	res, out := e.do("PUT", "/api/v1/fences/hq", body, true)
	if res.StatusCode != 200 || out["name"] != "HQ renombrada" {
		t.Fatalf("update: %d %v", res.StatusCode, out)
	}
}

func checkFenceUpdateInexistente(t *testing.T, e *testEnv, body map[string]any) {
	t.Helper()
	res, out := e.do("PUT", "/api/v1/fences/otra", body, true)
	if res.StatusCode != 404 {
		t.Fatalf("update inexistente: %d %v", res.StatusCode, out)
	}
}

func checkFenceDelete(t *testing.T, e *testEnv) {
	t.Helper()
	res, _ := e.do("DELETE", "/api/v1/fences/hq", nil, true)
	if res.StatusCode != 204 {
		t.Fatalf("delete: %d", res.StatusCode)
	}
}

func checkFenceBorrada(t *testing.T, e *testEnv) {
	t.Helper()
	res, _ := e.do("GET", "/api/v1/fences/hq", nil, true)
	if res.StatusCode != 404 {
		t.Fatal("borrada")
	}
}

func checkRouteCreate(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/routes", map[string]any{"id": "r1", "name": "R", "corridor_m": 100, "waypoints": []map[string]float64{{"lat": 40.42, "lng": -3.7}, {"lat": 40.43, "lng": -3.7}}, "device_ids": []string{"dev-001"}}, true)
	if res.StatusCode != 201 {
		t.Fatalf("route: %d %v", res.StatusCode, out)
	}
}

func checkPOICreate(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/pois", map[string]any{"id": "p1", "name": "P", "category": "school", "point": map[string]float64{"lat": 40.42, "lng": -3.7}}, true)
	if res.StatusCode != 201 {
		t.Fatalf("poi: %d %v", res.StatusCode, out)
	}
}

func checkPOIGeoJSON(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/pois/geojson", nil, true)
	if res.StatusCode != 200 || out["type"] != "FeatureCollection" {
		t.Fatalf("geojson: %v", out)
	}
}

func TestFencesRequierenPermisoYCSRF(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	req, _ := newRequest(e, "POST", "/api/v1/fences")
	req.AddCookie(e.cookie)
	if res, out := send(e, req); res.StatusCode != 403 || out["code"] != "csrf" {
		t.Fatalf("sin CSRF: %d %v", res.StatusCode, out)
	}
}
