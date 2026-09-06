package api

import (
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func (s *server) registerDevices() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices", Cap: auth.DeviceRead, Handler: s.devicesList})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices/{id}", Cap: auth.DeviceRead, Handler: s.deviceGet})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices/{id}/trail", Cap: auth.DeviceRead, Handler: s.deviceTrail})
}

func matchDevice(d device.Device, state, q string) bool {
	if state != "" && string(d.FenceState) != state {
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
	state, q := r.URL.Query().Get("state"), r.URL.Query().Get("q")
	out := make([]device.Device, 0, len(ds))
	for _, d := range ds {
		if matchDevice(d, state, q) {
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
