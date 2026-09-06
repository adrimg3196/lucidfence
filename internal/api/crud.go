package api

import (
	"errors"
	"log/slog"
	"net/http"
	"strings"
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
	// stamp fija las fechas del registro. En create se llama con prev == nil
	// (fija CreatedAt=UpdatedAt=now); en update, con prev apuntando al
	// registro almacenado (copia prev.CreatedAt y fija UpdatedAt=now), para
	// que un PUT cuyo cuerpo no incluya created_at no lo borre.
	stamp    func(next *T, prev *T, now time.Time)
	validate func([]T) error
	logger   *slog.Logger
}

var errConflict = errors.New("ya existe")

func (c crud[T]) register(s *server) {
	c.logger = s.d.Logger
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

// fail registra el error real (con la ruta del recurso y el paso donde
// ocurrió) en el logger del servidor y responde sin filtrar detalles
// internos del store (rutas de fichero, mensajes de os) al cliente.
func (c crud[T]) fail(w http.ResponseWriter, step string, err error) {
	writeInternalError(w, c.logger, strings.TrimPrefix(c.path, "/api/v1/")+"."+step, err)
}

func (c crud[T]) list(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		c.fail(w, "list", err)
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
		c.fail(w, "get", err)
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
		c.fail(w, "create.load", err)
		return
	}
	if c.find(items, c.id(item)) >= 0 {
		writeError(w, http.StatusConflict, "conflict", errConflict.Error())
		return
	}
	c.stamp(&item, nil, now)
	items = append(items, item)
	if err := c.validate(items); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := c.save(items); err != nil {
		c.fail(w, "create.save", err)
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
		c.fail(w, "update.load", err)
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
	c.stamp(&item, &items[i], now)
	items[i] = item
	if err := c.validate(items); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := c.save(items); err != nil {
		c.fail(w, "update.save", err)
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (c crud[T]) remove(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		c.fail(w, "remove.load", err)
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	items = append(items[:i], items[i+1:]...)
	if err := c.save(items); err != nil {
		c.fail(w, "remove.save", err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
