package api

import (
	"errors"
	"net/http"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

func (s *server) registerEngine() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/engine/status", Cap: auth.DeviceRead, Handler: s.engineStatus})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/engine/run-once", Cap: auth.EngineRun, Handler: s.engineRunOnce})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/events", Cap: auth.DeviceRead, Handler: s.eventsList})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/actions", Cap: auth.DeviceRead, Handler: s.actionsList})
}

func (s *server) engineStatus(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	writeJSON(w, http.StatusOK, s.d.Engine.Status())
}

func (s *server) engineRunOnce(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	st, err := s.d.Engine.RunOnce(r.Context())
	switch {
	case errors.Is(err, engine.ErrCycleInProgress):
		writeError(w, http.StatusConflict, "cycle_in_progress", err.Error())
	case err != nil:
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
	default:
		writeJSON(w, http.StatusOK, st)
	}
}

func (s *server) eventsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	evs, err := s.org().RecentEvents(queryInt(r, "limit", 100, 1000))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": evs})
}

func (s *server) actionsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	acts, err := s.org().RecentActions(queryInt(r, "limit", 100, 1000))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": acts})
}
