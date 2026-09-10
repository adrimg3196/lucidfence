package engine

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// pendiente construye la petición que habría abierto el ciclo sobre el
// dispositivo de la fixture.
func pendiente(id string, a action.Action) playbook.Handoff {
	return playbook.Handoff{
		ID: id, DeviceID: "dev-1", DeviceName: "Tablet almacén",
		PlaybookID: "soar-brecha", PlaybookName: "Brecha de perímetro",
		Action: a, Params: map[string]any{"reason": "noncompliant_outside"},
		Reason: "compliant=false, fence_state=outside", Severity: risk.SeverityHigh,
		Status: playbook.HandoffPending, RequestedAt: tSOAR,
	}
}

// conBandeja monta el motor sin playbooks, corre un ciclo para que
// devices.json tenga la flota (ApproveHandoff y ExecuteManual buscan ahí el
// dispositivo) y escribe la bandeja del caso. El grabador se vacía: lo que
// ejecutó el ciclo no interesa a estas pruebas.
func conBandeja(t *testing.T, hs ...playbook.Handoff) (*Engine, *store.OrgStore, *grabadora) {
	t.Helper()
	e, org, fleet, _ := motorSOAR(t, fueraHQ, false)
	unCiclo(t, e)
	if err := org.SaveHandoffs(hs); err != nil {
		t.Fatal(err)
	}
	fleet.olvidar()
	return e, org, fleet
}

// enforceWipeSinLlave deja la organización en enforce con el wipe en vivo
// pero sin allow_wipe: la doble llave a medio girar.
func enforceWipeSinLlave(t *testing.T, org *store.OrgStore) {
	t.Helper()
	set := settings.Default()
	set.Enforcement.Mode = settings.ModeEnforce
	set.Enforcement.LiveActions = []action.Action{action.Wipe}
	set.Enforcement.AllowWipe = false
	if err := org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
}

// TestAprobarEjecutaEnDryRunYCierraLaPeticion: en observe, aprobar un lock lo
// manda al conector en dry-run y deja el resultado dentro del handoff.
func TestAprobarEjecutaEnDryRunYCierraLaPeticion(t *testing.T) {
	e, org, fleet := conBandeja(t, pendiente("ho-lock", action.Lock))
	h, err := e.ApproveHandoff(context.Background(), "ho-lock", "ana@lucidfence.test", "confirmado por el SOC")
	if err != nil {
		t.Fatal(err)
	}
	assertLockAprobado(t, h)
	got := fleet.recibidas()
	if len(got) != 1 || got[0].Action != action.Lock || !got[0].DryRun {
		t.Fatalf("el conector recibe el lock con dry_run true: %v", got)
	}
	acts, err := org.RecentActions(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) != 1 || acts[0].Action != action.Lock ||
		!strings.Contains(acts[0].Note, "actor: ana@lucidfence.test") {
		t.Fatalf("la ejecución queda auditada con el actor: %+v", acts)
	}
	if hs := bandejaDe(t, org); len(hs) != 1 || hs[0].Status != playbook.HandoffExecuted || hs[0].Result == nil {
		t.Fatalf("la bandeja guarda el handoff cerrado con su resultado: %+v", hs)
	}
}

// assertLockAprobado comprueba el handoff que devuelve ApproveHandoff: la
// decisión sellada y el resultado que quedó dentro. Es una función con nombre
// y no un bloque más del test porque gocyclo suma todas las ramas de la
// función que las contiene, igual que los assertXxx de engine_test.go.
func assertLockAprobado(t *testing.T, h playbook.Handoff) {
	t.Helper()
	if h.Status != playbook.HandoffExecuted || h.DecidedBy != "ana@lucidfence.test" ||
		h.Note != "confirmado por el SOC" || h.DecidedAt == nil || !h.DecidedAt.Equal(tSOAR) {
		t.Fatalf("la decisión humana queda sellada y la petición cerrada: %+v", h)
	}
	if h.Result == nil {
		t.Fatalf("un handoff ejecutado lleva su resultado dentro: %+v", h)
	}
	if !h.Result.DryRun || !h.Result.OK || h.Result.Blocked {
		t.Fatalf("en observe la aprobación es dry-run y no hay nada que bloquear: %+v", h.Result)
	}
	if h.Result.Trigger != TriggerHandoff || h.Result.PlaybookID != "soar-brecha" {
		t.Fatalf("el resultado se traza al gate humano y a su playbook: %+v", h.Result)
	}
}

// TestAprobarUnWipeSinLlaveQuedaBloqueado es
// legacy/tests/test_enforcement.py::test_wipe_blocked_in_enforce_without_allow_wipe
// visto desde la bandeja: la aprobación autoriza el intento, no abre la doble
// llave, y el conector no llega a ver el wipe.
func TestAprobarUnWipeSinLlaveQuedaBloqueado(t *testing.T) {
	e, org, fleet := conBandeja(t, pendiente("ho-wipe", action.Wipe))
	enforceWipeSinLlave(t, org)

	h, err := e.ApproveHandoff(context.Background(), "ho-wipe", "ana@lucidfence.test", "aprobado por dirección")
	if err != nil {
		t.Fatalf("un bloqueo no es un error de la decisión: %v", err)
	}
	if h.Status != playbook.HandoffExecuted || h.Result == nil {
		t.Fatalf("la petición se resolvió: hubo decisión e intento: %+v", h)
	}
	if !h.Result.Blocked || h.Result.OK || h.Result.ErrorType != BlockedWipeNotAllowed {
		t.Fatalf("resultado bloqueado con su motivo: %+v", h.Result)
	}
	if !strings.Contains(h.Result.Error, "allow_wipe") {
		t.Fatalf("el motivo nombra la llave que falta: %q", h.Result.Error)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("el conector jamás ve un wipe bloqueado: %v", got)
	}
	acts, err := org.RecentActions(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) != 1 || !acts[0].Blocked {
		t.Fatalf("un intento parado sí se audita: %+v", acts)
	}
}

// TestRechazarNoLlamaAlConector: un rechazo no ejecuta nada, ni en dry-run.
func TestRechazarNoLlamaAlConector(t *testing.T) {
	e, org, fleet := conBandeja(t, pendiente("ho-reject", action.Reboot))
	h, err := e.RejectHandoff(context.Background(), "ho-reject", "ana@lucidfence.test", "falso positivo de GPS")
	if err != nil {
		t.Fatal(err)
	}
	if h.Status != playbook.HandoffRejected || h.Note != "falso positivo de GPS" || h.Result != nil {
		t.Fatalf("rechazado, con nota y sin resultado: %+v", h)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("un rechazo no toca el dispositivo: %v", got)
	}
	if acts, _ := org.RecentActions(10); len(acts) != 0 {
		t.Fatalf("un rechazo no deja acciones: %+v", acts)
	}
	if hs := bandejaDe(t, org); len(hs) != 1 || hs[0].Status != playbook.HandoffRejected {
		t.Fatalf("la bandeja conserva el rechazo: %+v", hs)
	}
}

// TestDecidirDosVecesEsConflicto y TestHandoffInexistente cubren los dos
// centinelas que T20 traduce a 409 y 404.
func TestDecidirDosVecesEsConflicto(t *testing.T) {
	e, _, fleet := conBandeja(t, pendiente("ho-lock", action.Lock))
	if _, err := e.ApproveHandoff(context.Background(), "ho-lock", "ana@lucidfence.test", ""); err != nil {
		t.Fatal(err)
	}
	fleet.olvidar()
	h, err := e.ApproveHandoff(context.Background(), "ho-lock", "ana@lucidfence.test", "otra vez")
	if !errors.Is(err, ErrHandoffDecided) {
		t.Fatalf("una petición cerrada no se redecide: %v", err)
	}
	if h.DeviceID != "dev-1" || h.Action != action.Lock {
		t.Fatalf("el error devuelve el handoff para que la API pueda explicarlo: %+v", h)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("la segunda aprobación no ejecuta nada: %v", got)
	}
	if _, err := e.RejectHandoff(context.Background(), "ho-lock", "ana@lucidfence.test", ""); !errors.Is(err, ErrHandoffDecided) {
		t.Fatalf("tampoco se puede rechazar lo ya ejecutado: %v", err)
	}
}

func TestHandoffInexistente(t *testing.T) {
	e, _, _ := conBandeja(t)
	if _, err := e.ApproveHandoff(context.Background(), "ho-inventado", "ana@lucidfence.test", ""); !errors.Is(err, ErrHandoffNotFound) {
		t.Fatalf("aprobar lo que no existe: %v", err)
	}
	if _, err := e.RejectHandoff(context.Background(), "ho-inventado", "ana@lucidfence.test", ""); !errors.Is(err, ErrHandoffNotFound) {
		t.Fatalf("rechazar lo que no existe: %v", err)
	}
}

// TestAprobarUnHandoffDeUnDispositivoQueYaNoEsta: la decisión humana se
// guarda igual; lo que falta es el dispositivo.
func TestAprobarUnHandoffDeUnDispositivoQueYaNoEsta(t *testing.T) {
	h := pendiente("ho-lock", action.Lock)
	h.DeviceID, h.DeviceName = "dev-999", "Tablet dada de baja"
	e, org, fleet := conBandeja(t, h)

	got, err := e.ApproveHandoff(context.Background(), "ho-lock", "ana@lucidfence.test", "")
	if !errors.Is(err, ErrDeviceNotFound) {
		t.Fatalf("sin dispositivo no hay a quién mandar la orden: %v", err)
	}
	if got.Status != playbook.HandoffApproved {
		t.Fatalf("la aprobación se conserva: %+v", got)
	}
	if hs := bandejaDe(t, org); len(hs) != 1 || hs[0].Status != playbook.HandoffApproved {
		t.Fatalf("y queda escrita en la bandeja: %+v", hs)
	}
	if len(fleet.recibidas()) != 0 {
		t.Fatalf("nada llega al conector: %v", fleet.recibidas())
	}
}

// TestExecuteManualAuditaConElActorYSeEnfria recorre la vía de
// POST /devices/{id}/actions: pasa por los guardarraíles, queda en
// actions.jsonl con quien la pidió y la segunda vez la suprime el cooldown.
func TestExecuteManualAuditaConElActorYSeEnfria(t *testing.T) {
	e, org, fleet := conBandeja(t)
	res, err := e.ExecuteManual(context.Background(), "dev-1", action.Wipe, nil, "adri@example.com")
	if err != nil {
		t.Fatal(err)
	}
	if !res.DryRun || !res.OK || res.Trigger != TriggerManual {
		t.Fatalf("en observe una acción manual sale en dry-run: %+v", res)
	}
	if !strings.Contains(res.Note, "actor: adri@example.com") {
		t.Fatalf("el resultado lleva el actor: %q", res.Note)
	}
	acts, err := org.RecentActions(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) != 1 || acts[0].Trigger != TriggerManual || acts[0].Action != action.Wipe ||
		!strings.Contains(acts[0].Note, "actor: adri@example.com") {
		t.Fatalf("la acción manual queda en actions.jsonl con el actor: %+v", acts)
	}
	fleet.olvidar()

	if _, err := e.ExecuteManual(context.Background(), "dev-1", action.Wipe, nil, "adri@example.com"); !errors.Is(err, ErrActionSuppressed) {
		t.Fatalf("la misma destructiva dentro de la ventana se suprime: %v", err)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("una acción suprimida no llega al conector: %v", got)
	}
	if acts, _ = org.RecentActions(10); len(acts) != 1 {
		t.Fatalf("y no deja rastro nuevo en la auditoría: %+v", acts)
	}
}

// TestExecuteManualBloqueadaDevuelveElResultado: la petición era válida, la
// orden no salió; T20 responde 200 con este resultado dentro.
func TestExecuteManualBloqueadaDevuelveElResultado(t *testing.T) {
	e, org, fleet := conBandeja(t)
	enforceWipeSinLlave(t, org)

	res, err := e.ExecuteManual(context.Background(), "dev-1", action.Wipe, nil, "adri@example.com")
	if !errors.Is(err, ErrActionBlocked) {
		t.Fatalf("una orden bloqueada se devuelve como tal: %v", err)
	}
	if !res.Blocked || res.OK || res.ErrorType != BlockedWipeNotAllowed {
		t.Fatalf("con el resultado relleno y su motivo: %+v", res)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("el conector no ve un wipe bloqueado: %v", got)
	}
}

// TestExecuteManualDispositivoInexistente cierra el centinela que falta.
func TestExecuteManualDispositivoInexistente(t *testing.T) {
	e, _, fleet := conBandeja(t)
	if _, err := e.ExecuteManual(context.Background(), "dev-404", action.Locate, nil, "adri@example.com"); !errors.Is(err, ErrDeviceNotFound) {
		t.Fatalf("dispositivo inexistente: %v", err)
	}
	if len(fleet.recibidas()) != 0 {
		t.Fatalf("nada llega al conector: %v", fleet.recibidas())
	}
}
