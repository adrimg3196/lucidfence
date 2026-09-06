package api

import (
	"errors"
	"net/http"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// crud monta GET/POST /coleccion y GET/PUT/DELETE /coleccion/{id} sobre una
// colección JSON del store. T debe serializar snake_case.
type crud[T any] struct {
	path      string
	readCap   auth.Capability
	writeCap  auth.Capability
	deleteCap auth.Capability
	load      func() ([]T, error)
	save      func([]T) error
	id        func(T) string
	stamp     func(*T, time.Time, bool)
	validate  func([]T) error
}

var errConflict = errors.New("ya existe")

func (c crud[T]) register(s *server) {
	s.reg.Add(Route{Method: "GET", Path: c.path, Cap: c.readCap, Handler: c.list})
	s.reg.Add(Route{Method: "POST", Path: c.path, Cap: c.writeCap, Handler: s.withNow(c.create)})
	s.reg.Add(Route{Method: "GET", Path: c.path + "/{id}", Cap: c.readCap, Handler: c.get})
	s.reg.Add(Route{Method: "PUT", Path: c.path + "/{id}", Cap: c.writeCap, Handler: s.withNow(c.update)})
	s.reg.Add(Route{Method: "DELETE", Path: c.path + "/{id}", Cap: c.deleteCap, Handler: c.remove})
}

type nowHandler func(w http.ResponseWriter, r *http.Request, now time.Time)

func (s *server) withNow(h nowHandler) HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request, _ *auth.Principal) { h(w, r, s.d.Now().UTC()) }
}

func (c crud[T]) list(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": items, "total": len(items)})
}

func (c crud[T]) find(items []T, id string) int {
	for i, it := range items {
		if c.id(it) == id {
			return i
		}
	}
	return -1
}

func (c crud[T]) get(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	writeJSON(w, http.StatusOK, items[i])
}

func (c crud[T]) create(w http.ResponseWriter, r *http.Request, now time.Time) {
	var item T
	if err := decodeJSON(r, &item); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	if c.find(items, c.id(item)) >= 0 {
		writeError(w, http.StatusConflict, "conflict", errConflict.Error())
		return
	}
	c.stamp(&item, now, true)
	items = append(items, item)
	if err := c.validate(items); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := c.save(items); err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, item)
}

func (c crud[T]) update(w http.ResponseWriter, r *http.Request, now time.Time) {
	var item T
	if err := decodeJSON(r, &item); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	if c.id(item) != pathID(r) {
		writeError(w, http.StatusBadRequest, "invalid", "el id del cuerpo no coincide con la ruta")
		return
	}
	c.stamp(&item, now, false)
	items[i] = item
	if err := c.validate(items); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := c.save(items); err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (c crud[T]) remove(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	items = append(items[:i], items[i+1:]...)
	if err := c.save(items); err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
