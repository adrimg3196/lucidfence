package notify

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// SignaturePrefix es el algoritmo declarado en la cabecera de firma.
const SignaturePrefix = "sha256="

// ErrNoTarget se devuelve cuando el canal no tiene URL configurada o el destino
// no pasó por Egress.Check: montar la petición sin destino validado abriría un
// socket fuera de la allowlist.
var ErrNoTarget = errors.New("canal sin destino validado")

// Sign firma los bytes exactos del cuerpo: "sha256=" + hex(HMAC-SHA256).
func Sign(secret string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	return SignaturePrefix + hex.EncodeToString(mac.Sum(nil))
}

// Verify es el ayudante del receptor: comparación en tiempo constante contra la
// cabecera tal cual llega. No se recorta: net/http ya normaliza los espacios.
func Verify(secret string, body []byte, header string) bool {
	return hmac.Equal([]byte(Sign(secret, body)), []byte(header))
}

// marshalCanonical serializa con claves ordenadas (propiedad de los mapas en
// encoding/json) y sin escapar HTML ni acentos, que es el equivalente exacto de
// json.dumps(sort_keys=True, ensure_ascii=False) de 1.x.
func marshalCanonical(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, fmt.Errorf("serializar el cuerpo de la entrega: %w", err)
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

// put añade el campo salvo que sea el valor cero, que en el sobre significa
// "no aplica". Los bool sí se escriben siempre: false es un dato.
func put(m map[string]any, key string, v any) {
	switch t := v.(type) {
	case string:
		if t == "" {
			return
		}
	case []string:
		if len(t) == 0 {
			return
		}
	case int:
		if t == 0 {
			return
		}
	case *float64:
		if t == nil {
			return
		}
		m[key] = *t
		return
	}
	m[key] = v
}

func putTime(m map[string]any, key string, t time.Time) {
	if t.IsZero() {
		return
	}
	m[key] = t.UTC().Format(time.RFC3339)
}

func putTimeP(m map[string]any, key string, t *time.Time) {
	if t == nil {
		return
	}
	putTime(m, key, *t)
}

func incidentPayload(i *incident.Incident) map[string]any {
	m := map[string]any{"id": i.ID}
	put(m, "status", string(i.Status))
	put(m, "kind", i.Kind)
	put(m, "severity", i.Severity)
	put(m, "title", i.Title)
	put(m, "recommendation", i.Recommendation)
	put(m, "device_id", i.DeviceID)
	put(m, "device_name", i.DeviceName)
	put(m, "fence_id", i.FenceID)
	put(m, "assignee", i.Assignee)
	put(m, "risk_score", i.RiskScore)
	put(m, "count", i.Count)
	put(m, "evidence_count", len(i.Evidence))
	put(m, "timeline_count", len(i.Timeline))
	putTime(m, "opened_at", i.OpenedAt)
	putTime(m, "updated_at", i.UpdatedAt)
	putTimeP(m, "acked_at", i.AckedAt)
	putTimeP(m, "closed_at", i.ClosedAt)
	return m
}

func handoffPayload(h *playbook.Handoff) map[string]any {
	m := map[string]any{"id": h.ID}
	put(m, "device_id", h.DeviceID)
	put(m, "device_name", h.DeviceName)
	put(m, "playbook_id", h.PlaybookID)
	put(m, "playbook_name", h.PlaybookName)
	put(m, "action", string(h.Action))
	put(m, "params_count", len(h.Params))
	put(m, "reason", h.Reason)
	put(m, "severity", h.Severity)
	put(m, "status", string(h.Status))
	putTime(m, "requested_at", h.RequestedAt)
	putTimeP(m, "decided_at", h.DecidedAt)
	put(m, "decided_by", h.DecidedBy)
	return m
}

func actionPayload(r *action.Result) map[string]any {
	m := map[string]any{"ok": r.OK, "dry_run": r.DryRun, "simulated": r.Simulated}
	put(m, "adapter", r.Adapter)
	put(m, "device_id", r.DeviceID)
	put(m, "device_name", r.DeviceName)
	put(m, "action", string(r.Action))
	put(m, "params_count", len(r.Params))
	put(m, "error", r.Error)
	put(m, "error_type", r.ErrorType)
	put(m, "command_id", r.CommandID)
	put(m, "note", r.Note)
	put(m, "fence_id", r.FenceID)
	put(m, "route_id", r.RouteID)
	put(m, "policy_id", r.PolicyID)
	put(m, "playbook_id", r.PlaybookID)
	put(m, "trigger", r.Trigger)
	put(m, "severity", r.Severity)
	if r.Blocked {
		m["blocked"] = true
	}
	putTime(m, "at", r.At)
	return m
}

func firingPayload(f *alert.Firing) map[string]any {
	m := map[string]any{"value": f.Value}
	put(m, "rule_id", f.RuleID)
	put(m, "rule_name", f.RuleName)
	put(m, "alert_kind", string(f.Kind))
	put(m, "device_id", f.DeviceID)
	put(m, "device_name", f.DeviceName)
	put(m, "severity", f.Severity)
	put(m, "reason", f.Reason)
	putTime(m, "at", f.At)
	return m
}

// NativePayload es el sobre propio de LucidFence: identidad de la entrega,
// titular y el objeto de dominio recortado a su lista blanca.
func NativePayload(ev Event) ([]byte, error) {
	body := map[string]any{
		"event":    ev.Kind,
		"product":  Product,
		"severity": ev.Severity(),
		"title":    ev.Title(),
	}
	put(body, "delivery_id", ev.DeliveryID)
	putTime(body, "ts", ev.At)
	switch {
	case ev.Incident != nil:
		body["incident"] = incidentPayload(ev.Incident)
	case ev.Handoff != nil:
		body["handoff"] = handoffPayload(ev.Handoff)
	case ev.Action != nil:
		body["action"] = actionPayload(ev.Action)
	case ev.Firing != nil:
		body["firing"] = firingPayload(ev.Firing)
	}
	return marshalCanonical(body)
}

// PayloadFor elige el formato del tenant. Un formato desconocido cae a nativo:
// una errata en los ajustes no puede dejar a nadie sin alertas.
func PayloadFor(format string, ev Event) ([]byte, error) {
	if strings.ToLower(strings.TrimSpace(format)) == settings.FormatOCSF {
		return OCSFPayload(ev)
	}
	return NativePayload(ev)
}

// WebhookRequest monta la petición firmada contra un destino ya validado y
// devuelve además el cuerpo, que es exactamente lo que se firmó.
func WebhookRequest(ctx context.Context, t Target, cfg settings.Webhook, secret string, ev Event) (*http.Request, []byte, error) {
	if t.URL == nil || strings.TrimSpace(cfg.URL) == "" {
		return nil, nil, ErrNoTarget
	}
	body, err := PayloadFor(cfg.Format, ev)
	if err != nil {
		return nil, nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.URL.String(), bytes.NewReader(body))
	if err != nil {
		return nil, nil, fmt.Errorf("construir la petición de webhook: %w", err)
	}
	req.Host = t.Host
	req.ContentLength = int64(len(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", UserAgent)
	req.Header.Set(EventHeader, ev.Kind)
	req.Header.Set(DeliveryHeader, ev.DeliveryID)
	if !ev.At.IsZero() {
		req.Header.Set(TimestampHeader, ev.At.UTC().Format(time.RFC3339))
	}
	if secret != "" {
		req.Header.Set(SignatureHeader, Sign(secret, body))
	}
	return req, body, nil
}
