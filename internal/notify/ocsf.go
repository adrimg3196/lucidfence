package notify

// Serialización a OCSF Detection Finding (class_uid 2004). Puerto de
// legacy/lucidfence/core/ocsf.py: función pura, sin red, sin disco y sin
// estado, construida con lista blanca de campos para que la superficie de
// datos no pueda crecer por accidente (spec §6.4). El comentario va aquí y no
// sobre la cláusula package porque el doc del paquete vive en notify.go.

import (
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
)

// Identificadores de la clase y versión del esquema que declaramos, para que el
// receptor sepa contra qué validar en vez de adivinarlo.
const (
	OCSFCategoryUID   = 2
	OCSFClassUID      = 2004
	OCSFSchemaVersion = "1.3.0"
)

const (
	transitionOpen   = "open"
	transitionAck    = "ack"
	transitionClosed = "closed"
)

// severityIDs mapea 1:1 la escala del producto sobre la de OCSF. El 6 Fatal
// queda sin usar a propósito: LucidFence no tiene nada por encima de critical y
// estirar la escala exageraría el veredicto en el panel del SOC.
var severityIDs = map[string]int{"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}

var severityNames = map[int]string{0: "Unknown", 1: "Informational", 2: "Low", 3: "Medium", 4: "High", 5: "Critical"}

type ocsfPair struct {
	id   int
	name string
}

var activities = map[string]ocsfPair{
	transitionOpen:   {1, "Create"},
	transitionAck:    {2, "Update"},
	transitionClosed: {3, "Close"},
}

var ocsfStatuses = map[string]ocsfPair{
	transitionOpen:   {1, "New"},
	transitionAck:    {2, "In Progress"},
	transitionClosed: {4, "Resolved"},
}

// SeverityID traduce la severidad del producto. Lo que no se reconoce (incluido
// el "unknown" que emite el evaluador de riesgo cuando falla) es 0 Unknown,
// NUNCA 1 Informational.
func SeverityID(severity string) int {
	return severityIDs[strings.ToLower(strings.TrimSpace(severity))]
}

// transitionOf deriva la transición del ciclo de vida: del estado del incidente
// cuando lo hay y, si no, del tipo de evento.
func transitionOf(ev Event) string {
	if ev.Incident != nil {
		switch ev.Incident.Status {
		case incident.StatusOpen:
			return transitionOpen
		case incident.StatusAck:
			return transitionAck
		case incident.StatusClosed:
			return transitionClosed
		}
	}
	switch ev.Kind {
	case EventIncidentOpened, EventAlertFired:
		return transitionOpen
	case EventIncidentClosed:
		return transitionClosed
	case EventHandoffPending, EventActionExecuted:
		return transitionAck
	}
	return ev.Kind
}

func epochMS(t time.Time) (int64, bool) {
	if t.IsZero() {
		return 0, false
	}
	return t.UTC().UnixMilli(), true
}

func nonEmpty(s string) []string {
	if s == "" {
		return nil
	}
	return []string{s}
}

func findingUID(ev Event) string {
	switch {
	case ev.Incident != nil:
		return ev.Incident.ID
	case ev.Handoff != nil:
		return ev.Handoff.ID
	case ev.Action != nil:
		if ev.Action.CommandID != "" {
			return ev.Action.CommandID
		}
	case ev.Firing != nil:
		return ev.Firing.RuleID
	}
	return ev.DeliveryID
}

func ocsfMetadata(ev Event) map[string]any {
	md := map[string]any{
		"version": OCSFSchemaVersion,
		"product": map[string]any{"vendor_name": Product, "name": Product},
	}
	put(md, "uid", ev.DeliveryID)
	put(md, "event_code", ev.Kind)
	return md
}

func ocsfFindingInfo(ev Event, title string) map[string]any {
	fi := map[string]any{"uid": findingUID(ev), "title": title}
	if ev.Incident == nil {
		put(fi, "types", nonEmpty(ev.Kind))
		return fi
	}
	put(fi, "desc", ev.Incident.Recommendation)
	put(fi, "types", nonEmpty(ev.Incident.Kind))
	if ms, ok := epochMS(ev.Incident.OpenedAt); ok {
		fi["first_seen_time"] = ms
	}
	if ms, ok := epochMS(ev.Incident.UpdatedAt); ok {
		fi["last_seen_time"] = ms
	}
	return fi
}

// unmapped es la lista blanca de lo que es de LucidFence y no tiene equivalente
// en el esquema. Nada fuera de aquí sale, y ninguna rama nombra lat, lng ni
// location: por eso el invariante de privacidad es estructural.
func ocsfUnmapped(ev Event) map[string]any {
	m := map[string]any{}
	put(m, "event", ev.Kind)
	switch {
	case ev.Incident != nil:
		unmappedIncident(m, ev.Incident)
	case ev.Handoff != nil:
		unmappedHandoff(m, ev.Handoff)
	case ev.Action != nil:
		unmappedAction(m, ev.Action)
	case ev.Firing != nil:
		unmappedFiring(m, ev.Firing)
	}
	return m
}

func unmappedIncident(m map[string]any, i *incident.Incident) {
	put(m, "type", i.Kind)
	put(m, "fence_id", i.FenceID)
	put(m, "risk_score", i.RiskScore)
	put(m, "assignee", i.Assignee)
	put(m, "incident_status", string(i.Status))
}

func unmappedHandoff(m map[string]any, h *playbook.Handoff) {
	put(m, "action", string(h.Action))
	put(m, "handoff_status", string(h.Status))
	put(m, "playbook_id", h.PlaybookID)
	put(m, "reason", h.Reason)
}

func unmappedAction(m map[string]any, r *action.Result) {
	m["ok"] = r.OK
	m["dry_run"] = r.DryRun
	if r.Blocked {
		m["blocked"] = true
	}
	put(m, "action", string(r.Action))
	put(m, "adapter", r.Adapter)
	put(m, "trigger", r.Trigger)
	put(m, "policy_id", r.PolicyID)
	put(m, "playbook_id", r.PlaybookID)
	put(m, "route_id", r.RouteID)
	put(m, "fence_id", r.FenceID)
	put(m, "error_type", r.ErrorType)
}

func unmappedFiring(m map[string]any, f *alert.Firing) {
	m["value"] = f.Value
	put(m, "rule_id", f.RuleID)
	put(m, "alert_kind", string(f.Kind))
	put(m, "reason", f.Reason)
}

// DetectionFinding construye el evento OCSF completo.
func DetectionFinding(ev Event) map[string]any {
	tr := transitionOf(ev)
	act, ok := activities[tr]
	if !ok {
		act = ocsfPair{99, "Other"}
		if tr != "" {
			act.name = tr
		}
	}
	st, ok := ocsfStatuses[tr]
	if !ok {
		st = ocsfPair{0, "Unknown"}
	}
	sevID := SeverityID(ev.Severity())
	title := ev.Title()
	out := map[string]any{
		"activity_id": act.id, "activity_name": act.name,
		"category_uid": OCSFCategoryUID, "category_name": "Findings",
		"class_uid": OCSFClassUID, "class_name": "Detection Finding",
		"type_uid":    OCSFClassUID*100 + act.id,
		"type_name":   "Detection Finding: " + act.name,
		"severity_id": sevID, "severity": severityNames[sevID],
		"status_id": st.id, "status": st.name,
		"message":      title,
		"metadata":     ocsfMetadata(ev),
		"finding_info": ocsfFindingInfo(ev, title),
	}
	// La marca es la de la condición observada; si no la hay, el hallazgo viaja
	// sin `time` en vez de con una inventada.
	if ms, ok := epochMS(ev.At); ok {
		out["time"] = ms
	}
	// El dispositivo viaja como recurso: identidad, nunca ubicación.
	if id, name := ev.device(); id != "" {
		out["resources"] = []any{map[string]any{"uid": id, "name": name, "type": "device"}}
	}
	if ev.Incident != nil && ev.Incident.Count > 0 {
		out["count"] = ev.Incident.Count
	}
	if um := ocsfUnmapped(ev); len(um) > 0 {
		out["unmapped"] = um
	}
	return out
}

// OCSFPayload serializa el hallazgo desnudo, sin el sobre nativo.
func OCSFPayload(ev Event) ([]byte, error) {
	return marshalCanonical(DetectionFinding(ev))
}
