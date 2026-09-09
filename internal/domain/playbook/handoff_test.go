package playbook

import (
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

func instante() time.Time { return time.Date(2026, 9, 6, 9, 30, 0, 0, time.UTC) }

// simularCiclo replica el bucle del motor de
// legacy/tests/test_multiuem_soar_gaps.py::test_soar_human_gate_emits_handoff_not_execution:
// las acciones no destructivas proceden y las destructivas se convierten en
// handoffs pendientes. T16 implementa este mismo reparto en el motor.
func simularCiclo(ms []Match, deviceID, deviceName string, at time.Time) ([]Handoff, []action.Action) {
	var handoffs []Handoff
	var ejecutadas []action.Action
	for _, m := range ms {
		for _, a := range m.Actions {
			if !RequiresHandoff(a.Action) {
				ejecutadas = append(ejecutadas, a.Action)
				continue
			}
			handoffs = append(handoffs, Handoff{
				ID:         HandoffID(deviceID, m.PlaybookID, a.Action),
				DeviceID:   deviceID,
				DeviceName: deviceName,
				PlaybookID: m.PlaybookID, PlaybookName: m.Name,
				Action: a.Action, Params: a.Params,
				Reason:   strings.Join(m.MatchedFields, ", "),
				Severity: m.Severity, Status: HandoffPending, RequestedAt: at,
			})
		}
	}
	return handoffs, ejecutadas
}

func TestGateHumanoDeUnaAccionDestructiva(t *testing.T) {
	ms := MatchAll(Defaults(), sujetoBrecha())
	if len(ms) != 1 || ms[0].PlaybookID != "soar-noncompliant-outside" {
		t.Fatalf("la brecha de geocerca debe disparar el playbook de perímetro: %#v", ms)
	}
	handoffs, ejecutadas := simularCiclo(ms, "dev-1", "iPad kiosco", instante())
	if len(handoffs) != 1 || handoffs[0].Action != action.Lock {
		t.Fatalf("el lock destructivo se registra como handoff, no se ejecuta: %#v", handoffs)
	}
	h := handoffs[0]
	if h.Status != HandoffPending || h.Result != nil || h.DecidedAt != nil || h.DecidedBy != "" {
		t.Fatalf("un handoff nace pendiente, sin resultado y sin decisión: %#v", h)
	}
	if h.Reason != "compliant, fence_state" {
		t.Errorf("el motivo debe llevar los campos que casaron, dio %q", h.Reason)
	}
	if len(ejecutadas) != 1 || ejecutadas[0] != action.Notify {
		t.Fatalf("las acciones no destructivas (notify) sí proceden: %#v", ejecutadas)
	}
}

func TestUnPlaybookNoDestructivoNoProduceHandoff(t *testing.T) {
	ms := MatchAll(Defaults(), sujetoFueraDeRuta())
	handoffs, ejecutadas := simularCiclo(ms, "dev-2", "Furgoneta 2", instante())
	if handoffs != nil {
		t.Fatalf("un playbook solo de aviso no abre handoffs: %#v", handoffs)
	}
	if len(ejecutadas) != 1 || ejecutadas[0] != action.Notify {
		t.Fatalf("la notificación procede sin gate: %#v", ejecutadas)
	}
}

func TestRequiresHandoffEsElEspejoDeDestructive(t *testing.T) {
	for _, a := range action.All {
		if RequiresHandoff(a) != a.Destructive() {
			t.Errorf("%q: RequiresHandoff y Destructive deben coincidir", a)
		}
	}
	for _, a := range []action.Action{action.Lock, action.Wipe, action.ClearPasscode, action.Reboot} {
		if !RequiresHandoff(a) {
			t.Errorf("%q exige handoff (spec §6.5)", a)
		}
	}
	for _, a := range []action.Action{action.Notify, action.Message, action.Locate, action.SetCompliance, action.Custom} {
		if RequiresHandoff(a) {
			t.Errorf("%q no exige handoff", a)
		}
	}
}

func TestHandoffIDEsDeterministaYSeguroEnURL(t *testing.T) {
	id := HandoffID("dev-1", "soar-noncompliant-outside", action.Lock)
	if id != "ho-dev-1-soar-noncompliant-outside-lock" {
		t.Fatalf("HandoffID = %q, quiero el formato ho-<device>-<playbook>-<action>", id)
	}
	if HandoffID("dev-1", "soar-noncompliant-outside", action.Lock) != id {
		t.Fatal("HandoffID debe ser determinista")
	}
	distintos := map[string]bool{
		id: true,
		HandoffID("dev-2", "soar-noncompliant-outside", action.Lock): true,
		HandoffID("dev-1", "soar-locate-unknown", action.Lock):       true,
		HandoffID("dev-1", "soar-noncompliant-outside", action.Wipe): true,
	}
	if len(distintos) != 4 {
		t.Fatalf("el id debe distinguir dispositivo, playbook y acción: %#v", distintos)
	}
	if got := HandoffID("Tablet Almacén/07", "soar-locate-unknown", action.Wipe); got != "ho-tablet-almac-n-07-soar-locate-unknown-wipe" {
		t.Fatalf("el id viaja en la URL: %q debe normalizarse a slug", got)
	}
}

// handoffPendiente es el handoff que abre el caso dorado.
func handoffPendiente() Handoff {
	return Handoff{
		ID:           HandoffID("dev-1", "soar-noncompliant-outside", action.Lock),
		DeviceID:     "dev-1",
		DeviceName:   "iPad kiosco",
		PlaybookID:   "soar-noncompliant-outside",
		PlaybookName: "No conforme y fuera de geocerca",
		Action:       action.Lock,
		Params:       map[string]any{"reason": "noncompliant_outside"},
		Reason:       "compliant, fence_state",
		Severity:     "high",
		Status:       HandoffPending,
		RequestedAt:  instante(),
	}
}

func TestFindPendingEncuentraElPendienteYLoIgnoraTrasAprobarlo(t *testing.T) {
	h := handoffPendiente()
	otro := handoffPendiente()
	otro.Action = action.Wipe
	otro.ID = HandoffID(otro.DeviceID, otro.PlaybookID, otro.Action)
	hs := []Handoff{otro, h}
	i, ok := FindPending(hs, "dev-1", "soar-noncompliant-outside", action.Lock)
	if !ok || i != 1 || hs[i].ID != h.ID {
		t.Fatalf("FindPending = %d, %v; quiero el índice del pendiente de lock", i, ok)
	}
	if _, ok := FindPending([]Handoff{h, otro}, "dev-1", "soar-noncompliant-outside", action.Lock); !ok {
		t.Fatal("FindPending no puede depender del orden de la lista")
	}
	if _, ok := FindPending(hs, "dev-9", "soar-noncompliant-outside", action.Lock); ok {
		t.Error("otro dispositivo no comparte handoff")
	}
	if _, ok := FindPending(hs, "dev-1", "soar-locate-unknown", action.Lock); ok {
		t.Error("otro playbook no comparte handoff")
	}
	aprobado, err := h.Decide(HandoffApproved, "ana@lucidfence.test", "aprobado en guardia", instante())
	if err != nil {
		t.Fatalf("aprobar el pendiente: %v", err)
	}
	hs = Upsert(hs, aprobado)
	if i, ok := FindPending(hs, "dev-1", "soar-noncompliant-outside", action.Lock); ok {
		t.Fatalf("un handoff aprobado deja de estar pendiente (índice %d)", i)
	}
}

// tablaDecide es la máquina de estados de §6.5 al completo.
var tablaDecide = []struct {
	nombre string
	desde  HandoffStatus
	hasta  HandoffStatus
	ok     bool
}{
	{"pendiente a aprobado", HandoffPending, HandoffApproved, true},
	{"pendiente a rechazado", HandoffPending, HandoffRejected, true},
	{"aprobado a ejecutado", HandoffApproved, HandoffExecuted, true},
	{"pendiente a ejecutado", HandoffPending, HandoffExecuted, false},
	{"pendiente a pendiente", HandoffPending, HandoffPending, false},
	{"aprobado a rechazado", HandoffApproved, HandoffRejected, false},
	{"aprobado a aprobado", HandoffApproved, HandoffApproved, false},
	{"rechazado a aprobado", HandoffRejected, HandoffApproved, false},
	{"rechazado a ejecutado", HandoffRejected, HandoffExecuted, false},
	{"ejecutado a aprobado", HandoffExecuted, HandoffApproved, false},
	{"ejecutado a rechazado", HandoffExecuted, HandoffRejected, false},
	{"ejecutado a ejecutado", HandoffExecuted, HandoffExecuted, false},
}

func TestDecideRecorreLaTablaCompleta(t *testing.T) {
	for _, c := range tablaDecide {
		h := handoffPendiente()
		h.Status = c.desde
		got, err := h.Decide(c.hasta, "ana@lucidfence.test", "", instante())
		if c.ok {
			if err != nil {
				t.Errorf("%s: debería permitirse, dio %v", c.nombre, err)
			} else if got.Status != c.hasta {
				t.Errorf("%s: estado %q, quiero %q", c.nombre, got.Status, c.hasta)
			}
			continue
		}
		if err == nil {
			t.Errorf("%s: debería fallar", c.nombre)
			continue
		}
		if !strings.Contains(err.Error(), "no se puede pasar") ||
			!strings.Contains(err.Error(), string(c.desde)) ||
			!strings.Contains(err.Error(), string(c.hasta)) {
			t.Errorf("%s: el error %q debe nombrar ambos estados en español", c.nombre, err)
		}
		if got.Status != c.desde {
			t.Errorf("%s: una transición rechazada no cambia el handoff: %q", c.nombre, got.Status)
		}
	}
}

func TestDecideSellaLaDecisionHumanaYNoLaPisaAlEjecutar(t *testing.T) {
	h := handoffPendiente()
	aprobado, err := h.Decide(HandoffApproved, "ana@lucidfence.test", "riesgo confirmado", instante())
	if err != nil {
		t.Fatalf("aprobar: %v", err)
	}
	if aprobado.DecidedAt == nil || !aprobado.DecidedAt.Equal(instante()) ||
		aprobado.DecidedBy != "ana@lucidfence.test" || aprobado.Note != "riesgo confirmado" {
		t.Fatalf("la aprobación debe sellar quién, cuándo y por qué: %#v", aprobado)
	}
	if h.Status != HandoffPending || h.DecidedAt != nil {
		t.Fatal("Decide no muta el handoff original")
	}
	aprobado.Params["reason"] = "mutado"
	if h.Params["reason"] != "noncompliant_outside" {
		t.Fatal("Decide debe copiar los params, no crear un alias")
	}
	despues := instante().Add(2 * time.Minute)
	ejecutado, err := aprobado.Decide(HandoffExecuted, "motor", "", despues)
	if err != nil {
		t.Fatalf("ejecutar: %v", err)
	}
	if ejecutado.DecidedBy != "ana@lucidfence.test" || !ejecutado.DecidedAt.Equal(instante()) {
		t.Fatalf("la ejecución no pisa la decisión humana: %#v", ejecutado)
	}
	if ejecutado.Note != "riesgo confirmado" {
		t.Errorf("una nota vacía no borra la anterior, dio %q", ejecutado.Note)
	}
}

func TestDecideRechazaUnEstadoFueraDelCatalogo(t *testing.T) {
	h := handoffPendiente()
	if _, err := h.Decide(HandoffStatus("cerrado"), "ana@lucidfence.test", "", instante()); err == nil ||
		!strings.Contains(err.Error(), `"cerrado"`) || !strings.Contains(err.Error(), "desconocido") {
		t.Fatalf("un estado fuera del catálogo debe fallar nombrándolo, dio: %v", err)
	}
	roto := handoffPendiente()
	roto.Status = HandoffStatus("zombi")
	if _, err := roto.Decide(HandoffApproved, "ana@lucidfence.test", "", instante()); err == nil ||
		!strings.Contains(err.Error(), "zombi") {
		t.Fatalf("un handoff en un estado no reconocido no se decide, dio: %v", err)
	}
	if len(HandoffStatuses) != 4 {
		t.Fatalf("HandoffStatuses tiene %d estados, quiero los 4 de §6.5", len(HandoffStatuses))
	}
}

func TestUpsertReemplazaPorIDSinDuplicar(t *testing.T) {
	a := handoffPendiente()
	b := handoffPendiente()
	b.Action = action.Wipe
	b.ID = HandoffID(b.DeviceID, b.PlaybookID, b.Action)
	hs := Upsert(Upsert(nil, a), b)
	if len(hs) != 2 || hs[0].ID != a.ID || hs[1].ID != b.ID {
		t.Fatalf("Upsert añade conservando el orden: %#v", hs)
	}
	rechazado, err := a.Decide(HandoffRejected, "ana@lucidfence.test", "falso positivo", instante())
	if err != nil {
		t.Fatalf("rechazar: %v", err)
	}
	out := Upsert(hs, rechazado)
	if len(out) != 2 {
		t.Fatalf("Upsert no duplica por id: %#v", out)
	}
	if out[0].Status != HandoffRejected || out[0].Note != "falso positivo" || out[1].ID != b.ID {
		t.Fatalf("Upsert reemplaza en su sitio: %#v", out)
	}
	if hs[0].Status != HandoffPending {
		t.Fatal("Upsert devuelve una lista nueva, no muta la recibida")
	}
}
