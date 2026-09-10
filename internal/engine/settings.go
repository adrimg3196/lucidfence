// Ajustes vistos desde fuera del ciclo: adoptarlos en el acto y comprobar
// las URLs de salida contra la allowlist de egress sin enviar nada. Vive en
// el motor y no en internal/api porque la regla depguard "api" no permite
// importar internal/notify: el motor es la única puerta de la API hacia el
// canal de salida (spec §5.2, §6.4).
package engine

import (
	"context"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/notify"
)

// ChannelCheck es el veredicto de una URL de salida: si pasaría la allowlist
// de egress y, si no, por qué. Nunca lleva credenciales: la URL es la que el
// operador tiene delante en el formulario.
type ChannelCheck struct {
	Channel   string   `json:"channel"`
	Enabled   bool     `json:"enabled"`
	URL       string   `json:"url,omitempty"`
	OK        bool     `json:"ok"`
	Reason    string   `json:"reason,omitempty"`
	Addresses []string `json:"addresses,omitempty"`
}

// SettingsCheck es el resultado de comprobar unos ajustes candidatos: si son
// válidos, qué campo falla si no lo son y el veredicto de cada canal.
type SettingsCheck struct {
	OK       bool           `json:"ok"`
	Error    string         `json:"error,omitempty"`
	Field    string         `json:"field,omitempty"`
	Channels []ChannelCheck `json:"channels"`
}

// ApplySettings adopta unos ajustes recién guardados sin esperar al ciclo
// siguiente: applySettings ya refresca el enforcement de los guardarraíles,
// el contexto de riesgo y el notificador (Notifier.Reload, idempotente y sin
// tocar los contadores de entregas) en una sola operación atómica bajo
// stateMu. Es lo que hace que un PUT de /api/v1/settings surta efecto en el
// acto.
func (e *Engine) ApplySettings(set settings.Settings) {
	e.applySettings(set)
}

// CheckSettings valida unos ajustes candidatos y comprueba sus URLs de
// salida contra la allowlist de egress. No abre ningún socket hacia el
// destino: Egress.Check mira la allowlist antes de tocar el DNS y nunca
// envía la petición. Un canal apagado se comprueba igual (el operador quiere
// saber si la URL pasaría antes de encenderlo) pero no decide el OK global.
func (e *Engine) CheckSettings(ctx context.Context, set settings.Settings) SettingsCheck {
	out := SettingsCheck{OK: true}
	if err := set.Validate(); err != nil {
		out.OK, out.Error, out.Field = false, err.Error(), SettingsField(err)
	}
	eg := notify.NewEgress(set.Egress)
	if e.opts.Logger != nil {
		eg.Logger = e.opts.Logger
	}
	out.Channels = []ChannelCheck{
		checkChannel(ctx, eg, notify.ChannelWebhook, set.Webhook.Enabled, set.Webhook.URL),
		checkChannel(ctx, eg, notify.ChannelNtfy, set.Ntfy.Enabled, set.Ntfy.URL),
	}
	for _, c := range out.Channels {
		if c.Enabled && !c.OK {
			out.OK = false
		}
	}
	return out
}

func checkChannel(ctx context.Context, eg *notify.Egress, channel string, enabled bool, rawURL string) ChannelCheck {
	c := ChannelCheck{Channel: channel, Enabled: enabled, URL: rawURL}
	if rawURL == "" {
		c.Reason = "sin URL configurada"
		return c
	}
	t, err := eg.Check(ctx, rawURL)
	if err != nil {
		c.Reason = err.Error()
		return c
	}
	c.OK = true
	for _, ip := range t.IPs {
		c.Addresses = append(c.Addresses, ip.String())
	}
	return c
}

// settingsBlocks son los prefijos con los que settings.Validate nombra el
// campo que falla (T7): "enforcement.mode", "webhook.events[1]", ...
var settingsBlocks = []string{"enforcement.", "webhook.", "ntfy.", "egress.", "risk."}

// SettingsField extrae de un error de validación el nombre del campo que lo
// causó, para que la API lo devuelva en el detail del 400 y el formulario lo
// pinte junto al control. Devuelve "" si el mensaje no nombra ningún bloque
// conocido: es preferible un 400 sin campo a un campo inventado.
func SettingsField(err error) string {
	if err == nil {
		return ""
	}
	for _, palabra := range strings.FieldsFunc(err.Error(), separadorDeCampo) {
		for _, p := range settingsBlocks {
			if strings.HasPrefix(palabra, p) && len(palabra) > len(p) {
				return palabra
			}
		}
	}
	return ""
}

// separadorDeCampo corta el mensaje por lo que nunca forma parte de un
// nombre de campo. El corchete del índice ("webhook.events[1]") sí forma
// parte, así que no separa.
func separadorDeCampo(r rune) bool {
	return r == ' ' || r == ':' || r == ',' || r == ';' || r == '"' || r == '\'' || r == '\n' || r == '\t'
}
