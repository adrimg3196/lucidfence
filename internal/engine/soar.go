package engine

import (
	"fmt"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/notify"
)

// Triggers de las órdenes que no nacen de una geocerca ni de una ruta.
// TriggerPlaybook marca la acción no destructiva que pide un playbook;
// TriggerHandoff, la destructiva que una persona ya aprobó; TriggerManual, la
// que un operador lanza desde el detalle del dispositivo. Los tres viajan en
// action.Result.Trigger y el registro de acciones (T26) los enseña tal cual.
const (
	TriggerPlaybook = "playbook"
	TriggerHandoff  = "handoff"
	TriggerManual   = "manual"
)

// HandoffReopenAfter es lo que tarda el motor en volver a pedir una acción
// destructiva ya decidida para el mismo dispositivo, playbook y acción.
// FindPending solo bloquea mientras la petición sigue pendiente, así que sin
// esta espera un rechazo se reabriría en el ciclo siguiente y el SOC recibiría
// un handoff.pending cada quince minutos por algo que ya contestó. Mientras
// corre, la bandeja conserva la decisión humana; pasada, la petición vuelve,
// porque una condición peligrosa sin resolver tiene que seguir preguntando.
const HandoffReopenAfter = 24 * time.Hour

// evaluatePlaybooks es el paso 7 del ciclo (spec §6.5). Reparte las acciones
// de los playbooks que casan con el sujeto en dos montones: las no
// destructivas salen como Planned y pasan por los mismos guardarraíles que
// todo lo demás; las destructivas NO se ejecutan nunca aquí, abren un handoff
// pendiente con el id determinista de playbook.HandoffID.
//
// El sujeto es el mismo que evaluaron las políticas (subjectFor, T14): un
// playbook y una política ven exactamente el mismo dispositivo. Un dispositivo
// cuya evaluación falló no dispara ninguno: sin veredicto no hay evidencia.
//
// Los handoffs abiertos se devuelven (es lo que comprueban los tests) y además
// quedan en la bandeja del ciclo, que es de donde salen la persistencia y los
// avisos al final de runCycle.
func (e *Engine) evaluatePlaybooks(cur device.Device, subject policy.Subject,
	pbs []playbook.Playbook, now time.Time) (planned []Planned, handoffs []playbook.Handoff) {
	if cur.EvaluationError != "" {
		return nil, nil
	}
	for _, m := range playbook.MatchAll(pbs, subject) {
		for _, a := range m.Actions {
			if !playbook.RequiresHandoff(a.Action) {
				planned = append(planned, Planned{Device: cur, Action: a.Action, Params: a.Params,
					FenceID: cur.InsideFence, PlaybookID: m.PlaybookID,
					Trigger: TriggerPlaybook, Severity: m.Severity})
				continue
			}
			if h, ok := e.openHandoff(cur, subject, m, a, now); ok {
				handoffs = append(handoffs, h)
			}
		}
	}
	return planned, handoffs
}

// openHandoff abre la petición humana de una acción destructiva. Devuelve
// false cuando no hay nada que abrir: es la invariante "uno por dispositivo,
// acción y playbook mientras siga pendiente" de §6.5.
func (e *Engine) openHandoff(cur device.Device, s policy.Subject, m playbook.Match,
	a policy.Action, now time.Time) (playbook.Handoff, bool) {
	if !e.reopens(cur.ID, m.PlaybookID, a.Action, now) {
		return playbook.Handoff{}, false
	}
	h := playbook.Handoff{
		ID:           playbook.HandoffID(cur.ID, m.PlaybookID, a.Action),
		DeviceID:     cur.ID,
		DeviceName:   cur.Name,
		PlaybookID:   m.PlaybookID,
		PlaybookName: m.Name,
		Action:       a.Action,
		Params:       a.Params,
		Reason:       handoffReason(s, m.MatchedFields),
		Severity:     m.Severity,
		Status:       playbook.HandoffPending,
		RequestedAt:  now,
	}
	e.handoffs = playbook.Upsert(e.handoffs, h)
	e.opened = append(e.opened, h)
	e.opts.Logger.Info("handoff pendiente", "device", cur.ID, "playbook", m.PlaybookID,
		"action", a.Action, "handoff", h.ID)
	return h, true
}

// reopens dice si procede abrir la petición. Una pendiente bloquea siempre;
// una ya decidida bloquea hasta HandoffReopenAfter después de la decisión.
func (e *Engine) reopens(deviceID, playbookID string, a action.Action, now time.Time) bool {
	if _, pending := playbook.FindPending(e.handoffs, deviceID, playbookID, a); pending {
		return false
	}
	id := playbook.HandoffID(deviceID, playbookID, a)
	for _, h := range e.handoffs {
		if h.ID != id || h.DecidedAt == nil {
			continue
		}
		return now.Sub(*h.DecidedAt) >= HandoffReopenAfter
	}
	return true
}

// handoffReason explica en una línea por qué se pide la acción: los campos que
// casaron (playbook.Match.MatchedFields, el c7n:MatchedFilters de 1.x) con el
// valor que tenían en este ciclo. Es lo que lee el aprobador antes de decidir,
// y por eso lleva el valor y no solo el nombre del campo.
func handoffReason(s policy.Subject, fields []string) string {
	parts := make([]string, 0, len(fields))
	for _, f := range fields {
		v, ok := policy.Resolve(s, f)
		if !ok {
			parts = append(parts, f+"=(sin valor)")
			continue
		}
		parts = append(parts, fmt.Sprintf("%s=%v", f, v))
	}
	return strings.Join(parts, ", ")
}

// soar es lo que llama el ciclo: evalúa los playbooks del dispositivo y
// devuelve solo las órdenes que sí se ejecutan. Los handoffs ya quedaron
// apuntados en la bandeja del ciclo, así que processDevice no tiene que
// enterarse de ellos.
func (e *Engine) soar(in cycleInput, cur device.Device, now time.Time) []Planned {
	planned, _ := e.evaluatePlaybooks(cur, subjectFor(cur), in.playbooks, now)
	return planned
}

// startHandoffs abre la bandeja del ciclo: la lista que evaluatePlaybooks
// consulta para no duplicar y el montón de las que este ciclo abra.
func (e *Engine) startHandoffs(hs []playbook.Handoff) {
	e.handoffs, e.opened = hs, nil
}

// persistHandoffs guarda la bandeja al final del ciclo y deja en el resumen
// cuántas peticiones esperan a una persona. Vuelve a leer handoffs.json bajo
// manualMu y aplica solo las que este ciclo ha abierto: si un aprobador
// decidió una mientras el ciclo recorría la flota, su decisión no se pisa. Un
// fallo aquí no aborta el ciclo (M1-R11).
func (e *Engine) persistHandoffs(st *CycleStats) {
	if len(e.opened) == 0 {
		st.HandoffsPending = countPending(e.handoffs)
		return
	}
	e.manualMu.Lock()
	defer e.manualMu.Unlock()
	hs, err := e.org.Handoffs()
	if err != nil {
		e.logPersistenceError(st, "handoffs", "", err)
		st.HandoffsPending = countPending(e.handoffs)
		return
	}
	for _, h := range e.opened {
		hs = playbook.Upsert(hs, h)
	}
	if err := e.org.SaveHandoffs(hs); err != nil {
		e.logPersistenceError(st, "handoffs", "", err)
	}
	st.HandoffsPending = countPending(hs)
}

// countPending cuenta las peticiones que esperan decisión humana.
func countPending(hs []playbook.Handoff) int {
	n := 0
	for _, h := range hs {
		if h.Status == playbook.HandoffPending {
			n++
		}
	}
	return n
}

// handoffEvents anuncia por el notificador las peticiones que este ciclo ha
// abierto. Solo las nuevas: una pendiente que sigue pendiente ya está delante
// del operador y repetir el aviso con el mismo id sería ruido.
func (e *Engine) handoffEvents() []notify.Event {
	evs := make([]notify.Event, 0, len(e.opened))
	for _, h := range e.opened {
		ho := h
		evs = append(evs, notify.Event{Kind: notify.EventHandoffPending, At: ho.RequestedAt, Handoff: &ho})
	}
	return evs
}
