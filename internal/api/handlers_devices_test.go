package api

import "testing"

// TestDevicesListaDetalleYTrail delega cada paso en una función con nombre
// propio (como TestSetupLoginMeLogout): un closure anidado en t.Run cuenta
// para la complejidad ciclomática de la función que lo contiene, así que la
// única forma de mantener cada paso bajo el umbral de gocyclo (15) es una
// función de nivel superior por paso, ejecutada en el mismo orden que el
// caso original de una sola función.
func TestDevicesListaDetalleYTrail(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	t.Run("run-once carga la flota fake", func(t *testing.T) { checkRunOnceCargaFlota(t, e) })
	t.Run("lista devuelve las seis fichas", func(t *testing.T) { checkDevicesLista(t, e) })
	t.Run("filtro state=inside", func(t *testing.T) { checkDevicesFiltroInside(t, e) })
	t.Run("búsqueda por nombre", func(t *testing.T) { checkDevicesBusquedaPorNombre(t, e) })
	t.Run("detalle de un dispositivo", func(t *testing.T) { checkDeviceDetalle(t, e) })
	t.Run("404 en dispositivo inexistente", func(t *testing.T) { checkDeviceNoEncontrado(t, e) })
	t.Run("trail con límite", func(t *testing.T) { checkDeviceTrail(t, e) })
}

func checkRunOnceCargaFlota(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/engine/run-once", nil, true)
	if res.StatusCode != 200 || out["devices_total"].(float64) != 6 {
		t.Fatalf("run-once: %d %v", res.StatusCode, out)
	}
}

func checkDevicesLista(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/devices", nil, true)
	if res.StatusCode != 200 || out["total"].(float64) != 6 || len(out["items"].([]any)) != 6 {
		t.Fatalf("lista: %d %v", res.StatusCode, out)
	}
}

func checkDevicesFiltroInside(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/devices?state=inside", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || len(items) == 0 || items[0].(map[string]any)["fence_state"] != "inside" {
		t.Fatalf("filtro inside: %v", out)
	}
}

func checkDevicesBusquedaPorNombre(t *testing.T, e *testEnv) {
	t.Helper()
	_, out := e.do("GET", "/api/v1/devices?q=recep", nil, true)
	if len(out["items"].([]any)) != 1 {
		t.Fatalf("búsqueda por nombre: %v", out)
	}
}

func checkDeviceDetalle(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/devices/dev-001", nil, true)
	if res.StatusCode != 200 || out["id"] != "dev-001" || out["inside_fence"] != "demo-hq" || out["inventory"].(map[string]any)["model"] == "" {
		t.Fatalf("detalle: %d %v", res.StatusCode, out)
	}
}

func checkDeviceNoEncontrado(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/devices/nope", nil, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("404: %d %v", res.StatusCode, out)
	}
}

func checkDeviceTrail(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/devices/dev-001/trail?limit=5", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 1 {
		t.Fatalf("trail: %d %v", res.StatusCode, out)
	}
}

// TestDeviceTrailInexistenteDevuelve404 cubre la ronda de corrección
// M1-R17: el trail de un id que no está en Devices() debe ser un 404, no un
// 200 con items vacíos (Trail lee un log JSONL que no sabe si el id existe).
func TestDeviceTrailInexistenteDevuelve404(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	res, out := e.do("GET", "/api/v1/devices/nope/trail", nil, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("trail inexistente: %d %v", res.StatusCode, out)
	}
}
