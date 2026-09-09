// Package settings define los ajustes de operación de una organización: modo
// de enforcement, canales de salida (webhook y ntfy), allowlist de egress y
// el contexto de riesgo. Es dominio puro: no lee ni escribe nada (lo persiste
// internal/store, spec §5.5) y no conoce HTTP. Los valores de los secretos
// nunca viven aquí: solo los booleanos secret_set y token_set (spec §5.8).
package settings

import (
	"errors"
	"fmt"
	"maps"
	"net/url"
	"slices"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

// SchemaVersion es la versión del documento settings.json (spec §5.5).
const SchemaVersion = 1

// Modos de enforcement (spec §5.4). En observe ninguna acción sale al UEM.
const (
	ModeObserve = "observe"
	ModeEnforce = "enforce"
)

// Formatos del payload del webhook (spec §6.4).
const (
	FormatNative = "native"
	FormatOCSF   = "ocsf"
)

// Valores de fábrica, los mismos que 1.x: cooldown de una hora para las
// acciones destructivas y franja nocturna de 20:00 a 07:00.
const (
	DefaultActionCooldownSeconds = 3600
	DefaultOffHoursStart         = 20
	DefaultOffHoursEnd           = 7
)

// Modes y Formats enumeran los valores válidos en orden estable (la API los
// publica tal cual para poblar los selectores del frontend).
var (
	Modes   = []string{ModeObserve, ModeEnforce}
	Formats = []string{FormatNative, FormatOCSF}
)

// WebhookEvents enumera los eventos a los que un webhook puede suscribirse.
var WebhookEvents = []string{
	"incident.opened",
	"incident.closed",
	"handoff.pending",
	"action.executed",
	"alert.fired",
}

// Enforcement decide qué sale en vivo. live_actions vacío significa NINGUNA
// acción en vivo (1.x lo interpretaba como "todas"; 2.0 falla cerrado).
type Enforcement struct {
	Mode                  string          `json:"mode"`
	LiveActions           []action.Action `json:"live_actions"`
	AllowWipe             bool            `json:"allow_wipe"`
	WipeAllowlist         []string        `json:"wipe_allowlist"`
	ActionCooldownSeconds int             `json:"action_cooldown_seconds"`
}

// Webhook es el canal HTTP firmado. SecretSet solo dice si hay secreto
// guardado; el valor vive en el store de secretos.
type Webhook struct {
	URL       string   `json:"url"`
	Format    string   `json:"format"`
	Events    []string `json:"events"`
	Enabled   bool     `json:"enabled"`
	SecretSet bool     `json:"secret_set"`
}

// Ntfy es el canal de notificación push. TokenSet, como SecretSet, es solo
// un indicador de presencia.
type Ntfy struct {
	URL      string `json:"url"`
	Enabled  bool   `json:"enabled"`
	TokenSet bool   `json:"token_set"`
}

// Egress es la allowlist de salida que aplica internal/notify.
type Egress struct {
	Hosts        []string `json:"hosts"`
	AllowPrivate bool     `json:"allow_private"`
}

// Risk es el contexto del cálculo de señales: turno esperado por dispositivo
// (id de dispositivo → id de geocerca), riesgo por zona (id de geocerca →
// [0, 1]) y franja nocturna.
type Risk struct {
	ShiftZones    map[string]string  `json:"shift_zones"`
	ZoneRisk      map[string]float64 `json:"zone_risk"`
	OffHoursStart int                `json:"off_hours_start"`
	OffHoursEnd   int                `json:"off_hours_end"`
}

// Settings son los ajustes completos de una organización.
type Settings struct {
	SchemaVersion int         `json:"schema_version"`
	Enforcement   Enforcement `json:"enforcement"`
	Webhook       Webhook     `json:"webhook"`
	Ntfy          Ntfy        `json:"ntfy"`
	Egress        Egress      `json:"egress"`
	Risk          Risk        `json:"risk"`
	UpdatedAt     time.Time   `json:"updated_at"`
}

// Default devuelve los ajustes seguros de fábrica. Cada llamada construye
// slices y mapas nuevos: quien los recibe puede editarlos sin afectar a nadie.
func Default() Settings {
	return Settings{
		SchemaVersion: SchemaVersion,
		Enforcement: Enforcement{
			Mode:                  ModeObserve,
			LiveActions:           []action.Action{},
			AllowWipe:             false,
			WipeAllowlist:         []string{},
			ActionCooldownSeconds: DefaultActionCooldownSeconds,
		},
		Webhook: Webhook{Format: FormatNative, Events: slices.Clone(WebhookEvents)},
		Ntfy:    Ntfy{},
		Egress:  Egress{Hosts: []string{}},
		Risk: Risk{
			ShiftZones:    map[string]string{},
			ZoneRisk:      map[string]float64{},
			OffHoursStart: DefaultOffHoursStart,
			OffHoursEnd:   DefaultOffHoursEnd,
		},
	}
}

// Normalized rellena lo ausente sin cambiar lo declarado: enum vacío a su
// valor de fábrica, listas y mapas nil a vacíos, hosts en minúsculas, sin
// espacios y sin duplicados. Las horas de Risk no se tocan: 0-0 es legítimo.
func (s Settings) Normalized() Settings {
	s.SchemaVersion = SchemaVersion
	s.Enforcement = s.Enforcement.normalized()
	s.Webhook = s.Webhook.normalized()
	s.Ntfy.URL = strings.TrimSpace(s.Ntfy.URL)
	s.Egress = s.Egress.normalized()
	s.Risk = s.Risk.normalized()
	return s
}

// Validate comprueba los cinco bloques y nombra el campo que falla.
func (s Settings) Validate() error {
	for _, v := range []func() error{
		s.Enforcement.Validate, s.Webhook.Validate, s.Ntfy.Validate,
		s.Egress.Validate, s.Risk.Validate,
	} {
		if err := v(); err != nil {
			return err
		}
	}
	return nil
}

func (e Enforcement) normalized() Enforcement {
	if e.Mode == "" {
		e.Mode = ModeObserve
	}
	if e.LiveActions == nil {
		e.LiveActions = []action.Action{}
	}
	if e.WipeAllowlist == nil {
		e.WipeAllowlist = []string{}
	}
	return e
}

// Validate valida el bloque de enforcement por separado (PUT /settings/enforcement).
func (e Enforcement) Validate() error {
	if !slices.Contains(Modes, e.Mode) {
		return fmt.Errorf("enforcement.mode: %q no es observe|enforce", e.Mode)
	}
	for i, a := range e.LiveActions {
		if _, err := action.Parse(string(a)); err != nil {
			return fmt.Errorf("enforcement.live_actions[%d]: %w", i, err)
		}
	}
	for i, id := range e.WipeAllowlist {
		if strings.TrimSpace(id) == "" {
			return fmt.Errorf("enforcement.wipe_allowlist[%d]: id de dispositivo vacío", i)
		}
	}
	if e.ActionCooldownSeconds < 0 {
		return fmt.Errorf("enforcement.action_cooldown_seconds: %d no puede ser negativo", e.ActionCooldownSeconds)
	}
	return nil
}

func (w Webhook) normalized() Webhook {
	if w.Format == "" {
		w.Format = FormatNative
	}
	if w.Events == nil {
		w.Events = []string{}
	}
	w.URL = strings.TrimSpace(w.URL)
	return w
}

// Validate valida el bloque del webhook por separado (PUT /settings/webhooks).
func (w Webhook) Validate() error {
	if !slices.Contains(Formats, w.Format) {
		return fmt.Errorf("webhook.format: %q no es native|ocsf", w.Format)
	}
	for i, ev := range w.Events {
		if !slices.Contains(WebhookEvents, ev) {
			return fmt.Errorf("webhook.events[%d]: %q no es un evento conocido", i, ev)
		}
	}
	if !w.Enabled {
		return nil
	}
	if err := validateHTTPURL(w.URL); err != nil {
		return fmt.Errorf("webhook.url: %w", err)
	}
	if len(w.Events) == 0 {
		return errors.New("webhook.events: un webhook activo debe suscribirse al menos a un evento")
	}
	return nil
}

// Validate valida el bloque de ntfy por separado.
func (n Ntfy) Validate() error {
	if !n.Enabled {
		return nil
	}
	if err := validateHTTPURL(n.URL); err != nil {
		return fmt.Errorf("ntfy.url: %w", err)
	}
	return nil
}

func (e Egress) normalized() Egress {
	hosts := make([]string, 0, len(e.Hosts))
	for _, h := range e.Hosts {
		h = strings.ToLower(strings.TrimSpace(h))
		if h != "" && !slices.Contains(hosts, h) {
			hosts = append(hosts, h)
		}
	}
	e.Hosts = hosts
	return e
}

// Validate valida el bloque de egress por separado (PUT /settings/egress).
func (e Egress) Validate() error {
	for i, h := range e.Hosts {
		trimmed := strings.TrimSpace(h)
		if trimmed == "" {
			return fmt.Errorf("egress.hosts[%d]: host vacío", i)
		}
		if strings.ContainsAny(trimmed, "/ \t") {
			return fmt.Errorf("egress.hosts[%d]: %q debe ser solo el host, sin esquema ni ruta", i, h)
		}
	}
	return nil
}

func (r Risk) normalized() Risk {
	if r.ShiftZones == nil {
		r.ShiftZones = map[string]string{}
	}
	if r.ZoneRisk == nil {
		r.ZoneRisk = map[string]float64{}
	}
	return r
}

// Validate valida el bloque de riesgo por separado.
func (r Risk) Validate() error {
	if r.OffHoursStart < 0 || r.OffHoursStart > 23 {
		return fmt.Errorf("risk.off_hours_start: %d fuera de [0, 23]", r.OffHoursStart)
	}
	if r.OffHoursEnd < 0 || r.OffHoursEnd > 23 {
		return fmt.Errorf("risk.off_hours_end: %d fuera de [0, 23]", r.OffHoursEnd)
	}
	// Orden determinista: el mensaje de error no puede depender del recorrido
	// aleatorio de un mapa.
	for _, zone := range slices.Sorted(maps.Keys(r.ZoneRisk)) {
		if v := r.ZoneRisk[zone]; v < 0 || v > 1 {
			return fmt.Errorf("risk.zone_risk[%q]: %.2f fuera de [0, 1]", zone, v)
		}
	}
	return nil
}

func validateHTTPURL(raw string) error {
	if strings.TrimSpace(raw) == "" {
		return errors.New("obligatoria cuando el canal está activo")
	}
	u, err := url.Parse(raw)
	if err != nil {
		return errors.New("no es una URL válida")
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return fmt.Errorf("esquema %q: solo http o https", u.Scheme)
	}
	if u.Host == "" {
		return errors.New("falta el host")
	}
	return nil
}
