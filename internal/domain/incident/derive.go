package incident

import (
	"strconv"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// HighRiskScore es el score a partir del cual el riesgo abre incidente crítico
// por sí solo (mismo umbral que 1.x).
const HighRiskScore = 85.0

// Derive traduce la foto de la flota y los resultados de acción del ciclo en
// incidentes con id determinista: la misma condición sobre el mismo dispositivo
// produce siempre el mismo id, que es lo que permite a Merge reconocerla.
func Derive(ds []device.Device, results []action.Result, at time.Time) []Incident {
	raw := make([]Incident, 0, len(ds)+len(results))
	for _, d := range ds {
		if d.ID == "" {
			continue
		}
		raw = append(raw, deriveDevice(d, at)...)
	}
	for _, r := range results {
		if inc, ok := failedAction(r, at); ok {
			raw = append(raw, inc)
		}
	}
	out := make([]Incident, 0, len(raw))
	seen := make(map[string]bool, len(raw))
	for _, inc := range raw {
		if seen[inc.ID] {
			continue
		}
		seen[inc.ID] = true
		out = append(out, inc)
	}
	sortIncidents(out)
	return out
}

// draft son los datos comunes a todos los incidentes de un dispositivo.
type draft struct {
	device device.Device
	at     time.Time
}

// incident construye el incidente con id determinista "inc-<tipo>-<device>".
func (dr draft) incident(kind, severity, title, recommendation string, evidence ...string) Incident {
	d := dr.device
	fenceID := d.InsideFence
	if fenceID == "" {
		fenceID = d.LastInsideFence
	}
	if evidence == nil {
		evidence = []string{}
	}
	return Incident{
		ID:             "inc-" + kind + "-" + d.ID,
		DeviceID:       d.ID,
		DeviceName:     deviceName(d),
		Kind:           kind,
		Severity:       severity,
		Title:          title,
		Recommendation: recommendation,
		FenceID:        fenceID,
		Status:         StatusOpen,
		RiskScore:      copyScore(d.Risk.Score),
		Count:          1,
		Evidence:       evidence,
		OpenedAt:       dr.at,
		UpdatedAt:      dr.at,
		Timeline:       []Entry{},
	}
}

func deriveDevice(d device.Device, at time.Time) []Incident {
	dr := draft{device: d, at: at}
	nonCompliant := d.Compliant != nil && !*d.Compliant
	return append(deriveHealth(dr, nonCompliant), deriveLocation(dr, nonCompliant)...)
}

// deriveHealth cubre cumplimiento y riesgo agregado.
func deriveHealth(dr draft, nonCompliant bool) []Incident {
	d := dr.device
	out := make([]Incident, 0, 2)
	if nonCompliant {
		out = append(out, dr.incident(KindNonCompliant, risk.SeverityHigh,
			deviceName(d)+" no cumple la política UEM",
			"Revisar el cumplimiento, localizar el dispositivo y aplicar el playbook de remediación.",
			"compliant=false"))
	}
	if d.Risk.Score != nil && *d.Risk.Score >= HighRiskScore {
		ev := []string{"risk_score=" + numText(*d.Risk.Score), "severity=" + orNone(d.Risk.Severity)}
		for _, reason := range d.Risk.Reasons {
			ev = append(ev, "motivo: "+reason)
		}
		out = append(out, dr.incident(KindHighRisk, risk.SeverityCritical,
			deviceName(d)+" concentra riesgo crítico",
			"Priorizar la revisión manual: combina señales de geocerca, cumplimiento o automatización.",
			ev...))
	}
	return out
}

// deriveLocation cubre geocerca, ruta e integridad de la ubicación. Estar fuera
// e incumplir a la vez escala el incidente de salida a crítico en vez de abrir
// un segundo incidente crítico.
func deriveLocation(dr draft, nonCompliant bool) []Incident {
	d := dr.device
	out := make([]Incident, 0, 3)
	switch d.FenceState {
	case device.Outside:
		severity := risk.SeverityHigh
		if nonCompliant {
			severity = risk.SeverityCritical
		}
		out = append(out, dr.incident(KindGeofenceExit, severity,
			deviceName(d)+" está fuera de geocerca",
			"Validar la ubicación reciente, contactar con la persona responsable y ejecutar una acción UEM si procede.",
			"fence_state=outside", "last_inside_fence="+orNone(d.LastInsideFence),
			"dwell_seconds="+strconv.Itoa(d.DwellSeconds)))
	case device.Unknown:
		out = append(out, dr.incident(KindUnknownLocation, risk.SeverityMedium,
			deviceName(d)+" tiene ubicación desconocida",
			"Forzar una actualización de ubicación y revisar la conectividad del agente.",
			"fence_state=unknown", "location_source="+orNone(d.Location.Source)))
	}
	if d.RouteState == device.OffRoute {
		ev := []string{"route_id=" + orNone(d.RouteID)}
		if d.RouteDeviationM != nil {
			ev = append(ev, "route_deviation_m="+numText(*d.RouteDeviationM))
		}
		out = append(out, dr.incident(KindRouteDeviation, risk.SeverityHigh,
			deviceName(d)+" se desvió de su ruta",
			"Comprobar la ruta asignada y confirmar el desvío con la persona responsable.",
			ev...))
	}
	if d.LocationIntegrity.Suspicious {
		out = append(out, dr.incident(KindLocationIntegrity, risk.SeverityHigh,
			"Ubicación sospechosa en "+deviceName(d),
			"Tratar la última ubicación como no fiable hasta confirmarla con otra fuente.",
			integrityEvidence(d)...))
	}
	return out
}

func integrityEvidence(d device.Device) []string {
	ev := make([]string, 0, len(d.LocationIntegrity.Checks)+2)
	for _, c := range d.LocationIntegrity.Checks {
		ev = append(ev, "check="+c)
	}
	if d.LocationIntegrity.SpeedKMH != nil {
		ev = append(ev, "speed_kmh="+numText(*d.LocationIntegrity.SpeedKMH))
	}
	if d.LocationIntegrity.DistanceKM != nil {
		ev = append(ev, "distance_km="+numText(*d.LocationIntegrity.DistanceKM))
	}
	return ev
}

// failedAction abre incidente por una acción que el UEM rechazó. Una acción
// bloqueada por un guardarraíl no es un fallo: es la decisión correcta, y
// tratarla como incidente enseñaría a la gente a ignorar la bandeja.
func failedAction(r action.Result, at time.Time) (Incident, bool) {
	if r.OK || r.Blocked || r.DeviceID == "" || r.Action == "" {
		return Incident{}, false
	}
	name := r.DeviceName
	if name == "" {
		name = r.DeviceID
	}
	stamp := r.At
	if stamp.IsZero() {
		stamp = at
	}
	ev := []string{"action=" + string(r.Action), "adapter=" + orNone(r.Adapter)}
	if r.ErrorType != "" {
		ev = append(ev, "error_type="+r.ErrorType)
	}
	if r.Error != "" {
		ev = append(ev, "error="+r.Error)
	}
	return Incident{
		ID:             "inc-" + KindActionFailed + "-" + r.DeviceID + "-" + string(r.Action),
		DeviceID:       r.DeviceID,
		DeviceName:     name,
		Kind:           KindActionFailed,
		Severity:       risk.SeverityMedium,
		Title:          "Falló la acción " + string(r.Action) + " en " + name,
		Recommendation: "Reintentar manualmente y revisar el endpoint, los permisos o las credenciales del UEM.",
		FenceID:        r.FenceID,
		Status:         StatusOpen,
		Count:          1,
		Evidence:       ev,
		OpenedAt:       stamp,
		UpdatedAt:      stamp,
		Timeline:       []Entry{},
	}, true
}

func deviceName(d device.Device) string {
	if d.Name != "" {
		return d.Name
	}
	return d.ID
}

func orNone(s string) string {
	if s == "" {
		return "none"
	}
	return s
}

func numText(v float64) string {
	return strconv.FormatFloat(v, 'f', -1, 64)
}
