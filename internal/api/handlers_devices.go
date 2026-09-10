package api

import (
	"errors"
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

// severities es el vocabulario válido del filtro ?severity: los cuatro
// niveles de risk.Severities más "unknown" (risk.SeverityUnknown), el único
// quinto valor que Verdict.Severity puede llevar (T3). Se calcula una vez.
var severities = append(append([]string{}, risk.Severities...), risk.SeverityUnknown)

func validSeverity(s string) bool {
	for _, v := range severities {
		if v == s {
			return true
		}
	}
	return false
}

func (s *server) registerDevices() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices", Cap: auth.DeviceRead, Handler: s.devicesList})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices/{id}", Cap: auth.DeviceRead, Handler: s.deviceGet})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices/{id}/trail", Cap: auth.DeviceRead, Handler: s.deviceTrail})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/devices/{id}/actions", Cap: auth.DeviceAction, Handler: s.deviceAction})
}

// matchDevice descarta, no rechaza, una severidad fuera del vocabulario: un
// valor inválido en la URL deja el listado sin filtrar por severidad en vez
// de convertir GET /devices en un 400.
func matchDevice(d device.Device, state, q, severity string) bool {
	if state != "" && string(d.FenceState) != state {
		return false
	}
	if severity != "" && validSeverity(severity) && d.Risk.Severity != severity {
		return false
	}
	if q == "" {
		return true
	}
	q = strings.ToLower(q)
	for _, field := range []string{d.ID, d.Name, d.Platform, d.Inventory.AssignedUser, d.Inventory.Department, d.Inventory.Model, d.Inventory.SerialNumber} {
		if strings.Contains(strings.ToLower(field), q) {
			return true
		}
	}
	return false
}

func (s *server) devicesList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	ds, err := s.org().Devices()
	if err != nil {
		s.fail(w, "devices.list", err)
		return
	}
	state, q, severity := r.URL.Query().Get("state"), r.URL.Query().Get("q"), r.URL.Query().Get("severity")
	out := make([]device.Device, 0, len(ds))
	for _, d := range ds {
		if matchDevice(d, state, q, severity) {
			out = append(out, d)
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": out, "total": len(out)})
}

func (s *server) deviceGet(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	ds, err := s.org().Devices()
	if err != nil {
		s.fail(w, "devices.get", err)
		return
	}
	if d, ok := device.Index(ds)[pathID(r)]; ok {
		writeJSON(w, http.StatusOK, d)
		return
	}
	writeError(w, http.StatusNotFound, "not_found", "dispositivo no encontrado")
}

// deviceTrail comprueba primero que el id exista en Devices(): trail.jsonl
// no distingue "dispositivo inexistente" de "sin posiciones todavía", así
// que sin esta comprobación un id inventado devolvía 200 con una lista
// vacía en vez de 404.
func (s *server) deviceTrail(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	ds, err := s.org().Devices()
	if err != nil {
		s.fail(w, "devices.trail.load", err)
		return
	}
	id := pathID(r)
	if _, ok := device.Index(ds)[id]; !ok {
		writeError(w, http.StatusNotFound, "not_found", "dispositivo no encontrado")
		return
	}
	tr, err := s.org().Trail(id, queryInt(r, "limit", 200, 2000))
	if err != nil {
		s.fail(w, "devices.trail", err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": tr})
}

// deviceActionRequest es el cuerpo de POST /devices/{id}/actions.
type deviceActionRequest struct {
	Action string         `json:"action"`
	Params map[string]any `json:"params,omitempty"`
}

// actionsHint enumera el catálogo para el mensaje de error, que es el único
// sitio donde un operador ve qué puede pedir.
func actionsHint() string {
	names := make([]string, len(action.All))
	for i, a := range action.All {
		names[i] = string(a)
	}
	return strings.Join(names, "|")
}

// deviceAction lanza una acción a mano sobre un dispositivo. Pasa por la
// misma tubería que el ciclo (engine.ExecuteManual: guardarraíles, conector
// y registro en actions.jsonl con el actor), así que un wipe en observe sale
// en dry-run y uno sin la doble llave sale bloqueado.
//
// Una acción bloqueada por el guardarraíl responde 200 con el resultado
// dentro, no un 4xx: la petición era válida y el bloqueo, con su motivo, es
// la respuesta. Una acción suprimida por cooldown sí es un 409, porque no se
// ejecutó nada y no hay resultado que enseñar.
func (s *server) deviceAction(w http.ResponseWriter, r *http.Request, p *auth.Principal) {
	var body deviceActionRequest
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	a, err := action.Parse(strings.TrimSpace(body.Action))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error()+" (usa "+actionsHint()+")")
		return
	}
	id := pathID(r)
	res, err := s.d.Engine.ExecuteManual(r.Context(), id, a, body.Params, actorOf(p))
	if err == nil || errors.Is(err, engine.ErrActionBlocked) {
		writeJSON(w, http.StatusOK, res)
		return
	}
	s.writeEngineActionError(w, "devices.action", id, a, err)
}
