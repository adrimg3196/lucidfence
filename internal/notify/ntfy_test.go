package notify

import (
	"bytes"
	"context"
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

func TestNtfyPrioridadPorSeveridad(t *testing.T) {
	casos := map[string]string{
		"critical": "5", "high": "4", "medium": "3", "low": "2", "info": "1",
		"CRITICAL": "5", "  High  ": "4",
		"unknown": NtfyDefaultPriority, "": NtfyDefaultPriority, "severa": NtfyDefaultPriority,
	}
	for entrada, quiero := range casos {
		if got := NtfyPriority(entrada); got != quiero {
			t.Fatalf("NtfyPriority(%q) = %q, esperada %q", entrada, got, quiero)
		}
	}
}

func TestNtfyRequestCabecerasCuerpoYEtiquetaPorEvento(t *testing.T) {
	cfg := settings.Ntfy{URL: "https://ntfy.sh/lucidfence-alertas", Enabled: true}
	req, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), cfg, "", eventoAbierto())
	if err != nil {
		t.Fatal(err)
	}
	quiero := map[string]string{
		"Content-Type": "text/plain; charset=utf-8",
		"User-Agent":   UserAgent,
		"Title":        "[LucidFence] [HIGH] nuevo incidente",
		"Priority":     "4",
		"Tags":         "rotating_light",
	}
	for k, v := range quiero {
		if got := req.Header.Get(k); got != v {
			t.Fatalf("cabecera %s = %q, esperada %q", k, got, v)
		}
	}
	cuerpo, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatal(err)
	}
	for _, linea := range []string{"Tablet almacén", "Dispositivo: Tablet almacén", "Severidad: high", "Geocerca: hq"} {
		if !strings.Contains(string(cuerpo), linea) {
			t.Fatalf("falta %q en el cuerpo:\n%s", linea, cuerpo)
		}
	}
	etiquetas := map[string]string{
		EventIncidentOpened: "rotating_light",
		EventIncidentClosed: "white_check_mark",
		EventHandoffPending: "hourglass",
		EventActionExecuted: "gear",
		EventAlertFired:     "bell",
		"incident.reopened": NtfyDefaultTag,
	}
	for kind, tag := range etiquetas {
		ev := eventoAbierto()
		ev.Kind = kind
		req, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), cfg, "", ev)
		if err != nil {
			t.Fatal(err)
		}
		if got := req.Header.Get("Tags"); got != tag {
			t.Fatalf("evento %s: Tags = %q, esperada %q", kind, got, tag)
		}
	}
}

func TestNtfyTituloSeFuerzaAASCII(t *testing.T) {
	ev := Event{
		Kind: EventHandoffPending, At: time.Date(2026, 8, 29, 9, 31, 0, 0, time.UTC),
		DeliveryID: "dlv-0002", Handoff: handoffPendiente(),
	}
	cfg := settings.Ntfy{URL: "https://ntfy.sh/lucidfence-alertas", Enabled: true}
	req, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), cfg, "", ev)
	if err != nil {
		t.Fatal(err)
	}
	titulo := req.Header.Get("Title")
	if titulo != "[LucidFence] [CRITICAL] aprobacion pendiente" {
		t.Fatalf("Title = %q", titulo)
	}
	for _, r := range titulo {
		if r > 0x7e || r < 0x20 {
			t.Fatalf("Title lleva un carácter no ASCII: %q", titulo)
		}
	}
	cuerpo, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(cuerpo), "aprobación pendiente") {
		t.Fatalf("el cuerpo sí lleva los acentos:\n%s", cuerpo)
	}
}

func TestNtfyBearerSoloConTokenYElTokenNoViajaEnClaro(t *testing.T) {
	cfg := settings.Ntfy{URL: "https://ntfy.sh/lucidfence-alertas", Enabled: true, TokenSet: true}
	ev := eventoAbierto()

	sinToken, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), cfg, "", ev)
	if err != nil {
		t.Fatal(err)
	}
	if len(sinToken.Header.Values("Authorization")) != 0 {
		t.Fatal("sin token no debe viajar Authorization")
	}

	const token = "tk_abc123"
	req, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), cfg, token, ev)
	if err != nil {
		t.Fatal(err)
	}
	if got := req.Header.Get("Authorization"); got != "Bearer "+token {
		t.Fatalf("Authorization = %q", got)
	}
	cuerpo, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(cuerpo), token) {
		t.Fatalf("el token no puede viajar en el cuerpo:\n%s", cuerpo)
	}
	if strings.Contains(req.URL.String(), token) {
		t.Fatalf("el token no puede viajar en la URL: %s", req.URL)
	}
	// El camino canónico de registro (Event.LogValue, que usa T11) tampoco lo ve.
	var buf bytes.Buffer
	slog.New(slog.NewTextHandler(&buf, nil)).Info("entrega", "evento", ev)
	if strings.Contains(buf.String(), token) {
		t.Fatalf("el token aparece en el log: %s", buf.String())
	}
	for _, campo := range []string{"incident.opened", "dlv-0001", "high", "dev-7"} {
		if !strings.Contains(buf.String(), campo) {
			t.Fatalf("el log debería identificar la entrega con %q: %s", campo, buf.String())
		}
	}
}

func TestNtfyCuerpoNoPublicaParametrosNiDestinoSinURL(t *testing.T) {
	cfg := settings.Ntfy{URL: "https://ntfy.sh/lucidfence-alertas", Enabled: true}
	ev := Event{
		Kind: EventActionExecuted, At: time.Date(2026, 8, 29, 9, 40, 0, 0, time.UTC),
		DeliveryID: "dlv-0009",
		Action: &action.Result{
			Adapter: "simulation", OK: true, DeviceID: "dev-7", DeviceName: "Tablet almacén",
			Action: action.Message, Severity: "low",
			Params: map[string]any{"lat": 41.403629, "lng": 2.174356},
		},
	}
	req, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), cfg, "", ev)
	if err != nil {
		t.Fatal(err)
	}
	cuerpo, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatal(err)
	}
	for _, fuga := range []string{"41.403629", "2.174356", "lat", "lng"} {
		if strings.Contains(string(cuerpo), fuga) {
			t.Fatalf("fuga %q en el aviso de ntfy:\n%s", fuga, cuerpo)
		}
	}
	if _, err := NtfyRequest(context.Background(), Target{}, cfg, "", ev); err == nil {
		t.Fatal("un Target sin URL validada debe fallar")
	}
	if _, err := NtfyRequest(context.Background(), receptor(t, cfg.URL), settings.Ntfy{}, "", ev); err == nil {
		t.Fatal("una configuración sin URL debe fallar")
	}
}
