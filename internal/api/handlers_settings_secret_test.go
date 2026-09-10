package api

import (
	"os"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/store"
)

// ajustesInvalidosEnDisco deja en settings.json un bloque que PUT
// /settings/webhooks no toca y que no valida. Llegar aquí no exige editar el
// fichero a mano: OrgStore.seedSettings escribe los ajustes de fábrica con la
// allowlist de config.json sin validarlos y config.Validate no mira los hosts,
// así que un "https://hooks.ejemplo.com/lucidfence" en config.json siembra
// exactamente este documento.
func ajustesInvalidosEnDisco(t *testing.T, e *testEnv) {
	t.Helper()
	set, err := e.org.Settings()
	if err != nil {
		t.Fatal(err)
	}
	set.Egress.Hosts = []string{"https://hooks.ejemplo.com/lucidfence"}
	if err := store.WriteJSON(e.org.Path("settings.json"), set); err != nil {
		t.Fatal(err)
	}
}

// TestSettingsWebhooksNoEscribeElSecretoSiElDocumentoNoValida: una petición
// que termina en 400 por un bloque que el cuerpo ni menciona no puede dejar
// una credencial escrita en el almacén.
func TestSettingsWebhooksNoEscribeElSecretoSiElDocumentoNoValida(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	ajustesInvalidosEnDisco(t, e)

	sec := elSecreto
	res, out := e.do("PUT", "/api/v1/settings/webhooks", webhookBody(&sec), true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("documento inválido: %d %v", res.StatusCode, out)
	}
	if detalle, _ := out["detail"].(map[string]any); detalle["field"] != "egress.hosts[0]" {
		t.Fatalf("el 400 nombra el bloque que no valida: %v", out)
	}
	if _, err := os.Stat(ficheroDelSecreto(e)); !os.IsNotExist(err) {
		t.Fatalf("un 400 no puede dejar la credencial escrita: %v", err)
	}
}

// TestSettingsWebhooksNoBorraElSecretoSiElDocumentoNoValida: el borrado es la
// otra mitad, y la cara cara. El formulario manda secret:"" para "sin
// secreto"; si el documento no valida, el 400 no puede llevarse por delante
// la credencial que el notificador está usando.
func TestSettingsWebhooksNoBorraElSecretoSiElDocumentoNoValida(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	sec := elSecreto
	if res, out := e.do("PUT", "/api/v1/settings/webhooks", webhookBody(&sec), true); res.StatusCode != 200 {
		t.Fatalf("alta: %d %v", res.StatusCode, out)
	}
	ajustesInvalidosEnDisco(t, e)

	vacio := ""
	res, out := e.do("PUT", "/api/v1/settings/webhooks", webhookBody(&vacio), true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("documento inválido: %d %v", res.StatusCode, out)
	}
	if _, err := os.Stat(ficheroDelSecreto(e)); err != nil {
		t.Fatalf("un 400 no puede borrar la credencial: %v", err)
	}
	if _, out = e.do("GET", "/api/v1/settings", nil, true); bloque(t, out, "webhook")["secret_set"] != true {
		t.Fatalf("la credencial sigue puesta y la API lo dice: %v", out)
	}
}
