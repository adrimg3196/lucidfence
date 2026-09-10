package battery

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"sync"
	"time"
)

// Cabeceras y algoritmo de firma: deben coincidir exactamente con
// internal/notify (Tasks 10-11). internal/battery vive bajo la regla
// depguard "leaf-utils" (spec §5.2: solo $gostd), así que trata el binario
// como una caja negra por HTTP y nunca enlaza contra internal/notify ni
// ningún otro paquete de dominio; en vez de importar notify.Verify,
// reimplementa aquí, en stdlib puro, el mismo esquema HMAC-SHA256 y los
// mismos nombres de cabecera que Sign/Verify (T10), verificando así de
// forma independiente que el binario firma como promete.
const (
	signatureHeader = "X-LucidFence-Signature"
	eventHeader     = "X-LucidFence-Event"
	deliveryHeader  = "X-LucidFence-Delivery"
	timestampHeader = "X-LucidFence-Timestamp"
)

// verifySignature reproduce notify.Verify: "sha256=" + hex(hmac_sha256(secret, body)),
// comparado en tiempo constante.
func verifySignature(secret string, body []byte, header string) bool {
	const prefix = "sha256="
	if len(header) <= len(prefix) || header[:len(prefix)] != prefix {
		return false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write(body)
	want := prefix + hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(header), []byte(want))
}

// ReceivedDelivery es una entrega capturada por el Receiver.
type ReceivedDelivery struct {
	Event     string
	Signature string
	Body      []byte
	Valid     bool // firma correcta Y las cuatro cabeceras presentes
}

// Receiver es un servidor HTTP local que hace de destino de webhooks: por
// cada entrega, comprueba la firma y guarda lo recibido para que el check
// lo inspeccione.
type Receiver struct {
	URL    string
	Secret string

	mu       sync.Mutex
	Received []ReceivedDelivery
}

// StartReceiver arranca el receptor en 127.0.0.1 en un puerto libre.
// Devuelve el receptor y una función de parada idempotente-segura de llamar
// una vez (cierra el listener).
func StartReceiver(secret string) (*Receiver, func() error, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, nil, err
	}
	r := &Receiver{Secret: secret, URL: "http://" + ln.Addr().String()}
	srv := &http.Server{Handler: http.HandlerFunc(r.handle)}
	go func() { _ = srv.Serve(ln) }()
	return r, srv.Close, nil
}

func (r *Receiver) handle(w http.ResponseWriter, req *http.Request) {
	body, _ := io.ReadAll(req.Body)
	sig := req.Header.Get(signatureHeader)
	allHeaders := sig != "" && req.Header.Get(eventHeader) != "" &&
		req.Header.Get(deliveryHeader) != "" && req.Header.Get(timestampHeader) != ""
	d := ReceivedDelivery{
		Event:     req.Header.Get(eventHeader),
		Signature: sig,
		Body:      body,
		Valid:     allHeaders && verifySignature(r.Secret, body, sig),
	}
	r.mu.Lock()
	r.Received = append(r.Received, d)
	r.mu.Unlock()
	w.WriteHeader(http.StatusOK)
}

// Deliveries devuelve una copia de lo recibido hasta ahora: el servidor HTTP
// escribe desde su propia goroutine, así que el acceso va protegido.
func (r *Receiver) Deliveries() []ReceivedDelivery {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]ReceivedDelivery, len(r.Received))
	copy(out, r.Received)
	return out
}

// awaitDelivery sondea el receptor hasta encontrar una entrega válida del
// evento dado que además cumpla check (si no es nil), o hasta agotar el
// plazo. Si check devuelve false por un cuerpo con forma inesperada, sigue
// probando otras entregas: solo el llamador decide si eso es un fallo.
func awaitDelivery(rcv *Receiver, event string, timeout time.Duration, check func(map[string]any) bool) bool {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		for _, d := range rcv.Deliveries() {
			if d.Event != event || !d.Valid {
				continue
			}
			if check == nil {
				return true
			}
			var body map[string]any
			if json.Unmarshal(d.Body, &body) == nil && check(body) {
				return true
			}
		}
		time.Sleep(200 * time.Millisecond)
	}
	return false
}

func boolField(m map[string]any, key string) bool {
	b, _ := m[key].(bool)
	return b
}

func stringField(m map[string]any, key string) string {
	s, _ := m[key].(string)
	return s
}

func mapField(m map[string]any, key string) (map[string]any, bool) {
	v, ok := m[key].(map[string]any)
	return v, ok
}

// containsKeyDeep busca recursivamente una clave en cualquier nivel de un
// valor JSON ya decodificado (mapas y listas). La usa el check OCSF para
// probar en negativo que el payload no lleva coordenadas en ningún punto
// del árbol, no solo en la raíz.
func containsKeyDeep(v any, key string) bool {
	switch t := v.(type) {
	case map[string]any:
		if _, ok := t[key]; ok {
			return true
		}
		for _, sub := range t {
			if containsKeyDeep(sub, key) {
				return true
			}
		}
	case []any:
		for _, sub := range t {
			if containsKeyDeep(sub, key) {
				return true
			}
		}
	}
	return false
}
