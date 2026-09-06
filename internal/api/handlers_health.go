package api

import (
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/version"
)

func (s *server) registerHealth() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/health", Public: true, Handler: s.health})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/readyz", Public: true, Handler: s.readyz})
}

func (s *server) health(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	st := s.d.Engine.Status()
	var lastAt *time.Time
	if st.LastCycle != nil {
		lastAt = &st.LastCycle.At
	}
	engineView := map[string]any{"running": st.Running, "cycles": st.Cycles, "last_cycle_at": lastAt, "interval_seconds": st.IntervalSeconds}
	if st.LastError != "" {
		engineView["last_error"] = st.LastError
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok", "version": version.Version, "mode": st.Mode, "enforcement": st.Enforcement, "web_built": s.d.WebBuilt,
		"setup_required": !s.d.Auth.HasUsers(),
		"engine":         engineView,
		"map":            map[string]any{"enabled": s.d.Config.Map.Enabled, "tiles_url": s.d.Config.Map.TilesURL},
	})
}

func (s *server) readyz(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	probe := filepath.Join(s.org().Dir(), ".ready-probe")
	if err := os.WriteFile(probe, []byte("ok"), 0o600); err != nil {
		writeErrorDetail(w, http.StatusServiceUnavailable, "not_ready", "el directorio de datos no es escribible", err.Error())
		return
	}
	_ = os.Remove(probe)
	writeJSON(w, http.StatusOK, map[string]any{"ready": true})
}
