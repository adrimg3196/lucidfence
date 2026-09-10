// Ajustes de la organización (spec §6.1): enforcement, webhook, ntfy, egress
// y contexto de riesgo. Los secretos nunca salen por aquí: settings.json solo
// guarda secret_set y token_set, y esta API los recalcula contra el almacén
// de secretos, que es donde el notificador los busca (spec §5.8, §7).
package api

import (
	"net/http"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

// secretWebhook y secretNtfy son los nombres con los que el notificador busca
// sus credenciales en <data>/secrets/<org>/. Repiten a propósito el valor de
// notify.SecretWebhook y notify.SecretNtfy: internal/api no puede importar
// internal/notify (regla depguard "api"). Una divergencia de nombre la
// atrapa el check de la batería (T28), que guarda el secreto por esta ruta y
// comprueba la firma HMAC en un receptor real.
const (
	secretWebhook = "webhook_secret"
	secretNtfy    = "ntfy_token"
)

func (s *server) registerSettings() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/settings", Cap: auth.EngineConfig, Handler: s.settingsGet})
	s.reg.Add(Route{Method: "PUT", Path: "/api/v1/settings/enforcement", Cap: auth.EngineConfig, Handler: s.withNow(s.settingsEnforcement)})
	s.reg.Add(Route{Method: "PUT", Path: "/api/v1/settings/webhooks", Cap: auth.EngineConfig, Handler: s.withNow(s.settingsWebhooks)})
	s.reg.Add(Route{Method: "PUT", Path: "/api/v1/settings/egress", Cap: auth.EngineConfig, Handler: s.withNow(s.settingsEgress)})
	s.reg.Add(Route{Method: "PUT", Path: "/api/v1/settings/risk", Cap: auth.EngineConfig, Handler: s.withNow(s.settingsRisk)})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/settings/validate", Cap: auth.EngineConfig, Handler: s.settingsValidate})
}

// hasSecret dice si el notificador encontraría la credencial: el fichero
// 0600 de la organización o la variable LUCIDFENCE_<NAME>, que gana.
func (s *server) hasSecret(name string) bool {
	_, err := s.d.Store.Secret(s.d.Config.Org, name)
	return err == nil
}

// settingsView es la única forma en que los ajustes salen de la API: los
// booleanos de credencial se recalculan contra el almacén de secretos en vez
// de creerle al fichero, que puede estar desfasado (secreto inyectado por
// variable de entorno, o guardado justo antes de un fallo de escritura).
func (s *server) settingsView(set settings.Settings) settings.Settings {
	set.Webhook.SecretSet = s.hasSecret(secretWebhook)
	set.Ntfy.TokenSet = s.hasSecret(secretNtfy)
	return set
}

func (s *server) settingsGet(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	set, err := s.org().Settings()
	if err != nil {
		s.fail(w, "settings.get", err)
		return
	}
	writeJSON(w, http.StatusOK, s.settingsView(set))
}

// invalidSettings responde 400 con el mensaje de validación tal cual (ya
// nombra el campo, T7) y con ese mismo campo en el detail, para que el
// formulario de ajustes lo pinte junto al control sin analizar cadenas.
func invalidSettings(w http.ResponseWriter, err error) {
	var detail any
	if f := engine.SettingsField(err); f != "" {
		detail = map[string]any{"field": f}
	}
	writeErrorDetail(w, http.StatusBadRequest, "invalid", err.Error(), detail)
}

// loadSettings lee los ajustes vigentes para un PUT parcial: cada ruta
// sustituye su bloque y deja los demás como estaban.
func (s *server) loadSettings(w http.ResponseWriter, step string) (settings.Settings, bool) {
	set, err := s.org().Settings()
	if err != nil {
		s.fail(w, step, err)
		return settings.Settings{}, false
	}
	return set, true
}

// persistSettings valida el documento completo, lo guarda, lo pone en vigor
// sin esperar al ciclo siguiente y responde con la vista pública.
func (s *server) persistSettings(w http.ResponseWriter, set settings.Settings, now time.Time) {
	set.UpdatedAt = now
	if err := set.Validate(); err != nil {
		invalidSettings(w, err)
		return
	}
	if err := s.org().SaveSettings(set); err != nil {
		s.fail(w, "settings.save", err)
		return
	}
	s.d.Engine.ApplySettings(set)
	writeJSON(w, http.StatusOK, s.settingsView(set))
}

func (s *server) settingsEnforcement(w http.ResponseWriter, r *http.Request, now time.Time) {
	var body settings.Enforcement
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := body.Validate(); err != nil {
		invalidSettings(w, err)
		return
	}
	set, ok := s.loadSettings(w, "settings.enforcement")
	if !ok {
		return
	}
	set.Enforcement = body
	s.persistSettings(w, set, now)
}

func (s *server) settingsEgress(w http.ResponseWriter, r *http.Request, now time.Time) {
	var body settings.Egress
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := body.Validate(); err != nil {
		invalidSettings(w, err)
		return
	}
	set, ok := s.loadSettings(w, "settings.egress")
	if !ok {
		return
	}
	set.Egress = body
	s.persistSettings(w, set, now)
}

// settingsRisk cambia solo el contexto de riesgo (ruling M2-C3): sin esta
// ruta el bloque risk que GET /api/v1/settings ya publica desde T7 sería
// inalcanzable en escritura.
func (s *server) settingsRisk(w http.ResponseWriter, r *http.Request, now time.Time) {
	var body settings.Risk
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := body.Validate(); err != nil {
		invalidSettings(w, err)
		return
	}
	set, ok := s.loadSettings(w, "settings.risk")
	if !ok {
		return
	}
	set.Risk = body
	s.persistSettings(w, set, now)
}

// webhookUpdate es el cuerpo de PUT /settings/webhooks: la configuración del
// canal más un secreto de solo escritura. Secret distingue tres intenciones:
// ausente (nil) no toca el secreto guardado, la cadena vacía lo borra y
// cualquier otro valor lo sustituye. Nunca vuelve en una respuesta.
type webhookUpdate struct {
	URL     string   `json:"url"`
	Format  string   `json:"format"`
	Events  []string `json:"events"`
	Enabled bool     `json:"enabled"`
	Secret  *string  `json:"secret,omitempty"`
}

func (s *server) settingsWebhooks(w http.ResponseWriter, r *http.Request, now time.Time) {
	var body webhookUpdate
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	cfg := settings.Webhook{URL: body.URL, Format: body.Format, Events: body.Events, Enabled: body.Enabled,
		SecretSet: s.secretAfterUpdate(body.Secret, secretWebhook)}
	if err := cfg.Validate(); err != nil {
		invalidSettings(w, err)
		return
	}
	set, ok := s.loadSettings(w, "settings.webhooks")
	if !ok {
		return
	}
	// El secreto se escribe después de validar (no se guarda credencial de
	// una configuración rechazada) y antes de persistir los ajustes: si el
	// guardado fallara, la verdad seguiría siendo la del almacén, que es lo
	// que settingsView recalcula.
	if err := s.applyWebhookSecret(body.Secret); err != nil {
		s.fail(w, "settings.webhooks.secret", err)
		return
	}
	set.Webhook = cfg
	s.persistSettings(w, set, now)
}

// secretAfterUpdate dice si la credencial quedará puesta tras aplicar la
// intención del cuerpo, sin haberla aplicado todavía.
func (s *server) secretAfterUpdate(secret *string, name string) bool {
	if secret == nil {
		return s.hasSecret(name)
	}
	return *secret != ""
}

func (s *server) applyWebhookSecret(secret *string) error {
	switch {
	case secret == nil:
		return nil
	case *secret == "":
		return s.d.Store.DeleteSecret(s.d.Config.Org, secretWebhook)
	default:
		return s.d.Store.SaveSecret(s.d.Config.Org, secretWebhook, *secret)
	}
}

// settingsCandidate es el cuerpo (opcional) de POST /settings/validate: los
// bloques que el formulario tiene en pantalla, superpuestos sobre lo
// guardado. El secreto no viaja: el botón comprueba URL y allowlist, no
// credenciales.
type settingsCandidate struct {
	Enforcement *settings.Enforcement `json:"enforcement,omitempty"`
	Webhook     *settings.Webhook     `json:"webhook,omitempty"`
	Ntfy        *settings.Ntfy        `json:"ntfy,omitempty"`
	Egress      *settings.Egress      `json:"egress,omitempty"`
	Risk        *settings.Risk        `json:"risk,omitempty"`
}

func (c settingsCandidate) applyTo(set *settings.Settings) {
	if c.Enforcement != nil {
		set.Enforcement = *c.Enforcement
	}
	if c.Webhook != nil {
		set.Webhook = *c.Webhook
	}
	if c.Ntfy != nil {
		set.Ntfy = *c.Ntfy
	}
	if c.Egress != nil {
		set.Egress = *c.Egress
	}
	if c.Risk != nil {
		set.Risk = *c.Risk
	}
}

func (s *server) settingsValidate(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	set, ok := s.loadSettings(w, "settings.validate")
	if !ok {
		return
	}
	if r.ContentLength != 0 {
		var body settingsCandidate
		if err := decodeJSON(r, &body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid", err.Error())
			return
		}
		body.applyTo(&set)
	}
	writeJSON(w, http.StatusOK, s.d.Engine.CheckSettings(r.Context(), set))
}
