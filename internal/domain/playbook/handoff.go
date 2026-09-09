// Handoffs: el gate humano de las acciones destructivas (spec §6.5). Ninguna
// acción destructiva de un playbook llega al adapter sin un handoff aprobado.
package playbook

import (
	"fmt"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

// HandoffStatus es el estado del gate humano.
type HandoffStatus string

const (
	HandoffPending  HandoffStatus = "pending"
	HandoffApproved HandoffStatus = "approved"
	HandoffRejected HandoffStatus = "rejected"
	HandoffExecuted HandoffStatus = "executed"
)

// HandoffStatuses enumera los estados válidos en orden estable.
var HandoffStatuses = []HandoffStatus{HandoffPending, HandoffApproved, HandoffRejected, HandoffExecuted}

// Handoff es una acción destructiva a la espera de decisión humana.
type Handoff struct {
	ID           string         `json:"id"`
	DeviceID     string         `json:"device_id"`
	DeviceName   string         `json:"device_name"`
	PlaybookID   string         `json:"playbook_id"`
	PlaybookName string         `json:"playbook_name"`
	Action       action.Action  `json:"action"`
	Params       map[string]any `json:"params,omitempty"`
	Reason       string         `json:"reason"`
	Severity     string         `json:"severity"`
	Status       HandoffStatus  `json:"status"`
	RequestedAt  time.Time      `json:"requested_at"`
	DecidedAt    *time.Time     `json:"decided_at,omitempty"`
	DecidedBy    string         `json:"decided_by,omitempty"`
	Note         string         `json:"note,omitempty"`
	Result       *action.Result `json:"result,omitempty"`
}

// RequiresHandoff delega en action.Action.Destructive() para que "destructivo"
// tenga una sola definición en el repo: lock, wipe, clear_passcode y reboot.
func RequiresHandoff(a action.Action) bool {
	return a.Destructive()
}

// HandoffID es determinista por dispositivo, playbook y acción, y no depende
// del orden de la lista: mientras el handoff siga pendiente, el mismo ciclo no
// crea un segundo. El id viaja en /api/v1/handoffs/{id}/approve, así que cada
// parte se normaliza a slug.
func HandoffID(deviceID, playbookID string, a action.Action) string {
	return "ho-" + slug(deviceID) + "-" + slug(playbookID) + "-" + slug(string(a))
}

// slug deja minúsculas, dígitos y guiones; cualquier otra runa se convierte en
// un guion y las repeticiones se colapsan.
func slug(s string) string {
	var b strings.Builder
	guion := false
	for _, r := range strings.ToLower(strings.TrimSpace(s)) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
			guion = false
			continue
		}
		if !guion && b.Len() > 0 {
			b.WriteByte('-')
			guion = true
		}
	}
	return strings.Trim(b.String(), "-")
}

// FindPending devuelve el índice del handoff pendiente de este dispositivo,
// playbook y acción. Un handoff ya decidido deja de bloquear: si el motivo
// vuelve a darse, el ciclo abre uno nuevo.
func FindPending(hs []Handoff, deviceID, playbookID string, a action.Action) (int, bool) {
	for i, h := range hs {
		if h.Status == HandoffPending && h.DeviceID == deviceID && h.PlaybookID == playbookID && h.Action == a {
			return i, true
		}
	}
	return -1, false
}

// allowed es la máquina de estados: de pending solo se sale a approved o
// rejected; de approved solo a executed; rejected y executed son terminales.
var allowed = map[HandoffStatus][]HandoffStatus{
	HandoffPending:  {HandoffApproved, HandoffRejected},
	HandoffApproved: {HandoffExecuted},
	HandoffRejected: {},
	HandoffExecuted: {},
}

// Decide aplica una transición y devuelve el handoff resultante sin mutar el
// original. approved y rejected sellan la decisión humana (quién y cuándo);
// executed no la pisa, porque el instante de la ejecución vive en el Result.
func (h Handoff) Decide(to HandoffStatus, by, note string, at time.Time) (Handoff, error) {
	if !validStatus(to) {
		return h, fmt.Errorf("estado de handoff desconocido %q (usa %s)", to, statusesHint())
	}
	siguientes, ok := allowed[h.Status]
	if !ok {
		return h, fmt.Errorf("handoff %q en estado desconocido %q", h.ID, h.Status)
	}
	if !contiene(siguientes, to) {
		return h, fmt.Errorf("handoff %q: no se puede pasar de %q a %q", h.ID, h.Status, to)
	}
	out := h
	out.Params = cloneParams(h.Params)
	out.Status = to
	if note != "" {
		out.Note = note
	}
	if to == HandoffApproved || to == HandoffRejected {
		decidido := at
		out.DecidedAt = &decidido
		out.DecidedBy = by
	}
	return out, nil
}

func validStatus(s HandoffStatus) bool {
	return contiene(HandoffStatuses, s)
}

func contiene(ss []HandoffStatus, s HandoffStatus) bool {
	for _, v := range ss {
		if v == s {
			return true
		}
	}
	return false
}

func statusesHint() string {
	names := make([]string, len(HandoffStatuses))
	for i, s := range HandoffStatuses {
		names[i] = string(s)
	}
	return strings.Join(names, "|")
}

// Upsert reemplaza por id sin duplicar, conserva el orden y devuelve una lista
// nueva: la recibida no se muta.
func Upsert(hs []Handoff, h Handoff) []Handoff {
	out := make([]Handoff, 0, len(hs)+1)
	sustituido := false
	for _, cur := range hs {
		if cur.ID == h.ID {
			out = append(out, h)
			sustituido = true
			continue
		}
		out = append(out, cur)
	}
	if !sustituido {
		out = append(out, h)
	}
	return out
}
