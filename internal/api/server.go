package api

import (
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// Deps son las dependencias del servidor.
type Deps struct {
	Engine   *engine.Engine
	Org      *store.OrgStore
	Auth     *auth.Store
	Web      http.Handler
	WebBuilt bool
	Config   config.Config
	Logger   *slog.Logger
	Now      func() time.Time
}

type server struct {
	d   Deps
	reg *Registry
}

// New construye el handler raíz: /api/v1/* con auth y capacidades, / el dashboard.
func New(d Deps) (http.Handler, *Registry) {
	if d.Logger == nil {
		d.Logger = slog.Default()
	}
	if d.Now == nil {
		d.Now = time.Now
	}
	s := &server{d: d, reg: NewRegistry()}
	s.registerHealth()
	s.registerAuth()
	s.registerDevices()
	s.registerFences()
	s.registerRoutes()
	s.registerPOIs()
	s.registerEngine()
	mux := http.NewServeMux()
	for _, rt := range s.reg.Routes() {
		mux.Handle(rt.Method+" "+rt.Path, s.wrap(rt))
	}
	mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) {
		writeError(w, http.StatusNotFound, "not_found", "ruta no encontrada")
	})
	mux.Handle("/", d.Web)
	return securityHeaders(mux), s.reg
}

func (s *server) org() *store.OrgStore { return s.d.Org }

// fail registra un error interno (con el nombre del paso donde ocurrió) en
// el logger del servidor y responde sin filtrar sus detalles al cliente.
func (s *server) fail(w http.ResponseWriter, op string, err error) {
	writeInternalError(w, s.d.Logger, op, err)
}

// pathID extrae el {id} de la ruta.
func pathID(r *http.Request) string { return strings.TrimSpace(r.PathValue("id")) }
