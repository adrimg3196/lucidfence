package notify

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// Prioridades de ntfy (https://docs.ntfy.sh/publish/#message-priority).
var ntfyPriorities = map[string]string{"critical": "5", "high": "4", "medium": "3", "low": "2", "info": "1"}

// NtfyDefaultPriority es la prioridad de lo que no declara severidad: ni la
// mínima, que escondería el aviso, ni la máxima, que lo exageraría.
const NtfyDefaultPriority = "3"

// NtfyDefaultTag es la etiqueta de un evento cuyo tipo no reconocemos.
const NtfyDefaultTag = "round_pushpin"

var ntfyTags = map[string]string{
	EventIncidentOpened: "rotating_light",
	EventIncidentClosed: "white_check_mark",
	EventHandoffPending: "hourglass",
	EventActionExecuted: "gear",
	EventAlertFired:     "bell",
}

// asciiFold traduce los acentos del español a su letra base.
var asciiFold = map[rune]rune{
	'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
	'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i', 'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o',
	'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u', 'ñ': 'n', 'ç': 'c',
	'Á': 'A', 'À': 'A', 'É': 'E', 'È': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ñ': 'N', 'Ü': 'U',
}

// NtfyPriority traduce la severidad a la escala de ntfy.
func NtfyPriority(severity string) string {
	if p, ok := ntfyPriorities[strings.ToLower(strings.TrimSpace(severity))]; ok {
		return p
	}
	return NtfyDefaultPriority
}

// asciiHeader deja el valor en ASCII imprimible: una cabecera HTTP no puede
// llevar UTF-8 (RFC 9110 §5.5) y ntfy mostraría bytes rotos en el aviso. El
// texto con acentos viaja en el cuerpo, que sí es UTF-8.
func asciiHeader(s string) string {
	var b strings.Builder
	for _, r := range s {
		if a, ok := asciiFold[r]; ok {
			r = a
		}
		if r < 0x20 || r > 0x7e {
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}

func ntfyTitle(ev Event) string {
	return "[" + Product + "] [" + strings.ToUpper(ev.Severity()) + "] " + ev.verb()
}

func ntfyTag(kind string) string {
	if tag, ok := ntfyTags[kind]; ok {
		return tag
	}
	return NtfyDefaultTag
}

// ntfyBody es el aviso en texto plano: titular, dispositivo, severidad y el
// dato concreto del evento. Nunca los parámetros de una acción ni ubicación.
func ntfyBody(ev Event) string {
	lines := []string{ev.Title()}
	if _, nombre := ev.device(); nombre != "" {
		lines = append(lines, "Dispositivo: "+nombre)
	}
	lines = append(lines, "Severidad: "+ev.Severity())
	switch {
	case ev.Incident != nil && ev.Incident.FenceID != "":
		lines = append(lines, "Geocerca: "+ev.Incident.FenceID)
	case ev.Handoff != nil:
		lines = append(lines, "Playbook: "+ev.Handoff.PlaybookName)
	case ev.Action != nil:
		lines = append(lines, "Acción: "+string(ev.Action.Action))
	case ev.Firing != nil:
		lines = append(lines, "Regla: "+ev.Firing.RuleName)
	}
	if !ev.At.IsZero() {
		lines = append(lines, "Hora: "+ev.At.UTC().Format(time.RFC3339))
	}
	return strings.Join(lines, "\n")
}

// NtfyRequest monta el aviso contra un destino ya validado. El token, cuando lo
// hay, viaja solo en Authorization: nunca en la URL ni en el cuerpo.
func NtfyRequest(ctx context.Context, t Target, cfg settings.Ntfy, token string, ev Event) (*http.Request, error) {
	if t.URL == nil || strings.TrimSpace(cfg.URL) == "" {
		return nil, ErrNoTarget
	}
	body := ntfyBody(ev)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.URL.String(), strings.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Host = t.Host
	req.ContentLength = int64(len(body))
	req.Header.Set("Content-Type", "text/plain; charset=utf-8")
	req.Header.Set("User-Agent", UserAgent)
	req.Header.Set("Title", asciiHeader(ntfyTitle(ev)))
	req.Header.Set("Priority", NtfyPriority(ev.Severity()))
	req.Header.Set("Tags", ntfyTag(ev.Kind))
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	return req, nil
}
