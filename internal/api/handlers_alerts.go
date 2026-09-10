package api

import (
	"net/http"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
)

// registerAlerts monta las reglas de alerta como un crud[T] más. La lectura va
// con incident:read porque §6.3 no define alert:read y las reglas se miran
// desde la misma pantalla que la bandeja; la escritura y el borrado, con
// alert:write. El borrado comparte capacidad con la escritura: una regla es
// configuración, no un registro histórico que convenga proteger aparte.
func (s *server) registerAlerts() {
	crud[alert.Rule]{
		path: "/api/v1/alerts", readCap: auth.IncidentRead, writeCap: auth.AlertWrite, deleteCap: auth.AlertWrite,
		load: s.org().Alerts, save: s.org().SaveAlerts,
		id: func(r alert.Rule) string { return r.ID },
		stamp: func(next *alert.Rule, prev *alert.Rule, now time.Time) {
			if prev == nil {
				next.CreatedAt = now
			} else {
				next.CreatedAt = prev.CreatedAt
			}
			next.UpdatedAt = now
		},
		validate: alert.ValidateAll,
	}.register(s)
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/alerts/evaluate", Cap: auth.AlertWrite, Handler: s.alertsEvaluate})
}

// alertsEvaluate corre las reglas contra la flota actual y devuelve los
// disparos sin notificar ni persistir: es la vista previa que usa quien
// administra para calibrar un umbral antes de dejar la regla activa. Escribir
// aquí en alerts.json o en deliveries.jsonl convertiría un ensayo en un aviso
// real a todo el equipo, así que la única salida es la respuesta.
//
// Exige alert:write y no incident:read porque probar un umbral es parte de
// configurarlo, y porque recorre la flota entera en cada llamada.
func (s *server) alertsEvaluate(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	rules, err := s.org().Alerts()
	if err != nil {
		s.fail(w, "alerts.evaluate.rules", err)
		return
	}
	devices, err := s.org().Devices()
	if err != nil {
		s.fail(w, "alerts.evaluate.devices", err)
		return
	}
	at := s.d.Now().UTC()
	firings := alert.Evaluate(rules, devices, at)
	writeJSON(w, http.StatusOK, map[string]any{
		"at": at, "rules_evaluated": len(rules), "devices": len(devices),
		"count": len(firings), "firings": firings,
	})
}
