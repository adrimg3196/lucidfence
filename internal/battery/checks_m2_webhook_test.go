package battery

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
)

func signBody(secret string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}

func sendDelivery(t *testing.T, url string, body []byte, sig string) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set(eventHeader, "alert.fired")
	req.Header.Set(signatureHeader, sig)
	req.Header.Set(deliveryHeader, "battery-test-delivery")
	req.Header.Set(timestampHeader, time.Now().UTC().Format(time.RFC3339))
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	_ = resp.Body.Close()
}

// webhookState recuerda la última configuración de webhook mandada por PUT,
// para que el servidor de mentira sepa a dónde y con qué secreto entregar.
type webhookState struct {
	mu      sync.Mutex
	url     string
	secret  string
	format  string
	enabled bool
}

func (s *webhookState) put(body map[string]any) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.url, _ = body["url"].(string)
	s.secret, _ = body["secret"].(string)
	s.format, _ = body["format"].(string)
	s.enabled, _ = body["enabled"].(bool)
}

func (s *webhookState) snapshot() (url, secret, format string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.url, s.secret, s.format
}

// apagado dice si el último PUT dejó el canal sin URL y deshabilitado, que es
// lo que los dos checks tienen que hacer al salir.
func (s *webhookState) apagado() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return !s.enabled && s.url == ""
}

// webhookDispatcherServer acepta la configuración de egress/webhook, la
// creación de una regla de alerta y su evaluación (una aserción de que casa,
// count>0, sin más efecto) y, en cada run-once, llama a deliver: el propio
// caso de prueba decide cómo de fiel (o infiel) es la entrega al Receiver
// real. Refleja que quien dispara la entrega es el ciclo (M2-R65), no la
// vista previa de /alerts/evaluate.
func webhookDispatcherServer(t *testing.T, deliver func(t *testing.T, url, secret, format string)) *httptest.Server {
	t.Helper()
	srv, _ := webhookDispatcherServerCon(t, deliver)
	return srv
}

// webhookDispatcherServerCon es webhookDispatcherServer devolviendo además el
// estado compartido, para los casos que necesitan afirmar sobre la última
// configuración con la que el check se va (por ejemplo, que se apagó).
func webhookDispatcherServerCon(t *testing.T, deliver func(t *testing.T, url, secret, format string)) (*httptest.Server, *webhookState) {
	t.Helper()
	state := &webhookState{}
	srv := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"PUT /api/v1/settings/egress": jsonOK(200, map[string]any{}),
		"PUT /api/v1/settings/webhooks": func(w http.ResponseWriter, r *http.Request) {
			var body map[string]any
			_ = json.NewDecoder(r.Body).Decode(&body)
			state.put(body)
			jsonOK(200, map[string]any{"webhook": map[string]any{"secret_set": true}})(w, r)
		},
		"POST /api/v1/alerts":          jsonOK(201, map[string]any{}),
		"POST /api/v1/alerts/evaluate": jsonOK(200, map[string]any{"count": 1}),
		"POST /api/v1/engine/run-once": func(w http.ResponseWriter, r *http.Request) {
			url, secret, format := state.snapshot()
			deliver(t, url, secret, format)
			jsonOK(200, map[string]any{})(w, r)
		},
	})
	return srv, state
}

func deliverGood(t *testing.T, url, secret, format string) {
	t.Helper()
	body := map[string]any{"message": "riesgo alto"}
	if format == "ocsf" {
		body = map[string]any{"class_uid": 2004, "category_uid": 2, "severity_id": 3}
	}
	raw, _ := json.Marshal(body)
	sendDelivery(t, url, raw, signBody(secret, raw))
}

func deliverBadSignature(t *testing.T, url, _, _ string) {
	t.Helper()
	raw, _ := json.Marshal(map[string]any{"message": "riesgo alto"})
	sendDelivery(t, url, raw, "sha256=00")
}

func deliverBadOCSF(t *testing.T, url, secret, _ string) {
	t.Helper()
	raw, _ := json.Marshal(map[string]any{"class_uid": 1001, "location": map[string]any{"lat": 40.42, "lng": -3.71}})
	sendDelivery(t, url, raw, signBody(secret, raw))
}

func TestCheckWebhookSignedGoodAndBad(t *testing.T) {
	good := webhookDispatcherServer(t, deliverGood)
	if err := checkWebhookSigned(context.Background(), envFor(good)); err != nil {
		t.Fatalf("entrega válida debía pasar: %v", err)
	}

	orig := deliveryTimeout
	deliveryTimeout = 300 * time.Millisecond
	t.Cleanup(func() { deliveryTimeout = orig })
	bad := webhookDispatcherServer(t, deliverBadSignature)
	if err := checkWebhookSigned(context.Background(), envFor(bad)); err == nil {
		t.Fatal("una firma alterada no debía dar el check por bueno")
	}
}

func TestCheckOCSFNoCoordsGoodAndBad(t *testing.T) {
	good := webhookDispatcherServer(t, deliverGood)
	if err := checkOCSFNoCoords(context.Background(), envFor(good)); err != nil {
		t.Fatalf("payload OCSF válido debía pasar: %v", err)
	}

	orig := deliveryTimeout
	deliveryTimeout = 300 * time.Millisecond
	t.Cleanup(func() { deliveryTimeout = orig })
	bad := webhookDispatcherServer(t, deliverBadOCSF)
	if err := checkOCSFNoCoords(context.Background(), envFor(bad)); err == nil {
		t.Fatal("class_uid erróneo y coordenadas presentes no debían dar el check por bueno")
	}
}

// TestLosChecksDelWebhookDejanElCanalApagado: el Receiver muere con el check
// y el webhook no puede quedarse apuntando a su puerto. Si se queda, cada
// evento suscrito de los checks siguientes se entrega contra un puerto
// cerrado con 3 intentos y backoff dentro del ciclo (~3 s por evento).
func TestLosChecksDelWebhookDejanElCanalApagado(t *testing.T) {
	casos := map[string]func(context.Context, *Env) error{
		"webhook firmado": checkWebhookSigned,
		"OCSF":            checkOCSFNoCoords,
	}
	for nombre, check := range casos {
		srv, state := webhookDispatcherServerCon(t, deliverGood)
		if err := check(context.Background(), envFor(srv)); err != nil {
			t.Fatalf("%s: %v", nombre, err)
		}
		if !state.apagado() {
			url, _, _ := state.snapshot()
			t.Fatalf("%s deja el webhook apagado al salir: url=%q", nombre, url)
		}
	}
}

func TestReceiverVerificaFirmaYRegistraCabeceras(t *testing.T) {
	rcv, stop, err := StartReceiver("secreto-receptor-2026")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = stop() }()
	body := []byte(`{"hola":"mundo"}`)
	goodSig := signBody(rcv.Secret, body)
	sendDelivery(t, rcv.URL, body, goodSig)
	altered := goodSig[:len(goodSig)-1] + "0"
	if altered == goodSig {
		altered = goodSig[:len(goodSig)-1] + "1"
	}
	sendDelivery(t, rcv.URL, body, altered)

	got := rcv.Deliveries()
	if len(got) != 2 {
		t.Fatalf("esperaba 2 entregas, tengo %d", len(got))
	}
	if !got[0].Valid {
		t.Fatalf("la firma correcta debía validar: %+v", got[0])
	}
	if got[1].Valid {
		t.Fatalf("una firma alterada un carácter no debía validar: %+v", got[1])
	}
	if got[0].Event != "alert.fired" {
		t.Fatalf("evento=%q, quiero alert.fired", got[0].Event)
	}
	if string(got[0].Body) != string(body) {
		t.Fatalf("cuerpo=%q, quiero %q", got[0].Body, body)
	}
}

func TestReceiverRechazaSinCabecerasCompletas(t *testing.T) {
	rcv, stop, err := StartReceiver("secreto-receptor-incompleto")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = stop() }()
	req, err := http.NewRequest(http.MethodPost, rcv.URL, bytes.NewReader([]byte(`{}`)))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set(eventHeader, "incident.opened")
	req.Header.Set(signatureHeader, signBody(rcv.Secret, []byte(`{}`)))
	// deliberadamente sin X-LucidFence-Delivery ni X-LucidFence-Timestamp.
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	_ = resp.Body.Close()

	got := rcv.Deliveries()
	if len(got) != 1 || got[0].Valid {
		t.Fatalf("una entrega sin las cuatro cabeceras no debía marcarse válida: %+v", got)
	}
}

// TestPutEgressAndWebhookLeeElSecretoAnidado fija la forma real de la
// respuesta de PUT /settings/webhooks: persistSettings responde con el
// documento entero de ajustes (settingsView), donde el indicador vive en
// webhook.secret_set, nunca en la raíz.
func TestPutEgressAndWebhookLeeElSecretoAnidado(t *testing.T) {
	rcv, stop, err := StartReceiver("secreto-forma-anidada")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = stop() }()

	nested := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"PUT /api/v1/settings/egress": jsonOK(200, map[string]any{}),
		"PUT /api/v1/settings/webhooks": jsonOK(200, map[string]any{
			"schema_version": 1,
			"webhook":        map[string]any{"url": rcv.URL, "format": "native", "enabled": true, "secret_set": true},
		}),
	})
	if err := putEgressAndWebhook(context.Background(), envFor(nested), rcv, "native"); err != nil {
		t.Fatalf("la respuesta real de settings debía bastar: %v", err)
	}

	sinSecreto := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"PUT /api/v1/settings/egress": jsonOK(200, map[string]any{}),
		"PUT /api/v1/settings/webhooks": jsonOK(200, map[string]any{
			"webhook": map[string]any{"url": rcv.URL, "secret_set": false},
		}),
	})
	if err := putEgressAndWebhook(context.Background(), envFor(sinSecreto), rcv, "native"); err == nil {
		t.Fatal("un webhook guardado sin secreto no debía darse por bueno")
	}
}
