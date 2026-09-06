package api

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// HandlerFunc recibe el principal ya autenticado (nil en rutas públicas).
type HandlerFunc func(w http.ResponseWriter, r *http.Request, p *auth.Principal)

// Route es una ruta declarada con su capacidad.
type Route struct {
	Method  string
	Path    string
	Cap     auth.Capability
	Public  bool
	Handler HandlerFunc
}

// Registry es la tabla de rutas. Los invariantes se comprueban al registrar
// (arranque del proceso), nunca se descubren en producción.
type Registry struct {
	routes []Route
	seen   map[string]bool
}

// NewRegistry crea un registro vacío.
func NewRegistry() *Registry { return &Registry{seen: map[string]bool{}} }

// Add registra una ruta o hace panic si viola un invariante.
func (reg *Registry) Add(r Route) {
	if !strings.HasPrefix(r.Path, "/api/v1/") {
		panic(fmt.Sprintf("ruta %s fuera de /api/v1/", r.Path))
	}
	if !r.Public && r.Cap == "" {
		panic(fmt.Sprintf("ruta %s %s sin capacidad (spec §6.1)", r.Method, r.Path))
	}
	key := r.Method + " " + r.Path
	if reg.seen[key] {
		panic("ruta duplicada: " + key)
	}
	reg.seen[key] = true
	reg.routes = append(reg.routes, r)
}

// Routes devuelve una copia de las rutas.
func (reg *Registry) Routes() []Route { return append([]Route(nil), reg.routes...) }
