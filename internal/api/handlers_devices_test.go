package api

import (
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

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
	t.Run("filtro por severidad", func(t *testing.T) { checkDevicesFiltroSeveridad(t, e) })
	t.Run("severidad fuera del vocabulario se descarta, no se rechaza", func(t *testing.T) { checkDevicesFiltroSeveridadInvalida(t, e) })
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

// checkDevicesFiltroSeveridad (M2-R63) prueba de extremo a extremo el filtro
// que DevicesPage ofrece en un <NativeSelect>: toma la severidad del primer
// dispositivo de la lista sin filtrar y comprueba que el filtro devuelve un
// subconjunto no vacío y homogéneo, nunca la flota entera disfrazada.
func checkDevicesFiltroSeveridad(t *testing.T, e *testEnv) {
	t.Helper()
	_, all := e.do("GET", "/api/v1/devices", nil, true)
	items := all["items"].([]any)
	severity := items[0].(map[string]any)["risk"].(map[string]any)["severity"].(string)
	res, out := e.do("GET", "/api/v1/devices?severity="+severity, nil, true)
	got := out["items"].([]any)
	if res.StatusCode != 200 || len(got) == 0 {
		t.Fatalf("filtro por severidad %q: %d %v", severity, res.StatusCode, out)
	}
	if len(got) >= len(items) {
		t.Fatalf("el filtro debería excluir al menos un dispositivo (severidad %q): %d de %d", severity, len(got), len(items))
	}
	for _, it := range got {
		if s := it.(map[string]any)["risk"].(map[string]any)["severity"]; s != severity {
			t.Fatalf("un dispositivo de otra severidad se coló en el filtro: %v", it)
		}
	}
}

// checkDevicesFiltroSeveridadInvalida cubre la mitad del ruling que un 400
// no puede cumplir por sí solo: un valor fuera de risk.Severities+unknown se
// descarta, no rechaza, así que un typo en la URL sigue devolviendo 200 con
// la flota entera en vez de romper el listado.
func checkDevicesFiltroSeveridadInvalida(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/devices?severity=nope", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 6 {
		t.Fatalf("severidad fuera del vocabulario se descarta, no se rechaza: %d %v", res.StatusCode, out)
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

// TestDeviceActionManual cubre POST /devices/{id}/actions: la vía por la que
// un operador lanza una orden a mano. Reutiliza el entorno con conector
// grabador de handlers_handoffs_test.go porque el caso del cooldown necesita
// saber qué llegó al conector y qué no.
func TestDeviceActionManual(t *testing.T) {
	e, fleet := nuevoEntornoConGrabador(t)
	t.Run("acción desconocida", func(t *testing.T) { checkAccionDesconocida(t, e) })
	t.Run("dispositivo inexistente", func(t *testing.T) { checkAccionDispositivoInexistente(t, e) })
	t.Run("wipe manual en observe es dry-run", func(t *testing.T) { checkAccionWipeEnObserve(t, e, fleet) })
	t.Run("segunda llamada dentro del cooldown", func(t *testing.T) { checkAccionCooldown(t, e, fleet) })
	t.Run("el resultado queda auditado con el actor", func(t *testing.T) { checkAccionAuditada(t, e) })
	t.Run("wipe manual sin allow_wipe queda bloqueado", func(t *testing.T) { checkAccionWipeBloqueado(t, e, fleet) })
}

func checkAccionDesconocida(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/devices/dev-001/actions", map[string]any{"action": "retire"}, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("acción desconocida: %d %v", res.StatusCode, out)
	}
	msg := out["error"].(string)
	if !strings.Contains(msg, "retire") || !strings.Contains(msg, "lock|wipe|message|locate|reboot|clear_passcode|set_compliance|custom|notify") {
		t.Fatalf("el 400 nombra el enum entero: %v", out)
	}
}

func checkAccionDispositivoInexistente(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/devices/dev-nope/actions", map[string]any{"action": "locate"}, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("dispositivo inexistente: %d %v", res.StatusCode, out)
	}
}

func checkAccionWipeEnObserve(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/devices/dev-004/actions",
		map[string]any{"action": "wipe", "params": map[string]any{"reason": "equipo robado"}}, true)
	if res.StatusCode != 200 || out["dry_run"] != true || out["ok"] != true {
		t.Fatalf("en observe todo es dry-run: %d %v", res.StatusCode, out)
	}
	if out["trigger"] != "manual" || out["device_id"] != "dev-004" {
		t.Fatalf("el origen queda marcado: %v", out)
	}
	if got := fleet.recibidas(); len(got) != 1 || got[0] != action.Wipe {
		t.Fatalf("el conector recibe el wipe en dry-run: %v", got)
	}
	fleet.olvidar()
}

func checkAccionCooldown(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/devices/dev-004/actions", map[string]any{"action": "wipe"}, true)
	if res.StatusCode != 409 || out["code"] != "cooldown" {
		t.Fatalf("segundo wipe dentro de la ventana: %d %v", res.StatusCode, out)
	}
	detail := out["detail"].(map[string]any)
	if detail["retry_after"] != "2026-09-05T13:00:00Z" {
		t.Fatalf("el 409 dice cuándo se puede reintentar (una hora, la ventana por defecto): %v", detail)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("una acción suprimida no llega al conector: %v", got)
	}
}

func checkAccionAuditada(t *testing.T, e *testEnv) {
	t.Helper()
	_, out := e.do("GET", "/api/v1/actions?limit=200", nil, true)
	for _, it := range out["items"].([]any) {
		act := it.(map[string]any)
		if act["trigger"] != "manual" {
			continue
		}
		if act["action"] != "wipe" || act["device_id"] != "dev-004" {
			t.Fatalf("la acción manual registrada no es la que se pidió: %v", act)
		}
		if !strings.Contains(act["note"].(string), "actor: adri@example.com") {
			t.Fatalf("el registro lleva el actor: %v", act)
		}
		return
	}
	t.Fatalf("la acción manual no quedó en actions.jsonl: %v", out)
}

// checkAccionWipeBloqueado es checkAprobarWipeBloqueado (la bandeja) visto
// desde la otra entrada manual: la misma tubería, el mismo guardarraíl y el
// mismo 200 con el bloqueo dentro. Es la red de la decisión de cabecera "un
// bloqueo del guardarraíl es un 200, no un 4xx, ni en la aprobación ni en la
// acción manual": sin él, borrar el `|| errors.Is(err, engine.ErrActionBlocked)`
// de handlers_devices.go convierte un wipe bloqueado en un 500 genérico y la
// suite entera sigue verde.
//
// Va el último y sobre dev-001, no sobre dev-004, por el estado que comparten
// los subtests: dev-004 arrastra la marca de cooldown que dejó
// checkAccionWipeEnObserve y el cooldown se decide antes que la doble llave
// (internal/engine/guardrails.go:103), así que un wipe suyo saldría suprimido
// y no bloqueado; y ni el enforce que enciende este caso ni la línea que añade
// a actions.jsonl deben llegar a los casos anteriores.
func checkAccionWipeBloqueado(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	set := settings.Default()
	set.Enforcement.Mode = settings.ModeEnforce
	set.Enforcement.LiveActions = []action.Action{action.Wipe}
	set.Enforcement.AllowWipe = false
	if err := e.org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("POST", "/api/v1/devices/dev-001/actions", map[string]any{"action": "wipe"}, true)
	if res.StatusCode != 200 || out["blocked"] != true || out["ok"] != false {
		t.Fatalf("un bloqueo no es un error de la petición: %d %v", res.StatusCode, out)
	}
	if out["error_type"] != "wipe_not_allowed" || out["trigger"] != "manual" {
		t.Fatalf("el resultado dice por qué no salió la orden: %v", out)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("el conector jamás ve un wipe bloqueado: %v", got)
	}
}
