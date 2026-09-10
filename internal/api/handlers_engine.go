package api

import (
	"errors"
	"net/http"
	"net/url"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
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
		s.fail(w, "engine.run_once", err)
	default:
		writeJSON(w, http.StatusOK, st)
	}
}

// pageParams normaliza los dos parámetros de la paginación de §6.1: limit
// fuera de rango se acota (nunca es un 400, lo escribe la vista) y el cursor
// viaja opaco tal cual llegó. r.URL.Query().Get ya no sirve para leerlo:
// ante un % mal escrito, net/http descarta en silencio el par entero, así
// que un cursor corrupto se confundiría con "sin cursor" (primera página)
// en vez de fallar. rawCursor lo extrae a mano para que ese caso también
// sea store.ErrBadCursor.
func pageParams(r *http.Request) (int, string, error) {
	limit := queryInt(r, "limit", store.DefaultPageLimit, store.MaxPageLimit)
	cursor, err := rawCursor(r.URL.RawQuery)
	if err != nil {
		return 0, "", store.ErrBadCursor
	}
	return limit, cursor, nil
}

// rawCursor devuelve el valor de "cursor" en la query cruda, o "" si no
// aparece. A diferencia de url.Values.Get, no descarta en silencio una clave
// cuyo valor no se puede desescapar: lo propaga como error.
func rawCursor(rawQuery string) (string, error) {
	for _, pair := range strings.Split(rawQuery, "&") {
		key, value, _ := strings.Cut(pair, "=")
		if key != "cursor" {
			continue
		}
		return url.QueryUnescape(value)
	}
	return "", nil
}

// pageFail traduce un cursor manipulado a 400 invalid y cualquier otro fallo
// a 500 con el error real solo en el log: el cursor viaja en la query y
// cualquiera puede escribirlo a mano, así que no puede parecer una caída del
// servidor.
func (s *server) pageFail(w http.ResponseWriter, op string, err error) {
	if errors.Is(err, store.ErrBadCursor) {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	s.fail(w, op, err)
}

func (s *server) eventsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	limit, cursor, err := pageParams(r)
	if err != nil {
		s.pageFail(w, "events.list", err)
		return
	}
	evs, next, err := s.org().EventsPage(limit, cursor)
	if err != nil {
		s.pageFail(w, "events.list", err)
		return
	}
	if evs == nil {
		evs = []transition.Transition{}
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": evs, "next_cursor": next})
}

func (s *server) actionsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	limit, cursor, err := pageParams(r)
	if err != nil {
		s.pageFail(w, "actions.list", err)
		return
	}
	acts, next, err := s.org().ActionsPage(limit, cursor)
	if err != nil {
		s.pageFail(w, "actions.list", err)
		return
	}
	if acts == nil {
		acts = []action.Result{}
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": acts, "next_cursor": next})
}
