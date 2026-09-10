package api

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// elSecreto es el valor que ninguna respuesta de la API puede contener.
const elSecreto = "s3cr3t-de-webhook-que-no-debe-salir"

// webhookBody es el cuerpo de PUT /settings/webhooks. Las claves son
// exactamente los tags JSON de webhookUpdate porque decodeJSON rechaza
// campos desconocidos: secret_set es de solo lectura y mandarlo es un 400.
func webhookBody(secreto *string) map[string]any {
	body := map[string]any{
		"url": "https://hooks.ejemplo.com/lucidfence", "format": "native",
		"events": []string{"incident.opened", "incident.closed"}, "enabled": true,
	}
	if secreto != nil {
		body["secret"] = *secreto
	}
	return body
}

// contieneValor busca una cadena en cualquier hoja del JSON decodificado, a
// cualquier profundidad. Es la red que impide que un secreto salga por un
// campo nuevo que nadie miró al añadirlo.
func contieneValor(v any, aguja string) bool {
	switch t := v.(type) {
	case string:
		return strings.Contains(t, aguja)
	case []any:
		for _, it := range t {
			if contieneValor(it, aguja) {
				return true
			}
		}
	case map[string]any:
		for k, it := range t {
			if strings.Contains(k, aguja) || contieneValor(it, aguja) {
				return true
			}
		}
	}
	return false
}

func bloque(t *testing.T, out map[string]any, nombre string) map[string]any {
	t.Helper()
	b, ok := out[nombre].(map[string]any)
	if !ok {
		t.Fatalf("falta el bloque %q en %v", nombre, out)
	}
	return b
}

func ficheroDelSecreto(e *testEnv) string {
	return filepath.Join(e.st.SecretsDir("default"), "webhook_secret.json")
}

func TestSettingsGetNuncaExponeElSecreto(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	sec := elSecreto
	res, out := e.do("PUT", "/api/v1/settings/webhooks", webhookBody(&sec), true)
	if res.StatusCode != 200 {
		t.Fatalf("guardar el webhook: %d %v", res.StatusCode, out)
	}
	if wh := bloque(t, out, "webhook"); wh["secret_set"] != true || wh["url"] != "https://hooks.ejemplo.com/lucidfence" {
		t.Fatalf("la respuesta declara el secreto puesto sin devolverlo: %v", wh)
	}
	if contieneValor(out, elSecreto) {
		t.Fatalf("el secreto viaja en la respuesta del PUT: %v", out)
	}
	info, err := os.Stat(ficheroDelSecreto(e))
	if err != nil {
		t.Fatal(err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Fatalf("el fichero del secreto es %v, quiero 0600", perm)
	}
	res, out = e.do("GET", "/api/v1/settings", nil, true)
	if res.StatusCode != 200 || bloque(t, out, "webhook")["secret_set"] != true {
		t.Fatalf("GET: %d %v", res.StatusCode, out)
	}
	if contieneValor(out, elSecreto) {
		t.Fatalf("el secreto viaja en GET /settings: %v", out)
	}
	if bloque(t, out, "ntfy")["token_set"] != false {
		t.Fatalf("ntfy no tiene token: %v", out)
	}
	if _, hay := bloque(t, out, "risk")["off_hours_start"]; !hay {
		t.Fatalf("GET publica el contexto de riesgo: %v", out)
	}
}

func TestSettingsWebhooksSecretoAusenteVacioYNuevo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	sec := elSecreto
	if res, out := e.do("PUT", "/api/v1/settings/webhooks", webhookBody(&sec), true); res.StatusCode != 200 {
		t.Fatalf("alta: %d %v", res.StatusCode, out)
	}
	// Sin campo secret: el guardado normal del formulario no puede borrar la
	// credencial.
	res, out := e.do("PUT", "/api/v1/settings/webhooks", webhookBody(nil), true)
	if res.StatusCode != 200 || bloque(t, out, "webhook")["secret_set"] != true {
		t.Fatalf("sin campo secret el existente se conserva: %d %v", res.StatusCode, out)
	}
	if _, err := os.Stat(ficheroDelSecreto(e)); err != nil {
		t.Fatalf("el fichero del secreto debe seguir ahí: %v", err)
	}
	// Cadena vacía: borrar es una intención explícita.
	vacio := ""
	res, out = e.do("PUT", "/api/v1/settings/webhooks", webhookBody(&vacio), true)
	if res.StatusCode != 200 || bloque(t, out, "webhook")["secret_set"] != false {
		t.Fatalf("secret vacío borra el secreto: %d %v", res.StatusCode, out)
	}
	if _, err := os.Stat(ficheroDelSecreto(e)); !os.IsNotExist(err) {
		t.Fatalf("el fichero del secreto debe haber desaparecido: %v", err)
	}
	if res, out = e.do("GET", "/api/v1/settings", nil, true); bloque(t, out, "webhook")["secret_set"] != false {
		t.Fatalf("GET tras el borrado: %d %v", res.StatusCode, out)
	}
}

func TestSettingsEnforcementSeAplicaEnElActo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	body := map[string]any{"mode": "enforce", "live_actions": []string{"message"},
		"allow_wipe": false, "wipe_allowlist": []string{}, "action_cooldown_seconds": 3600}
	res, out := e.do("PUT", "/api/v1/settings/enforcement", body, true)
	if res.StatusCode != 200 || bloque(t, out, "enforcement")["mode"] != "enforce" {
		t.Fatalf("PUT enforcement: %d %v", res.StatusCode, out)
	}
	// Sin ejecutar un ciclo: el motor ya tiene el enforcement nuevo.
	res, out = e.do("GET", "/api/v1/engine/status", nil, true)
	enf := bloque(t, out, "enforcement")
	live, _ := enf["live_actions"].([]any)
	if res.StatusCode != 200 || enf["mode"] != "enforce" || len(live) != 1 || live[0] != "message" {
		t.Fatalf("el estado del motor debe reflejar el enforcement guardado: %d %v", res.StatusCode, out)
	}
	// El bloque del webhook no se ha tocado.
	if _, out = e.do("GET", "/api/v1/settings", nil, true); bloque(t, out, "webhook")["enabled"] != false {
		t.Fatalf("un PUT de enforcement no pisa el webhook: %v", out)
	}
	body["mode"] = "vigilante"
	res, out = e.do("PUT", "/api/v1/settings/enforcement", body, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("modo desconocido: %d %v", res.StatusCode, out)
	}
	if msg, _ := out["error"].(string); !strings.Contains(msg, "enforcement.mode") {
		t.Fatalf("el 400 nombra el campo en el mensaje: %v", out)
	}
	if detalle, _ := out["detail"].(map[string]any); detalle["field"] != "enforcement.mode" {
		t.Fatalf("el 400 nombra el campo en el detail: %v", out)
	}
}

// TestSettingsEnforcementNormalizaAntesDeAplicar (revisión final del hito):
// el contrato admite live_actions nula y el guardarraíl la trata como la
// lista vacía. Lo que se responde, lo que queda en disco y lo que gatea el
// motor tienen que ser el mismo valor; antes de esta revisión el disco decía
// [] y el motor se quedaba con nil.
func TestSettingsEnforcementNormalizaAntesDeAplicar(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	body := map[string]any{"mode": "enforce", "live_actions": nil, "allow_wipe": true,
		"wipe_allowlist": []string{}, "action_cooldown_seconds": 3600}
	res, out := e.do("PUT", "/api/v1/settings/enforcement", body, true)
	if res.StatusCode != 200 {
		t.Fatalf("PUT enforcement con live_actions nula: %d %v", res.StatusCode, out)
	}
	for _, caso := range []struct {
		nombre string
		doc    map[string]any
	}{
		{"la respuesta del PUT", out},
		{"GET /settings", segundo(e.do("GET", "/api/v1/settings", nil, true))},
		{"GET /engine/status", segundo(e.do("GET", "/api/v1/engine/status", nil, true))},
	} {
		live, ok := bloque(t, caso.doc, "enforcement")["live_actions"].([]any)
		if !ok || len(live) != 0 {
			t.Fatalf("%s debe publicar la lista vacía, no nula: %v", caso.nombre, caso.doc["enforcement"])
		}
	}
}

// segundo devuelve solo el cuerpo decodificado de e.do, para poder usarlo
// dentro de una tabla.
func segundo(_ *http.Response, out map[string]any) map[string]any { return out }

// TestSettingsNtfyGuardaElCanalYElTokenEsDeSoloEscritura (revisión final del
// hito): sin PUT /settings/ntfy el canal que la spec §4.1/§6.4 exige y que
// internal/notify entrega entero solo se podía activar editando settings.json
// a mano. Mismo argumento que M2-C3 para PUT /settings/risk.
func TestSettingsNtfyGuardaElCanalYElTokenEsDeSoloEscritura(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	const token = "tk-de-ntfy-que-no-debe-salir"
	body := map[string]any{"url": "https://ntfy.ejemplo.com/lucidfence", "enabled": true, "token": token}
	res, out := e.do("PUT", "/api/v1/settings/ntfy", body, true)
	ntfy := bloque(t, out, "ntfy")
	if res.StatusCode != 200 || ntfy["enabled"] != true || ntfy["token_set"] != true {
		t.Fatalf("alta de ntfy: %d %v", res.StatusCode, out)
	}
	if contieneValor(out, token) {
		t.Fatalf("el token no puede salir en ninguna respuesta: %v", out)
	}
	if _, err := os.Stat(filepath.Join(e.st.SecretsDir("default"), "ntfy_token.json")); err != nil {
		t.Fatalf("el token se guarda donde lo busca el notificador: %v", err)
	}
	// Sin campo token el guardado normal del formulario no borra nada.
	delete(body, "token")
	if res, out = e.do("PUT", "/api/v1/settings/ntfy", body, true); res.StatusCode != 200 || bloque(t, out, "ntfy")["token_set"] != true {
		t.Fatalf("sin campo token el existente se conserva: %d %v", res.StatusCode, out)
	}
	// Cadena vacía: borrar es una intención explícita.
	body["token"] = ""
	if res, out = e.do("PUT", "/api/v1/settings/ntfy", body, true); res.StatusCode != 200 || bloque(t, out, "ntfy")["token_set"] != false {
		t.Fatalf("token vacío borra el token: %d %v", res.StatusCode, out)
	}
	// Un canal activo sin URL es un 400 que nombra el campo.
	res, out = e.do("PUT", "/api/v1/settings/ntfy", map[string]any{"url": "", "enabled": true}, true)
	detalle, _ := out["detail"].(map[string]any)
	if res.StatusCode != 400 || out["code"] != "invalid" || detalle["field"] != "ntfy.url" {
		t.Fatalf("ntfy activo sin URL: %d %v", res.StatusCode, out)
	}
	// El webhook no se ha tocado en ninguno de los PUT anteriores.
	if _, out = e.do("GET", "/api/v1/settings", nil, true); bloque(t, out, "webhook")["enabled"] != false {
		t.Fatalf("un PUT de ntfy no pisa el webhook: %v", out)
	}
}

func TestSettingsEgressPersisteYValidateNoAbreSocket(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	var visitas atomic.Int64
	receptor := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		visitas.Add(1)
		w.WriteHeader(http.StatusNoContent)
	}))
	defer receptor.Close()

	res, out := e.do("PUT", "/api/v1/settings/egress",
		map[string]any{"hosts": []string{"hooks.ejemplo.com"}, "allow_private": false}, true)
	hosts, _ := bloque(t, out, "egress")["hosts"].([]any)
	if res.StatusCode != 200 || len(hosts) != 1 || hosts[0] != "hooks.ejemplo.com" ||
		bloque(t, out, "egress")["allow_private"] != false {
		t.Fatalf("PUT egress: %d %v", res.StatusCode, out)
	}

	candidato := map[string]any{
		"webhook": map[string]any{"url": receptor.URL + "/hook", "format": "native",
			"events": []string{"incident.opened"}, "enabled": true, "secret_set": false},
	}
	res, out = e.do("POST", "/api/v1/settings/validate", candidato, true)
	if res.StatusCode != 200 || out["ok"] != false {
		t.Fatalf("validate con un destino fuera de la allowlist: %d %v", res.StatusCode, out)
	}
	canales, _ := out["channels"].([]any)
	wh, _ := canales[0].(map[string]any)
	motivo, _ := wh["reason"].(string)
	if wh["channel"] != "webhook" || wh["ok"] != false || !strings.Contains(motivo, "allowlist") {
		t.Fatalf("el canal explica por qué no pasaría: %v", canales)
	}

	candidato["egress"] = map[string]any{"hosts": []string{"127.0.0.1"}, "allow_private": true}
	res, out = e.do("POST", "/api/v1/settings/validate", candidato, true)
	canales, _ = out["channels"].([]any)
	wh, _ = canales[0].(map[string]any)
	if res.StatusCode != 200 || wh["ok"] != true {
		t.Fatalf("con la allowlist correcta el destino se acepta: %d %v", res.StatusCode, out)
	}
	if got := visitas.Load(); got != 0 {
		t.Fatalf("validar no envía nada: %d peticiones al receptor", got)
	}
	// Y no ha guardado nada: la allowlist sigue siendo la del PUT.
	if _, out = e.do("GET", "/api/v1/settings", nil, true); len(bloque(t, out, "egress")["hosts"].([]any)) != 1 {
		t.Fatalf("validate no persiste: %v", out)
	}
}

func TestSettingsSonDeAdminYNoDeOperator(t *testing.T) {
	e := newRoleEnv(t)
	e.as(auth.Admin)
	if res, out := e.do("GET", "/api/v1/settings", nil, true); res.StatusCode != 200 {
		t.Fatalf("un admin lee los ajustes: %d %v", res.StatusCode, out)
	}
	body := map[string]any{"mode": "observe", "live_actions": []string{},
		"allow_wipe": false, "wipe_allowlist": []string{}, "action_cooldown_seconds": 60}
	if res, out := e.do("PUT", "/api/v1/settings/enforcement", body, true); res.StatusCode != 200 {
		t.Fatalf("un admin escribe el enforcement: %d %v", res.StatusCode, out)
	}
	e.as(auth.Operator)
	if res, out := e.do("GET", "/api/v1/settings", nil, true); res.StatusCode != 403 || out["code"] != "forbidden" {
		t.Fatalf("un operator no tiene engine:config: %d %v", res.StatusCode, out)
	}
	if res, out := e.do("PUT", "/api/v1/settings/enforcement", body, true); res.StatusCode != 403 {
		t.Fatalf("un operator no cambia el enforcement: %d %v", res.StatusCode, out)
	}
}

func TestSettingsErrorInternoNoFiltraLaRutaDelFichero(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	// settings.json como directorio: el store no puede leerlo y el handler
	// tiene que responder sin contar dónde vive el fichero. El motor ya
	// sembró el fichero al construir su notificador (newNotifier lee
	// org.Settings()), así que hay que quitarlo antes de poner el
	// directorio en su lugar.
	if err := os.Remove(e.org.Path("settings.json")); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(e.org.Path("settings.json"), 0o700); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("GET", "/api/v1/settings", nil, true)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("error interno: %d %v", res.StatusCode, out)
	}
	if strings.Contains(e.logs.String(), "op=settings.get") == false {
		t.Fatalf("el log tiene que llevar el paso: %s", e.logs.String())
	}
}

// TestSettingsRiskPersisteYNombraElCampo cubre la ruling M2-C3: PUT
// /settings/risk valida y persiste el bloque de riesgo por separado (el
// esqueleto del brief no la lista; GET /api/v1/settings ya la devuelve
// desde T7, así que sin este PUT el bloque risk sería de solo lectura).
func TestSettingsRiskPersisteYNombraElCampo(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	body := map[string]any{
		"shift_zones":     map[string]any{"dev-001": "hq"},
		"zone_risk":       map[string]any{"hq": 0.2},
		"off_hours_start": 20,
		"off_hours_end":   7,
	}
	res, out := e.do("PUT", "/api/v1/settings/risk", body, true)
	if res.StatusCode != 200 || bloque(t, out, "risk")["off_hours_start"] != float64(20) {
		t.Fatalf("PUT risk: %d %v", res.StatusCode, out)
	}
	// La persistencia se comprueba leyendo el store, no solo lo que devuelve
	// la respuesta.
	set, err := e.org.Settings()
	if err != nil {
		t.Fatal(err)
	}
	if set.Risk.ShiftZones["dev-001"] != "hq" || set.Risk.ZoneRisk["hq"] != 0.2 {
		t.Fatalf("el store no guardó el bloque de riesgo: %+v", set.Risk)
	}

	body["off_hours_start"] = 99
	res, out = e.do("PUT", "/api/v1/settings/risk", body, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("hora fuera de rango: %d %v", res.StatusCode, out)
	}
	if detalle, _ := out["detail"].(map[string]any); detalle["field"] != "risk.off_hours_start" {
		t.Fatalf("el 400 nombra el campo en el detail: %v", out)
	}
}

// TestSettingsRiskNoEsDeOperator cubre la mitad "403 sin capacidad" de la
// ruling M2-C3: engine:config es de owner y admin, no de operator.
func TestSettingsRiskNoEsDeOperator(t *testing.T) {
	e := newRoleEnv(t)
	e.as(auth.Operator)
	body := map[string]any{"shift_zones": map[string]any{}, "zone_risk": map[string]any{},
		"off_hours_start": 20, "off_hours_end": 7}
	if res, out := e.do("PUT", "/api/v1/settings/risk", body, true); res.StatusCode != 403 || out["code"] != "forbidden" {
		t.Fatalf("un operator no cambia el riesgo: %d %v", res.StatusCode, out)
	}
}
