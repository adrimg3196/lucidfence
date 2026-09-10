package api

import (
	"context"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// soarT0 es el instante de referencia de los casos de esta tarea.
var soarT0 = time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)

// recordingFleet es fakeFleet con memoria: apunta cada Execute que llega al
// conector. Es la única forma de comprobar la invariante de §6.5 desde la
// API (un wipe bloqueado no puede llegar al adapter): mirar el action.Result
// no basta, porque un bloqueo y un dry-run se parecen desde fuera.
type recordingFleet struct {
	*fakeFleet
	mu    sync.Mutex
	calls []action.Action
}

func (f *recordingFleet) Execute(ctx context.Context, dev device.Device, a action.Action, params map[string]any, dryRun bool) action.Result {
	f.mu.Lock()
	f.calls = append(f.calls, a)
	f.mu.Unlock()
	return f.fakeFleet.Execute(ctx, dev, a, params, dryRun)
}

func (f *recordingFleet) recibidas() []action.Action {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]action.Action(nil), f.calls...)
}

func (f *recordingFleet) olvidar() {
	f.mu.Lock()
	f.calls = nil
	f.mu.Unlock()
}

// nuevoEntornoConGrabador arranca el entorno con un conector que apunta lo
// que recibe, siembra la demo y deja la flota en devices.json con un ciclo
// (ApproveHandoff y ExecuteManual buscan el dispositivo ahí). El grabador se
// vacía al final: lo que ejecutó el ciclo no interesa a estos casos.
func nuevoEntornoConGrabador(t *testing.T) (*testEnv, *recordingFleet) {
	t.Helper()
	fleet := &recordingFleet{fakeFleet: &fakeFleet{now: func() time.Time { return soarT0 }}}
	e := newTestEnvWithFleet(t, fleet, soarT0)
	e.setup("demo")
	if res, out := e.do("POST", "/api/v1/engine/run-once", nil, true); res.StatusCode != 200 {
		t.Fatalf("run-once: %d %v", res.StatusCode, out)
	}
	fleet.olvidar()
	return e, fleet
}

// bandeja es la foto de handoffs.json con la que arrancan los casos: cuatro
// pendientes y uno ya rechazado, para que el filtro tenga algo que filtrar.
// Se escribe directamente en el store (no se provoca con un ciclo) para que
// los casos de la API no dependan de qué playbook casó en qué dispositivo:
// eso ya lo cubren los tests del motor (T16).
func bandeja() []playbook.Handoff {
	nuevo := func(id, dev, name string, a action.Action, sev string, min int) playbook.Handoff {
		return playbook.Handoff{ID: id, DeviceID: dev, DeviceName: name,
			PlaybookID: "soar-noncompliant-outside", PlaybookName: "No conforme y fuera de geocerca",
			Action: a, Params: map[string]any{"reason": "noncompliant_outside"},
			Reason: "compliant=false, fence_state=outside", Severity: sev,
			Status: playbook.HandoffPending, RequestedAt: soarT0.Add(time.Duration(min) * time.Minute)}
	}
	rechazado := nuevo("ho-cerrado", "dev-006", "Portátil Soporte", action.Lock, "high", -30)
	rechazado.Status = playbook.HandoffRejected
	return []playbook.Handoff{
		nuevo("ho-lock", "dev-001", "Tablet Campo A1", action.Lock, "high", -4),
		nuevo("ho-wipe", "dev-002", "Móvil Reparto B7", action.Wipe, "critical", -3),
		nuevo("ho-reject", "dev-003", "iPad Recepción", action.Reboot, "medium", -2),
		nuevo("ho-operator", "dev-005", "Escáner Almacén", action.Lock, "high", -1),
		rechazado,
	}
}

// TestBandejaDeHandoffs recorre el ciclo de vida completo de la bandeja. Cada
// paso vive en una función de nivel superior (como TestSetupLoginMeLogout):
// un closure anidado en t.Run cuenta para la complejidad ciclomática de la
// función que lo contiene, y el estado (la bandeja, los ajustes) es
// compartido y ordenado.
func TestBandejaDeHandoffs(t *testing.T) {
	e, fleet := nuevoEntornoConGrabador(t)
	if err := e.org.SaveHandoffs(bandeja()); err != nil {
		t.Fatal(err)
	}
	t.Run("lista con los pendientes primero", func(t *testing.T) { checkHandoffsLista(t, e) })
	t.Run("filtro status=pending", func(t *testing.T) { checkHandoffsFiltroPendientes(t, e) })
	t.Run("filtro con un estado inventado", func(t *testing.T) { checkHandoffsFiltroInvalido(t, e) })
	t.Run("aprobar en observe ejecuta en dry-run", func(t *testing.T) { checkAprobarEnObserve(t, e, fleet) })
	t.Run("aprobar dos veces es conflicto", func(t *testing.T) { checkAprobarDosVeces(t, e) })
	t.Run("wipe sin allow_wipe queda bloqueado", func(t *testing.T) { checkAprobarWipeBloqueado(t, e, fleet) })
	t.Run("rechazar no llama al conector", func(t *testing.T) { checkRechazar(t, e, fleet) })
	t.Run("handoff inexistente", func(t *testing.T) { checkHandoffInexistente(t, e) })
	t.Run("aprobar dentro del cooldown deja la petición varada", func(t *testing.T) { checkAprobarDentroDelCooldown(t, e, fleet) })
}

func checkHandoffsLista(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/handoffs", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || out["total"].(float64) != 5 || len(items) != 5 {
		t.Fatalf("lista: %d %v", res.StatusCode, out)
	}
	if items[0].(map[string]any)["status"] != "pending" || items[4].(map[string]any)["id"] != "ho-cerrado" {
		t.Fatalf("los pendientes van primero y el decidido al final: %v", items)
	}
	if items[0].(map[string]any)["id"] != "ho-operator" {
		t.Fatalf("dentro de los pendientes manda el más reciente: %v", items[0])
	}
}

func checkHandoffsFiltroPendientes(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/handoffs?status=pending", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || len(items) != 4 {
		t.Fatalf("filtro pending: %d %v", res.StatusCode, out)
	}
	for _, it := range items {
		if it.(map[string]any)["status"] != "pending" {
			t.Fatalf("el filtro deja pasar decididos: %v", it)
		}
	}
}

func checkHandoffsFiltroInvalido(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/handoffs?status=pendiente", nil, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("estado inventado: %d %v", res.StatusCode, out)
	}
	if !strings.Contains(out["error"].(string), "pending|approved|rejected|executed") {
		t.Fatalf("el 400 debe nombrar el enum: %v", out)
	}
}

func checkAprobarEnObserve(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/handoffs/ho-lock/approve", map[string]any{"note": "confirmado por el SOC"}, true)
	if res.StatusCode != 200 || out["status"] != "executed" || out["decided_by"] != "adri@example.com" {
		t.Fatalf("aprobar: %d %v", res.StatusCode, out)
	}
	result := out["result"].(map[string]any)
	if result["dry_run"] != true || result["ok"] != true || result["trigger"] != "handoff" {
		t.Fatalf("en observe la aprobación es dry-run: %v", result)
	}
	if _, blocked := result["blocked"]; blocked {
		t.Fatalf("nada que bloquear en observe: %v", result)
	}
	if got := fleet.recibidas(); len(got) != 1 || got[0] != action.Lock {
		t.Fatalf("el conector recibe el lock en dry-run: %v", got)
	}
	fleet.olvidar()
}

func checkAprobarDosVeces(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/handoffs/ho-lock/approve", map[string]any{"note": "otra vez"}, true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("segunda aprobación: %d %v", res.StatusCode, out)
	}
}

// checkAprobarWipeBloqueado es el caso dorado de
// legacy/tests/test_enforcement.py::test_wipe_blocked_in_enforce_without_allow_wipe
// visto desde la bandeja: la aprobación humana autoriza el intento, no abre
// la doble llave, y el conector no llega a ver el wipe.
func checkAprobarWipeBloqueado(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	set := settings.Default()
	set.Enforcement.Mode = settings.ModeEnforce
	set.Enforcement.LiveActions = []action.Action{action.Wipe}
	set.Enforcement.AllowWipe = false
	if err := e.org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("POST", "/api/v1/handoffs/ho-wipe/approve", map[string]any{"note": "aprobado por dirección"}, true)
	if res.StatusCode != 200 || out["status"] != "executed" {
		t.Fatalf("un bloqueo no es un error de la petición: %d %v", res.StatusCode, out)
	}
	result := out["result"].(map[string]any)
	if result["blocked"] != true || result["ok"] != false || result["error_type"] != "wipe_not_allowed" {
		t.Fatalf("resultado bloqueado: %v", result)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("el conector jamás ve un wipe bloqueado: %v", got)
	}
}

func checkRechazar(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/handoffs/ho-reject/reject", map[string]any{"note": "falso positivo de GPS"}, true)
	if res.StatusCode != 200 || out["status"] != "rejected" || out["note"] != "falso positivo de GPS" {
		t.Fatalf("rechazar: %d %v", res.StatusCode, out)
	}
	if _, has := out["result"]; has {
		t.Fatalf("un rechazo no ejecuta nada: %v", out)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("el conector no se entera de un rechazo: %v", got)
	}
}

func checkHandoffInexistente(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/handoffs/ho-nope/approve", map[string]any{"note": ""}, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("id inexistente: %d %v", res.StatusCode, out)
	}
}

// checkAprobarDentroDelCooldown fija el 409 cooldown de la aprobación —la
// desviación que el propio brief se añadió (task-20-brief.md:1315) y que no
// ejercitaba nadie— y, con él, lo que la supresión deja detrás.
//
// El par (dev-001, lock) ya se ejecutó en checkAprobarEnObserve dentro de la
// misma ventana (el reloj del entorno está clavado en soarT0), así que una
// segunda petición para ese par se suprime: el cooldown se decide antes que
// todo lo demás (internal/engine/guardrails.go:103) y no depende del modo.
//
// Las tres últimas comprobaciones documentan el callejón sin salida de
// M2-R52, que esta ronda NO corrige: T16 sella la decisión antes de ejecutar
// (internal/engine/handoffs.go:37) y la máquina de estados solo sale de
// approved a executed (internal/domain/playbook/handoff.go:104), así que el
// reintento que promete retry_after no existe por esta ruta y la bandeja se
// queda con una fila aprobada que nunca se ejecutó. Cuando la revisión final
// del hito decida cómo se sale de ahí, este caso es el que hay que reescribir.
func checkAprobarDentroDelCooldown(t *testing.T, e *testEnv, fleet *recordingFleet) {
	t.Helper()
	hs, err := e.org.Handoffs()
	if err != nil {
		t.Fatal(err)
	}
	otra := bandeja()[0] // dev-001 + lock: el mismo par que ya ejecutó checkAprobarEnObserve
	otra.ID, otra.RequestedAt = "ho-cooldown", soarT0
	if err := e.org.SaveHandoffs(append(hs, otra)); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("POST", "/api/v1/handoffs/ho-cooldown/approve", map[string]any{"note": "cambio de turno"}, true)
	if res.StatusCode != 409 || out["code"] != "cooldown" {
		t.Fatalf("dentro de la ventana la aprobación se suprime: %d %v", res.StatusCode, out)
	}
	detail := out["detail"].(map[string]any)
	if detail["retry_after"] != "2026-09-05T13:00:00Z" {
		t.Fatalf("el 409 dice cuándo volverá a estar disponible (una hora, la ventana por defecto): %v", detail)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("una acción suprimida no llega al conector: %v", got)
	}
	res, out = e.do("POST", "/api/v1/handoffs/ho-cooldown/approve", map[string]any{"note": "reintento"}, true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("la decisión ya está sellada: el reintento no existe por esta ruta (M2-R52): %d %v", res.StatusCode, out)
	}
	_, out = e.do("GET", "/api/v1/handoffs?status=approved", nil, true)
	items := out["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("la bandeja conserva exactamente la petición varada: %v", out)
	}
	varada := items[0].(map[string]any)
	if varada["id"] != "ho-cooldown" || varada["status"] != "approved" {
		t.Fatalf("varada en approved: %v", varada)
	}
	if _, ejecutada := varada["result"]; ejecutada {
		t.Fatalf("aprobada pero sin ejecutar: no hay resultado que enseñar: %v", varada)
	}
}

// TestHandoffsRespetanElRolDeQuienLlama comprueba la matriz §6.3 contra el
// middleware: un viewer lee la bandeja (incident:read) pero no aprueba, y un
// operator sí (handoff:approve). Va en su propio test, con el entorno por
// roles de T18 (newRoleEnv siembra un usuario por rol en users.json y e.as
// abre sesión con él), en vez de colgar de TestBandejaDeHandoffs: ese entorno
// no pasa por el asistente inicial, así que el inventario y la bandeja se
// siembran por el store. Basta con el dispositivo del handoff que se aprueba,
// que es el único que ApproveHandoff busca.
func TestHandoffsRespetanElRolDeQuienLlama(t *testing.T) {
	e := newRoleEnv(t)
	dev := fakeDevice("dev-005", "Escáner Almacén", "android", 40.4050, -3.7100,
		device.Inventory{Model: "Honeywell CT45"}, soarT0)
	if err := e.org.SaveDevices([]device.Device{dev}); err != nil {
		t.Fatal(err)
	}
	if err := e.org.SaveHandoffs(bandeja()); err != nil {
		t.Fatal(err)
	}
	e.as(auth.Viewer)
	res, out := e.do("POST", "/api/v1/handoffs/ho-operator/approve", map[string]any{"note": "yo"}, true)
	if res.StatusCode != 403 || out["code"] != "forbidden" {
		t.Fatalf("un viewer no aprueba: %d %v", res.StatusCode, out)
	}
	if res, out = e.do("GET", "/api/v1/handoffs", nil, true); res.StatusCode != 200 {
		t.Fatalf("un viewer sí lee la bandeja (incident:read): %d %v", res.StatusCode, out)
	}
	e.as(auth.Operator)
	res, out = e.do("POST", "/api/v1/handoffs/ho-operator/approve", map[string]any{"note": "turno de noche"}, true)
	if res.StatusCode != 200 || out["status"] != "executed" || out["decided_by"] != "operator@example.com" {
		t.Fatalf("un operator sí aprueba: %d %v", res.StatusCode, out)
	}
}
