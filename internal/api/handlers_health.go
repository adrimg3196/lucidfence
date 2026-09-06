package api

import (
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/engine"
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
		"persistence":    persistenceView(st),
		"map":            map[string]any{"enabled": s.d.Config.Map.Enabled, "tiles_url": s.d.Config.Map.TilesURL},
	})
}

// persistenceView traduce el último ciclo del motor a la salud del store que
// pide la spec §11 ("fallo de escritura → estado en memoria intacto,
// health.persistence = degraded, doctor lo explica"). Dos fuentes: el error
// del ciclo, que siempre viene del store (leer la entrada o guardar
// devices.json) y deja el ciclo sin contar, y los persistence_errors del
// último ciclo completado, que son los fallos de trail/eventos/acciones/
// estadísticas que el motor solo cuenta para poder seguir (M1-R11).
// last_error repite el mismo texto que engine.last_error, ya presente en
// esta misma respuesta.
func persistenceView(st engine.Status) map[string]any {
	switch {
	case st.LastError != "":
		return map[string]any{"ok": false, "last_error": st.LastError}
	case st.LastCycle != nil && st.LastCycle.PersistenceErrors > 0:
		return map[string]any{"ok": false,
			"last_error": fmt.Sprintf("%d fallos de escritura en el último ciclo", st.LastCycle.PersistenceErrors)}
	default:
		return map[string]any{"ok": true}
	}
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
