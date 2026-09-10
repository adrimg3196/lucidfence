package api

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// TestHealthPublicaElEstadoDeNotificacionSinSecretos: el operador tiene que
// poder ver por qué no le llegan los avisos (canal, destino, contadores y
// último error) sin que health filtre jamás el secreto ni el token de la URL.
func TestHealthPublicaElEstadoDeNotificacionSinSecretos(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")

	set, err := e.org.Settings()
	if err != nil {
		t.Fatal(err)
	}
	set.Webhook = settings.Webhook{URL: "https://siem.example.test/hook?token=no-debe-salir",
		Format: settings.FormatNative, Events: settings.WebhookEvents, Enabled: true, SecretSet: true}
	set.Ntfy = settings.Ntfy{URL: "https://ntfy.example.test/lucidfence", Enabled: false}
	if err := e.org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	if res, out := e.do("POST", "/api/v1/engine/run-once", nil, true); res.StatusCode != 200 {
		t.Fatalf("run-once: %d %v", res.StatusCode, out)
	}

	res, out := e.do("GET", "/api/v1/health", nil, false)
	if res.StatusCode != 200 {
		t.Fatalf("health: %d %v", res.StatusCode, out)
	}
	assertBloqueNotify(t, out)
}

// assertBloqueNotify comprueba el bloque "notify" de la respuesta de health.
// Separado del test para mantener su complejidad ciclomática bajo el límite
// del linter (gocyclo): es el mismo patrón que engine_test.go usa para las
// aserciones de la fixture demo.
func assertBloqueNotify(t *testing.T, out map[string]any) {
	t.Helper()
	bloque, ok := out["notify"].(map[string]any)
	if !ok {
		t.Fatalf("health debe llevar el bloque notify: %v", out)
	}
	wh, ok := bloque["webhook"].(map[string]any)
	if !ok {
		t.Fatalf("el bloque notify lleva un estado por canal: %v", bloque)
	}
	if wh["enabled"] != true || wh["target"] != "https://siem.example.test/hook" {
		t.Fatalf("destino redactado y canal habilitado: %v", wh)
	}
	// Sin allowlist de egress (los ajustes de fábrica no permiten ningún
	// host) el ciclo intenta la entrega y la deniega: nada entregado, todo
	// fallido y el motivo a la vista.
	if wh["delivered"] != float64(0) || wh["failed"] == float64(0) || wh["last_error"] == "" {
		t.Fatalf("las entregas denegadas por egress se cuentan y se explican: %v", wh)
	}
	if ntfy, ok := bloque["ntfy"].(map[string]any); !ok || ntfy["enabled"] != false {
		t.Fatalf("el canal apagado también se publica: %v", bloque)
	}
	raw, _ := json.Marshal(out)
	if strings.Contains(string(raw), "no-debe-salir") || strings.Contains(string(raw), "secret") {
		t.Fatalf("health no puede filtrar credenciales: %s", raw)
	}
}
