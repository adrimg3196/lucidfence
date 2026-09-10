package api

import (
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
)

// registerIncidents monta el recurso. No hay POST ni DELETE: los incidentes
// los abre y los cierra el motor (Task 15); lo único que decide una persona es
// el estado, y eso viaja por PATCH.
//
// Las dos rutas literales conviven con la de {id} sin ambigüedad: el mux de la
// stdlib da precedencia al patrón más específico, así que /incidents/export
// nunca cae en incidentGet por mucho que se registre después.
func (s *server) registerIncidents() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/incidents", Cap: auth.IncidentRead, Handler: s.incidentsList})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/incidents/analytics", Cap: auth.IncidentRead, Handler: s.incidentAnalytics})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/incidents/export", Cap: auth.ReportExport, Handler: s.incidentExport})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/incidents/{id}", Cap: auth.IncidentRead, Handler: s.incidentGet})
	s.reg.Add(Route{Method: "PATCH", Path: "/api/v1/incidents/{id}", Cap: auth.IncidentWrite, Handler: s.incidentPatch})
}

// matchIncident aplica los dos filtros opcionales. Un valor que no existe
// (status=cerrado) deja la lista vacía en vez de dar 400, igual que hace
// state en /api/v1/devices: el filtro es una comodidad de la UI, no una
// validación de entrada.
func matchIncident(i incident.Incident, status, deviceID string) bool {
	if status != "" && string(i.Status) != status {
		return false
	}
	return deviceID == "" || i.DeviceID == deviceID
}

// filterIncidents conserva el orden del store: incident.Merge ya deja la
// cartera ordenada por estado, severidad, título e id, que es el orden que la
// bandeja del 1.x enseñaba y el que espera la UI de T24.
func filterIncidents(is []incident.Incident, r *http.Request) []incident.Incident {
	status := strings.TrimSpace(r.URL.Query().Get("status"))
	deviceID := strings.TrimSpace(r.URL.Query().Get("device_id"))
	out := make([]incident.Incident, 0, len(is))
	for _, i := range is {
		if matchIncident(i, status, deviceID) {
			out = append(out, i)
		}
	}
	return out
}

func (s *server) incidentsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	is, err := s.org().Incidents()
	if err != nil {
		s.fail(w, "incidents.list", err)
		return
	}
	out := filterIncidents(is, r)
	writeJSON(w, http.StatusOK, map[string]any{"items": out, "total": len(out)})
}

func (s *server) incidentGet(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	is, err := s.org().Incidents()
	if err != nil {
		s.fail(w, "incidents.get", err)
		return
	}
	inc, ok := incident.FindByID(is, pathID(r))
	if !ok {
		writeError(w, http.StatusNotFound, "not_found", "incidente no encontrado")
		return
	}
	writeJSON(w, http.StatusOK, inc)
}

// incidentPatchBody es el cuerpo de la única mutación del recurso.
type incidentPatchBody struct {
	Status   string `json:"status"`
	Assignee string `json:"assignee"`
	Note     string `json:"note"`
}

// indexOfIncident devuelve la posición para poder sustituir el registro:
// incident.FindByID devuelve una copia, y aquí hay que guardar la modificada.
func indexOfIncident(is []incident.Incident, id string) int {
	for i := range is {
		if is[i].ID == id {
			return i
		}
	}
	return -1
}

// actorOf identifica en la auditoría a quien hace el cambio. El email es lo
// que una persona reconoce al leer el timeline meses después; el id de usuario
// solo se usa cuando la petición llega por el token local, que no lleva email.
func actorOf(p *auth.Principal) string {
	if p == nil {
		return incident.ActorSystem
	}
	if p.Email != "" {
		return p.Email
	}
	return p.UserID
}

// writeTransitionError traduce los dos errores del dominio: un estado que no
// existe es entrada mal formada (400) y una transición que el estado actual no
// permite es un conflicto con lo guardado (409).
func writeTransitionError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, incident.ErrInvalidStatus):
		writeErrorDetail(w, http.StatusBadRequest, "invalid", err.Error(),
			map[string]any{"field": "status", "allowed": incident.Statuses})
	case errors.Is(err, incident.ErrSameStatus):
		writeErrorDetail(w, http.StatusConflict, "conflict", err.Error(), map[string]any{"field": "status"})
	default:
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
	}
}

// incidentPatch delega la validación del destino en incident.Transition y sella
// la entrada de auditoría con el email del principal, de modo que el timeline
// dice quién hizo qué sin que la API tenga que replicar la máquina de estados.
func (s *server) incidentPatch(w http.ResponseWriter, r *http.Request, p *auth.Principal) {
	var b incidentPatchBody
	if err := decodeJSON(r, &b); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if strings.TrimSpace(b.Status) == "" {
		writeErrorDetail(w, http.StatusBadRequest, "invalid", "status es obligatorio",
			map[string]any{"field": "status", "allowed": incident.Statuses})
		return
	}
	is, err := s.org().Incidents()
	if err != nil {
		s.fail(w, "incidents.patch.load", err)
		return
	}
	idx := indexOfIncident(is, pathID(r))
	if idx < 0 {
		writeError(w, http.StatusNotFound, "not_found", "incidente no encontrado")
		return
	}
	next, err := is[idx].Transition(incident.Status(b.Status), actorOf(p), b.Assignee, b.Note, s.d.Now().UTC())
	if err != nil {
		writeTransitionError(w, err)
		return
	}
	is[idx] = next
	if err := s.org().SaveIncidents(is); err != nil {
		s.fail(w, "incidents.patch.save", err)
		return
	}
	writeJSON(w, http.StatusOK, next)
}

func (s *server) incidentAnalytics(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	is, err := s.org().Incidents()
	if err != nil {
		s.fail(w, "incidents.analytics", err)
		return
	}
	writeJSON(w, http.StatusOK, incident.Analyze(is, s.d.Now().UTC()))
}

// exportFilename fecha el fichero para que dos descargas del mismo día no se
// pisen con nombres como "export(1).csv" en la carpeta de descargas.
func exportFilename(at time.Time) string {
	return "incidentes-" + at.UTC().Format("2006-01-02") + ".csv"
}

// incidentExport responde CSV, no JSON. Exige report:export (la capacidad que
// §6.3 da a admin, owner y auditor) porque sacar la cartera entera de la
// herramienta es un acto de exportación, no de lectura: un operator puede
// reconocer y cerrar incidentes y aun así no llevarse el fichero.
func (s *server) incidentExport(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	is, err := s.org().Incidents()
	if err != nil {
		s.fail(w, "incidents.export", err)
		return
	}
	body := incident.ToCSV(filterIncidents(is, r))
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", `attachment; filename="`+exportFilename(s.d.Now())+`"`)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}
