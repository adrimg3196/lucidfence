package notify

import (
	"log/slog"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
)

// Cabeceras de una entrega de webhook. La firma cubre solo el cuerpo y es
// compatible bit a bit con la de 1.x (legacy/lucidfence/core/notifier.py).
const (
	SignatureHeader = "X-LucidFence-Signature"
	EventHeader     = "X-LucidFence-Event"
	DeliveryHeader  = "X-LucidFence-Delivery"
	TimestampHeader = "X-LucidFence-Timestamp"
)

// Los cinco eventos que publica el producto; el mismo enum que
// settings.WebhookEvents, que es lo que el tenant marca en Ajustes.
const (
	EventIncidentOpened = "incident.opened"
	EventIncidentClosed = "incident.closed"
	EventHandoffPending = "handoff.pending"
	EventActionExecuted = "action.executed"
	EventAlertFired     = "alert.fired"
)

// Product identifica al emisor en el sobre nativo y en metadata.product de OCSF.
const Product = "LucidFence"

// SeverityUnknown es la severidad de un evento que no declara ninguna. No es
// "info": presentar lo desconocido como benigno es el falso verde prohibido.
const SeverityUnknown = "unknown"

// NoDevice sustituye al nombre del dispositivo cuando el evento no señala uno.
const NoDevice = "sin dispositivo"

// Event es lo que el motor entrega a los canales. Exactamente uno de los cuatro
// punteros está relleno; el resto son nil.
type Event struct {
	Kind       string
	At         time.Time
	DeliveryID string
	Incident   *incident.Incident
	Handoff    *playbook.Handoff
	Action     *action.Result
	Firing     *alert.Firing
}

// verbs traduce el tipo de evento al verbo del titular, en español.
var verbs = map[string]string{
	EventIncidentOpened: "nuevo incidente",
	EventIncidentClosed: "incidente resuelto",
	EventHandoffPending: "aprobación pendiente",
	EventActionExecuted: "acción ejecutada",
	EventAlertFired:     "alerta disparada",
}

// Severity devuelve la severidad declarada por la fuente del evento, en
// minúsculas, o SeverityUnknown si ninguna la declara.
func (e Event) Severity() string {
	switch {
	case e.Incident != nil && e.Incident.Severity != "":
		return strings.ToLower(e.Incident.Severity)
	case e.Handoff != nil && e.Handoff.Severity != "":
		return strings.ToLower(e.Handoff.Severity)
	case e.Action != nil && e.Action.Severity != "":
		return strings.ToLower(e.Action.Severity)
	case e.Firing != nil && e.Firing.Severity != "":
		return strings.ToLower(e.Firing.Severity)
	}
	return SeverityUnknown
}

// device devuelve el identificador y el nombre del dispositivo afectado.
func (e Event) device() (id, name string) {
	switch {
	case e.Incident != nil:
		id, name = e.Incident.DeviceID, e.Incident.DeviceName
	case e.Handoff != nil:
		id, name = e.Handoff.DeviceID, e.Handoff.DeviceName
	case e.Action != nil:
		id, name = e.Action.DeviceID, e.Action.DeviceName
	case e.Firing != nil:
		id, name = e.Firing.DeviceID, e.Firing.DeviceName
	}
	if name == "" {
		name = id
	}
	return id, name
}

// verb es el verbo del titular; un tipo de evento desconocido se entrega con su
// propio nombre en lugar de callarse.
func (e Event) verb() string {
	if v, ok := verbs[e.Kind]; ok {
		return v
	}
	if e.Kind != "" {
		return e.Kind
	}
	return "evento"
}

// subject describe el hecho concreto, sin ubicación ni parámetros.
func (e Event) subject() string {
	switch {
	case e.Incident != nil:
		if e.Incident.Title != "" {
			return e.Incident.Title
		}
		return e.Incident.ID
	case e.Handoff != nil:
		nombre := e.Handoff.PlaybookName
		if nombre == "" {
			nombre = e.Handoff.PlaybookID
		}
		return nombre + " requiere " + string(e.Handoff.Action)
	case e.Action != nil:
		return e.actionSubject()
	case e.Firing != nil:
		if e.Firing.RuleName != "" {
			return e.Firing.RuleName
		}
		return e.Firing.RuleID
	}
	return e.verb()
}

func (e Event) actionSubject() string {
	s := string(e.Action.Action) + " fallida"
	if e.Action.OK {
		s = string(e.Action.Action) + " ejecutada"
	}
	if e.Action.DryRun {
		s += " en dry-run"
	}
	return s
}

// Title es el titular legible: "[SEVERIDAD] verbo: asunto (dispositivo)", la
// misma forma que el canal Slack de 1.x.
func (e Event) Title() string {
	_, nombre := e.device()
	if nombre == "" {
		nombre = NoDevice
	}
	return "[" + strings.ToUpper(e.Severity()) + "] " + e.verb() + ": " + e.subject() + " (" + nombre + ")"
}

// LogValue fija lo que el paquete registra de un evento: identidad de la
// entrega, nunca cuerpos, secretos ni la ruta del destino (spec §7).
func (e Event) LogValue() slog.Value {
	id, _ := e.device()
	return slog.GroupValue(
		slog.String("event", e.Kind),
		slog.String("delivery", e.DeliveryID),
		slog.String("severity", e.Severity()),
		slog.String("device_id", id),
	)
}
