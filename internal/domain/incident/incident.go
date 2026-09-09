// Package incident modela los incidentes operativos: los hechos que el ciclo
// deriva de la flota (qué está mal ahora) y la capa humana que se apila encima
// (reconocer, asignar, cerrar) con auditoría. Sin I/O: el motor deriva, el
// store persiste, la API expone.
package incident

import (
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// Status es el estado operativo del incidente.
type Status string

const (
	StatusOpen   Status = "open"
	StatusAck    Status = "ack"
	StatusClosed Status = "closed"
)

// Statuses enumera los estados válidos en orden de flujo.
var Statuses = []Status{StatusOpen, StatusAck, StatusClosed}

// Tipos de incidente que Derive sabe producir.
const (
	KindNonCompliant      = "device_non_compliant"
	KindGeofenceExit      = "geofence_exit"
	KindUnknownLocation   = "device_unknown_location"
	KindHighRisk          = "high_risk_device"
	KindRouteDeviation    = "route_deviation"
	KindLocationIntegrity = "location_integrity"
	KindActionFailed      = "automation_failed"
)

// Kinds enumera los tipos en orden estable (paneles y filtros).
var Kinds = []string{
	KindNonCompliant, KindGeofenceExit, KindUnknownLocation, KindHighRisk,
	KindRouteDeviation, KindLocationIntegrity, KindActionFailed,
}

// ActorSystem firma las entradas de auditoría que escribe el motor, para que
// nunca se confundan con una decisión humana.
const ActorSystem = "sistema"

var (
	// ErrInvalidStatus indica un estado destino fuera de Statuses.
	ErrInvalidStatus = errors.New("estado de incidente inválido")
	// ErrSameStatus indica una transición al estado que ya tenía: no
	// transiciona nada y solo ensuciaría la auditoría.
	ErrSameStatus = errors.New("el incidente ya está en ese estado")
)

// Entry es una entrada de la auditoría del incidente.
type Entry struct {
	At    time.Time `json:"at"`
	Actor string    `json:"actor"`
	From  string    `json:"from"`
	To    string    `json:"to"`
	Note  string    `json:"note"`
}

// Incident es un problema abierto sobre un dispositivo. Los campos derivados
// (tipo, severidad, título, evidencias) los refresca cada ciclo; los operativos
// (estado, asignación, sellos, auditoría) solo cambian por Transition o por el
// cierre automático de Merge.
type Incident struct {
	ID             string     `json:"id"`
	DeviceID       string     `json:"device_id"`
	DeviceName     string     `json:"device_name"`
	Kind           string     `json:"kind"`
	Severity       string     `json:"severity"`
	Title          string     `json:"title"`
	Recommendation string     `json:"recommendation"`
	FenceID        string     `json:"fence_id,omitempty"`
	Assignee       string     `json:"assignee,omitempty"`
	Status         Status     `json:"status"`
	RiskScore      *float64   `json:"risk_score"`
	Count          int        `json:"count"`
	Evidence       []string   `json:"evidence"`
	OpenedAt       time.Time  `json:"opened_at"`
	UpdatedAt      time.Time  `json:"updated_at"`
	AckedAt        *time.Time `json:"acked_at,omitempty"`
	ClosedAt       *time.Time `json:"closed_at,omitempty"`
	Timeline       []Entry    `json:"timeline"`
}

// FindByID busca por id.
func FindByID(is []Incident, id string) (Incident, bool) {
	for _, inc := range is {
		if inc.ID == id {
			return inc, true
		}
	}
	return Incident{}, false
}

// Transition mueve el incidente a otro estado, sella la marca correspondiente
// y añade la entrada de auditoría. Devuelve una copia: el original no se muta.
func (i Incident) Transition(to Status, actor, assignee, note string, at time.Time) (Incident, error) {
	if !validStatus(to) {
		return Incident{}, fmt.Errorf("%w: %q", ErrInvalidStatus, string(to))
	}
	if i.Status == to {
		return Incident{}, fmt.Errorf("%w: %s", ErrSameStatus, string(to))
	}
	out := i.clone()
	from := string(i.Status)
	if from == "" {
		from = string(StatusOpen)
	}
	out.Status = to
	out.UpdatedAt = at
	if a := strings.TrimSpace(assignee); a != "" {
		out.Assignee = a
	}
	stamp := at
	switch to {
	case StatusOpen:
		out.AckedAt, out.ClosedAt = nil, nil
	case StatusAck:
		out.AckedAt, out.ClosedAt = &stamp, nil
	case StatusClosed:
		out.ClosedAt = &stamp
	}
	out.Timeline = append(out.Timeline, Entry{
		At: at, Actor: strings.TrimSpace(actor), From: from, To: string(to),
		Note: strings.TrimSpace(note),
	})
	return out, nil
}

// Merge cruza lo persistido con lo que el ciclo acaba de derivar. Refresca los
// hechos conservando el estado operativo, abre los que no existían, cierra solo
// los abiertos cuya condición ha desaparecido y deja intactos los ya cerrados
// (un cerrado no se reabre solo: eso sería un bucle abrir/cerrar eterno sobre
// una condición permanente). Devuelve la lista completa ordenada más las de
// aperturas y cierres para que el motor sepa qué notificar.
func Merge(stored, derived []Incident, at time.Time) (merged, opened, closed []Incident) {
	byID := make(map[string]Incident, len(stored)+len(derived))
	order := make([]string, 0, len(stored)+len(derived))
	for _, s := range stored {
		if s.ID == "" {
			continue
		}
		if _, dup := byID[s.ID]; dup {
			continue
		}
		byID[s.ID] = s
		order = append(order, s.ID)
	}
	seen := make(map[string]bool, len(derived))
	for _, d := range derived {
		if d.ID == "" || seen[d.ID] {
			continue
		}
		seen[d.ID] = true
		prev, known := byID[d.ID]
		if !known {
			fresh := open(d, at)
			byID[d.ID] = fresh
			order = append(order, d.ID)
			opened = append(opened, fresh)
			continue
		}
		byID[d.ID] = refresh(prev, d, at)
	}
	merged = make([]Incident, 0, len(order))
	for _, id := range order {
		cur := byID[id]
		if !seen[id] && cur.Status != StatusClosed {
			cur = autoClose(cur, at)
			closed = append(closed, cur)
		}
		merged = append(merged, cur)
	}
	sortIncidents(merged)
	return merged, opened, closed
}

// open normaliza un incidente recién derivado.
func open(derived Incident, at time.Time) Incident {
	out := derived.clone()
	out.Status = StatusOpen
	out.AckedAt, out.ClosedAt = nil, nil
	out.UpdatedAt = at
	if out.OpenedAt.IsZero() {
		out.OpenedAt = at
	}
	if out.Count < 1 {
		out.Count = 1
	}
	return out
}

// refresh actualiza los hechos derivados y preserva el estado operativo.
// Count cuenta los ciclos en los que la condición se ha vuelto a observar.
func refresh(stored, derived Incident, at time.Time) Incident {
	out := stored.clone()
	out.DeviceID, out.DeviceName = derived.DeviceID, derived.DeviceName
	out.Kind, out.Severity = derived.Kind, derived.Severity
	out.Title, out.Recommendation = derived.Title, derived.Recommendation
	out.FenceID = derived.FenceID
	out.RiskScore = copyScore(derived.RiskScore)
	out.Evidence = append(make([]string, 0, len(derived.Evidence)), derived.Evidence...)
	out.Count = stored.Count + 1
	out.UpdatedAt = at
	return out
}

// autoClose cierra el incidente cuya condición ha dejado de observarse y lo
// deja escrito en la auditoría, para que nadie crea que lo cerró una persona.
func autoClose(in Incident, at time.Time) Incident {
	out := in.clone()
	from := string(out.Status)
	if from == "" {
		from = string(StatusOpen)
	}
	stamp := at
	out.Status = StatusClosed
	out.ClosedAt = &stamp
	out.UpdatedAt = at
	out.Timeline = append(out.Timeline, Entry{
		At: at, Actor: ActorSystem, From: from, To: string(StatusClosed),
		Note: "la condición dejó de observarse en el ciclo",
	})
	return out
}

// sortIncidents ordena por estado, severidad, título e id: orden total y
// estable, para que dos ciclos idénticos produzcan el mismo JSON.
func sortIncidents(is []Incident) {
	sort.SliceStable(is, func(a, b int) bool {
		x, y := is[a], is[b]
		if ra, rb := statusRank(x.Status), statusRank(y.Status); ra != rb {
			return ra < rb
		}
		if ra, rb := severityRank(x.Severity), severityRank(y.Severity); ra != rb {
			return ra < rb
		}
		if x.Title != y.Title {
			return x.Title < y.Title
		}
		return x.ID < y.ID
	})
}

func validStatus(s Status) bool {
	for _, v := range Statuses {
		if v == s {
			return true
		}
	}
	return false
}

func statusRank(s Status) int {
	for i, v := range Statuses {
		if v == s {
			return i
		}
	}
	return len(Statuses)
}

// severityRank ordena de más grave a menos con el catálogo de risk. Lo
// desconocido va detrás de todo lo conocido, nunca delante y nunca mezclado.
func severityRank(s string) int {
	for i, name := range risk.Severities {
		if name == s {
			return len(risk.Severities) - 1 - i
		}
	}
	if s == risk.SeverityUnknown {
		return len(risk.Severities)
	}
	return len(risk.Severities) + 1
}

func (i Incident) clone() Incident {
	out := i
	out.RiskScore = copyScore(i.RiskScore)
	out.AckedAt = copyStamp(i.AckedAt)
	out.ClosedAt = copyStamp(i.ClosedAt)
	out.Evidence = append(make([]string, 0, len(i.Evidence)), i.Evidence...)
	out.Timeline = append(make([]Entry, 0, len(i.Timeline)), i.Timeline...)
	return out
}

func copyScore(v *float64) *float64 {
	if v == nil {
		return nil
	}
	c := *v
	return &c
}

func copyStamp(v *time.Time) *time.Time {
	if v == nil {
		return nil
	}
	c := *v
	return &c
}
