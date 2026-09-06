package uem

import (
	"errors"
	"fmt"
	"sort"
	"sync"
)

// Factory construye un conector a partir de su configuración no secreta y sus secretos.
type Factory func(cfg map[string]any, secrets map[string]string) (Adapter, error)

// ErrUnknownProvider indica un nombre no registrado.
var ErrUnknownProvider = errors.New("proveedor desconocido")

// Registry es la tabla nombre → fábrica. Añadir un conector = una línea aquí.
type Registry struct {
	mu        sync.RWMutex
	factories map[string]Factory
}

// NewRegistry crea un registro vacío.
func NewRegistry() *Registry { return &Registry{factories: map[string]Factory{}} }

// Register añade una fábrica; registrar dos veces el mismo nombre es un error de programación.
func (r *Registry) Register(name string, f Factory) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, dup := r.factories[name]; dup {
		panic(fmt.Sprintf("uem: proveedor %q registrado dos veces", name))
	}
	r.factories[name] = f
}

// New construye un conector por nombre.
func (r *Registry) New(name string, cfg map[string]any, secrets map[string]string) (Adapter, error) {
	r.mu.RLock()
	f, ok := r.factories[name]
	r.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("%w: %q", ErrUnknownProvider, name)
	}
	return f(cfg, secrets)
}

// Names lista los proveedores registrados en orden estable.
func (r *Registry) Names() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	names := make([]string, 0, len(r.factories))
	for n := range r.factories {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}
