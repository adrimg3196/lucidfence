package notify

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net"
	"net/url"
	"os"
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// receptor es el Target ya validado que devolvería Egress.Check: esta tarea no
// resuelve ni conecta, solo monta la petición.
func receptor(t *testing.T, raw string) Target {
	t.Helper()
	u, err := url.Parse(raw)
	if err != nil {
		t.Fatalf("URL de prueba inválida: %v", err)
	}
	return Target{URL: u, Host: u.Hostname(), Port: "443", IPs: []net.IP{net.ParseIP("203.0.113.10")}}
}

func score(v float64) *float64 { return &v }

// incidenteAbierto es el mismo incidente que fija el fichero dorado OCSF.
func incidenteAbierto() *incident.Incident {
	return &incident.Incident{
		ID: "inc-geofence_exit-dev-7", DeviceID: "dev-7", DeviceName: "Tablet almacén",
		Kind: "geofence_exit", Severity: "high", Status: incident.StatusOpen,
		Title:          "Tablet almacén está fuera de la geocerca Almacén central",
		Recommendation: "Valida la última ubicación conocida y ejecuta una acción UEM si procede.",
		FenceID:        "hq", Assignee: "ana.soto", RiskScore: score(82.5), Count: 3,
		Evidence:  []string{"fuera de la geocerca hq desde las 09:00"},
		OpenedAt:  time.Date(2026, 8, 29, 9, 0, 0, 0, time.UTC),
		UpdatedAt: time.Date(2026, 8, 29, 9, 30, 0, 0, time.UTC),
	}
}

func eventoAbierto() Event {
	return Event{
		Kind:       EventIncidentOpened,
		At:         time.Date(2026, 8, 29, 9, 30, 0, 0, time.UTC),
		DeliveryID: "dlv-0001",
		Incident:   incidenteAbierto(),
	}
}

type vector struct {
	Nombre    string `json:"nombre"`
	Secret    string `json:"secret"`
	Body      string `json:"body"`
	Signature string `json:"signature"`
}

func cargarVectores(t *testing.T) []vector {
	t.Helper()
	raw, err := os.ReadFile("testdata/hmac_vectors.json")
	if err != nil {
		t.Fatalf("leer vectores: %v", err)
	}
	var doc struct {
		Vectors []vector `json:"vectors"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("vectores inválidos: %v", err)
	}
	if len(doc.Vectors) == 0 {
		t.Fatal("el fichero de vectores está vacío")
	}
	return doc.Vectors
}

func TestSignCoincideConLosVectoresDe1x(t *testing.T) {
	for _, v := range cargarVectores(t) {
		got := Sign(v.Secret, []byte(v.Body))
		if got != v.Signature {
			t.Fatalf("%s: firma %q, esperada %q", v.Nombre, got, v.Signature)
		}
		if !strings.HasPrefix(got, SignaturePrefix) {
			t.Fatalf("%s: la firma debe empezar por %q", v.Nombre, SignaturePrefix)
		}
		if !Verify(v.Secret, []byte(v.Body), v.Signature) {
			t.Fatalf("%s: Verify rechaza su propia firma", v.Nombre)
		}
	}
}

func TestVerifyRechazaFirmaAlteradaSecretoDistintoYEspacios(t *testing.T) {
	body := []byte(`{"event":"incident.opened"}`)
	firma := Sign("s3cr3t", body)

	// Un bit alterado: se cambia el último dígito hexadecimal.
	ultimo := firma[len(firma)-1]
	otro := byte('0')
	if ultimo == '0' {
		otro = '1'
	}
	alterada := firma[:len(firma)-1] + string(otro)

	casos := []struct {
		nombre string
		secret string
		body   []byte
		header string
	}{
		{"firma alterada en un dígito", "s3cr3t", body, alterada},
		{"secreto distinto", "otra-clave", body, firma},
		{"cuerpo con un byte de más", "s3cr3t", append(body, 'x'), firma},
		{"cabecera con espacio delante", "s3cr3t", body, " " + firma},
		{"cabecera con espacio detrás", "s3cr3t", body, firma + " "},
		{"cabecera vacía", "s3cr3t", body, ""},
		{"cabecera sin prefijo", "s3cr3t", body, strings.TrimPrefix(firma, SignaturePrefix)},
	}
	for _, c := range casos {
		if Verify(c.secret, c.body, c.header) {
			t.Fatalf("%s: Verify debería rechazar", c.nombre)
		}
	}
	if !Verify("s3cr3t", body, firma) {
		t.Fatal("Verify debería aceptar la firma correcta")
	}
}

func TestNativePayloadEsDeterministaYConClavesOrdenadas(t *testing.T) {
	ev := eventoAbierto()
	primero, err := NativePayload(ev)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 100; i++ {
		otro, err := NativePayload(eventoAbierto())
		if err != nil {
			t.Fatal(err)
		}
		if string(otro) != string(primero) {
			t.Fatalf("serialización %d difiere:\n%s\n%s", i, primero, otro)
		}
	}
	// Las claves del sobre salen en orden alfabético porque es un map[string]any
	// y encoding/json las ordena. Se leen con el decodificador, no buscando
	// subcadenas, para no confundirlas con las del objeto anidado.
	dec := json.NewDecoder(bytes.NewReader(primero))
	if _, err := dec.Token(); err != nil {
		t.Fatal(err)
	}
	var claves []string
	for dec.More() {
		tok, err := dec.Token()
		if err != nil {
			t.Fatal(err)
		}
		nombre, ok := tok.(string)
		if !ok {
			t.Fatalf("clave inesperada %v", tok)
		}
		claves = append(claves, nombre)
		var descartar json.RawMessage
		if err := dec.Decode(&descartar); err != nil {
			t.Fatal(err)
		}
	}
	quiero := []string{"delivery_id", "event", "incident", "product", "severity", "title", "ts"}
	if !slices.Equal(claves, quiero) {
		t.Fatalf("claves del sobre %v, esperadas %v", claves, quiero)
	}
	cuerpo := string(primero)
	if strings.Contains(cuerpo, `\u00e9`) {
		t.Fatalf("el cuerpo escapa los acentos en vez de emitirlos en UTF-8: %s", cuerpo)
	}
	if !strings.Contains(cuerpo, "Tablet almacén") {
		t.Fatalf("el cuerpo debería llevar el nombre con acentos tal cual: %s", cuerpo)
	}
}

func TestNativePayloadNoPublicaLosParametrosDeUnaAccion(t *testing.T) {
	ev := Event{
		Kind: EventActionExecuted, At: time.Date(2026, 8, 29, 9, 40, 0, 0, time.UTC),
		DeliveryID: "dlv-0009",
		Action: &action.Result{
			Adapter: "simulation", OK: true, DeviceID: "dev-7", DeviceName: "Tablet almacén",
			Action: action.Lock, DryRun: true, Severity: "medium", PolicyID: "pol-1",
			At: time.Date(2026, 8, 29, 9, 40, 0, 0, time.UTC),
			Params: map[string]any{
				"lat": 41.403629, "lng": 2.174356,
				"location": "Carrer de Mallorca 401, Barcelona",
			},
		},
	}
	cuerpo, err := NativePayload(ev)
	if err != nil {
		t.Fatal(err)
	}
	for _, fuga := range []string{"41.403629", "2.174356", "Mallorca", `"lat"`, `"lng"`, `"location"`, `"params"`} {
		if strings.Contains(string(cuerpo), fuga) {
			t.Fatalf("fuga %q en el sobre nativo: %s", fuga, cuerpo)
		}
	}
	if !strings.Contains(string(cuerpo), `"params_count":3`) {
		t.Fatalf("el sobre debería declarar cuántos parámetros llevaba: %s", cuerpo)
	}
}

func TestPayloadForCaeANativoConFormatoDesconocido(t *testing.T) {
	ev := eventoAbierto()
	for _, formato := range []string{settings.FormatOCSF, "OCSF", "  ocsf  "} {
		cuerpo, err := PayloadFor(formato, ev)
		if err != nil {
			t.Fatal(err)
		}
		var m map[string]any
		if err := json.Unmarshal(cuerpo, &m); err != nil {
			t.Fatal(err)
		}
		if m["class_uid"] != float64(OCSFClassUID) {
			t.Fatalf("formato %q debería ser OCSF: %s", formato, cuerpo)
		}
		if _, hay := m["incident"]; hay {
			t.Fatalf("el evento OCSF viaja desnudo, sin sobre nativo: %s", cuerpo)
		}
	}
	for _, formato := range []string{settings.FormatNative, "", "ocsv", "native "} {
		cuerpo, err := PayloadFor(formato, ev)
		if err != nil {
			t.Fatal(err)
		}
		var m map[string]any
		if err := json.Unmarshal(cuerpo, &m); err != nil {
			t.Fatal(err)
		}
		if m["event"] != EventIncidentOpened {
			t.Fatalf("formato %q debería caer a nativo: %s", formato, cuerpo)
		}
	}
}

func TestWebhookRequestLlevaLasCuatroCabecerasYFirmaElCuerpoEnviado(t *testing.T) {
	ev := eventoAbierto()
	cfg := settings.Webhook{URL: "https://receptor.example/hook", Format: settings.FormatNative, Enabled: true, SecretSet: true}
	req, cuerpo, err := WebhookRequest(context.Background(), receptor(t, cfg.URL), cfg, "s3cr3t", ev)
	if err != nil {
		t.Fatal(err)
	}
	if req.Method != "POST" || req.URL.String() != cfg.URL {
		t.Fatalf("petición inesperada: %s %s", req.Method, req.URL)
	}
	if req.Host != "receptor.example" {
		t.Fatalf("Host debería quedar pinneado al nombre validado, got %q", req.Host)
	}
	quiero := map[string]string{
		"Content-Type":  "application/json",
		"User-Agent":    UserAgent,
		EventHeader:     EventIncidentOpened,
		DeliveryHeader:  "dlv-0001",
		TimestampHeader: "2026-08-29T09:30:00Z",
	}
	for k, v := range quiero {
		if got := req.Header.Get(k); got != v {
			t.Fatalf("cabecera %s = %q, esperada %q", k, got, v)
		}
	}
	// Los bytes firmados son exactamente los enviados.
	enviado, err := io.ReadAll(req.Body)
	if err != nil {
		t.Fatal(err)
	}
	if string(enviado) != string(cuerpo) {
		t.Fatalf("el cuerpo devuelto no es el enviado:\n%s\n%s", cuerpo, enviado)
	}
	if int64(len(cuerpo)) != req.ContentLength {
		t.Fatalf("ContentLength %d, cuerpo %d", req.ContentLength, len(cuerpo))
	}
	if !Verify("s3cr3t", enviado, req.Header.Get(SignatureHeader)) {
		t.Fatalf("la firma no verifica sobre los bytes enviados: %s", req.Header.Get(SignatureHeader))
	}
}

func TestWebhookRequestSinSecretoNoFirmaYSinDestinoFalla(t *testing.T) {
	ev := eventoAbierto()
	cfg := settings.Webhook{URL: "https://receptor.example/hook", Enabled: true}
	req, _, err := WebhookRequest(context.Background(), receptor(t, cfg.URL), cfg, "", ev)
	if err != nil {
		t.Fatal(err)
	}
	// Se consulta con Values, no indexando el mapa: net/http canonicaliza las
	// claves ("X-Lucidfence-Signature"), así que indexar con la constante nunca
	// encontraría nada y la comprobación sería vacía.
	if len(req.Header.Values(SignatureHeader)) != 0 {
		t.Fatal("sin secreto no debe viajar la cabecera de firma")
	}
	if _, _, err := WebhookRequest(context.Background(), Target{}, cfg, "s", ev); err == nil {
		t.Fatal("un Target sin URL validada debe fallar")
	}
	vacio := settings.Webhook{Format: settings.FormatNative}
	if _, _, err := WebhookRequest(context.Background(), receptor(t, cfg.URL), vacio, "s", ev); err == nil {
		t.Fatal("una configuración sin URL debe fallar")
	}
}

func TestWebhookRequestSinMarcaDeTiempoOmiteLaCabecera(t *testing.T) {
	ev := eventoAbierto()
	ev.At = time.Time{}
	cfg := settings.Webhook{URL: "https://receptor.example/hook", Enabled: true}
	req, _, err := WebhookRequest(context.Background(), receptor(t, cfg.URL), cfg, "", ev)
	if err != nil {
		t.Fatal(err)
	}
	if len(req.Header.Values(TimestampHeader)) != 0 {
		t.Fatal("sin marca de tiempo la cabecera no se inventa")
	}
}
