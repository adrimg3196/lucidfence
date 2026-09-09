package notify

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// Canales de salida.
const (
	ChannelWebhook = "webhook"
	ChannelNtfy    = "ntfy"
)

// Clasificación del fallo de una entrega. Va en Delivery.ErrorType para que
// el panel y la batería distingan "no se intentó" de "se intentó y falló".
const (
	ErrorTypeEgress    = "egress"    // denegada por la allowlist: no se abrió socket
	ErrorTypeSecret    = "secret"    // el secreto configurado no se pudo resolver
	ErrorTypePayload   = "payload"   // no se pudo construir el cuerpo o la petición
	ErrorTypeTransport = "transport" // DNS, TCP, TLS o timeout
	ErrorTypeHTTP      = "http"      // respuesta recibida y no 2xx
)

// Nombres de los secretos en el proveedor (store.Secret los busca por este
// nombre, y LUCIDFENCE_WEBHOOK_SECRET / LUCIDFENCE_NTFY_TOKEN los pisan).
const (
	SecretWebhook = "webhook_secret"
	SecretNtfy    = "ntfy_token"
)

// DefaultBackoff son las pausas entre intentos. len(DefaultBackoff) es el
// número de intentos: tres. La última pausa no se llega a esperar nunca,
// porque tras el último intento no hay otro; está en la lista para que la
// regla "un elemento por intento" no tenga excepciones.
var DefaultBackoff = []time.Duration{time.Second, 2 * time.Second, 4 * time.Second}

// El tope por intento es DefaultTimeout, que ya declara notify.go (Task 9):
// es el mismo tope para toda salida del producto y redeclararlo aquí no
// compilaría.

// Delivery es una línea de deliveries.jsonl: el resultado de intentar
// entregar un evento por un canal. Los reintentos de una misma entrega
// comparten ID y producen una sola línea.
type Delivery struct {
	ID         string    `json:"id"`
	Event      string    `json:"event"`
	Channel    string    `json:"channel"`
	Target     string    `json:"target"`
	Format     string    `json:"format"`
	At         time.Time `json:"at"`
	Attempts   int       `json:"attempts"`
	OK         bool      `json:"ok"`
	HTTPStatus int       `json:"http_status,omitempty"`
	Error      string    `json:"error,omitempty"`
	ErrorType  string    `json:"error_type,omitempty"`
}

// Sink recibe cada entrega cerrada. *store.OrgStore lo satisface con
// AppendDelivery; la interfaz vive aquí para que notify no importe store.
type Sink interface {
	AppendDelivery(v any) error
}

// Secrets resuelve un secreto por nombre en el momento del envío. El
// Notifier nunca guarda el valor devuelto.
type Secrets interface {
	Secret(name string) (string, error)
}

// Options configura el Notifier. Todos los campos tienen valor por defecto;
// los tests los inyectan para tener reloj, ids y esperas deterministas.
type Options struct {
	Now     func() time.Time
	Backoff []time.Duration
	Timeout time.Duration
	Logger  *slog.Logger
	NewID   func() string
}

// Notifier entrega eventos a los canales configurados. Es seguro para uso
// concurrente: el ciclo del motor lo usa mientras la API lo recarga.
type Notifier struct {
	mu     sync.RWMutex
	set    settings.Settings
	egress *Egress
	status Status

	sec  Secrets
	sink Sink
	opts Options
}

// New construye el Notifier con la configuración inicial.
func New(set settings.Settings, sec Secrets, sink Sink, opts Options) *Notifier {
	if opts.Now == nil {
		opts.Now = time.Now
	}
	if len(opts.Backoff) == 0 {
		opts.Backoff = DefaultBackoff
	}
	if opts.Timeout <= 0 {
		opts.Timeout = DefaultTimeout
	}
	opts.Logger = defaultLogger(opts.Logger)
	if opts.NewID == nil {
		opts.NewID = nuevoIDAleatorio
	}
	n := &Notifier{sec: sec, sink: sink, opts: opts}
	n.aplicar(set)
	return n
}

// Reload cambia la configuración en caliente (PUT /settings/webhooks) sin
// tocar los contadores acumulados: son el histórico que publica health.
func (n *Notifier) Reload(set settings.Settings) { n.aplicar(set) }

func (n *Notifier) aplicar(set settings.Settings) {
	n.mu.Lock()
	defer n.mu.Unlock()
	n.set = set
	n.egress = NewEgress(set.Egress)
	// La denegación de egress se registra con el logger del Notifier, no con
	// el global: así el operador la ve en el mismo sitio que el resto de la
	// entrega y los tests la capturan en su buffer.
	n.egress.Logger = n.opts.Logger
	n.status.Webhook.Enabled = set.Webhook.Enabled
	n.status.Webhook.Target = destino(set.Webhook.URL)
	n.status.Ntfy.Enabled = set.Ntfy.Enabled
	n.status.Ntfy.Target = destino(set.Ntfy.URL)
}

// Notify entrega el evento por los canales suscritos y devuelve las entregas
// resultantes. Nunca devuelve error y nunca propaga pánico: un webhook mal
// configurado no puede tumbar el ciclo del motor (§6.4).
func (n *Notifier) Notify(ctx context.Context, ev Event) (out []Delivery) {
	defer n.recuperar(ev.Kind)
	if !catalogado(ev.Kind) {
		return nil
	}
	n.mu.RLock()
	set, eg := n.set, n.egress
	n.mu.RUnlock()
	if set.Webhook.Enabled && suscrito(set.Webhook.Events, ev.Kind) {
		out = append(out, n.entregar(ctx, eg, planWebhook(set), ev))
	}
	if set.Ntfy.Enabled {
		out = append(out, n.entregar(ctx, eg, planNtfy(set), ev))
	}
	return out
}

func (n *Notifier) recuperar(kind string) {
	if r := recover(); r != nil {
		n.opts.Logger.Error("pánico entregando notificación", "evento", kind, "recover", fmt.Sprint(r))
	}
}

// plan describe una entrega antes de tocar la red: a dónde va, con qué
// formato, qué secreto necesita y cómo se construye su petición.
type plan struct {
	canal     string
	rawURL    string
	formato   string
	secreto   string
	requiere  bool
	construir func(ctx context.Context, t Target, secreto string, ev Event) (*http.Request, error)
}

func planWebhook(set settings.Settings) plan {
	cfg := set.Webhook
	return plan{
		canal: ChannelWebhook, rawURL: cfg.URL, formato: cfg.Format,
		secreto: SecretWebhook, requiere: cfg.SecretSet,
		construir: func(ctx context.Context, t Target, secreto string, ev Event) (*http.Request, error) {
			req, _, err := WebhookRequest(ctx, t, cfg, secreto, ev)
			return req, err
		},
	}
}

func planNtfy(set settings.Settings) plan {
	cfg := set.Ntfy
	return plan{
		canal: ChannelNtfy, rawURL: cfg.URL, formato: "",
		secreto: SecretNtfy, requiere: cfg.TokenSet,
		construir: func(ctx context.Context, t Target, token string, ev Event) (*http.Request, error) {
			return NtfyRequest(ctx, t, cfg, token, ev)
		},
	}
}

// entregar ejecuta una entrega completa: egress, secreto, intentos y cierre.
// Siempre devuelve una Delivery, también cuando no se abre socket.
func (n *Notifier) entregar(ctx context.Context, eg *Egress, p plan, ev Event) Delivery {
	d := Delivery{
		ID: n.opts.NewID(), Event: ev.Kind, Channel: p.canal,
		Target: destino(p.rawURL), Format: p.formato, At: n.opts.Now().UTC(),
	}
	ev.DeliveryID = d.ID
	t, err := eg.Check(ctx, p.rawURL)
	if err != nil {
		return n.cerrar(fallo(d, ErrorTypeEgress, err.Error()))
	}
	secreto, err := n.resolver(p)
	if err != nil {
		return n.cerrar(fallo(d, ErrorTypeSecret, err.Error()))
	}
	nueva := func(c context.Context) (*http.Request, error) { return p.construir(c, t, secreto, ev) }
	n.intentar(ctx, eg.Client(t, n.opts.Timeout), nueva, d.Target, &d)
	return n.cerrar(d)
}

// resolver pide el secreto al proveedor en el momento del envío. Un canal
// sin secreto configurado entrega sin firma, como en 1.x.
func (n *Notifier) resolver(p plan) (string, error) {
	if !p.requiere {
		return "", nil
	}
	if n.sec == nil {
		return "", errors.New("no hay proveedor de secretos configurado")
	}
	v, err := n.sec.Secret(p.secreto)
	if err != nil {
		return "", fmt.Errorf("secreto %q: %w", p.secreto, err)
	}
	return v, nil
}

// intentar recorre los intentos. Reintenta solo ante error de transporte o
// 5xx; cualquier otra respuesta no 2xx es definitiva.
func (n *Notifier) intentar(ctx context.Context, cli *http.Client, nueva func(context.Context) (*http.Request, error), target string, d *Delivery) {
	for i := 0; i < len(n.opts.Backoff); i++ {
		if i > 0 && !n.esperar(ctx, n.opts.Backoff[i-1]) {
			return
		}
		d.Attempts = i + 1
		req, err := nueva(ctx)
		if err != nil {
			*d = fallo(*d, ErrorTypePayload, err.Error())
			return // reconstruir el mismo cuerpo daría el mismo error
		}
		resp, err := cli.Do(req)
		if err != nil {
			*d = fallo(*d, ErrorTypeTransport, transporte(err, target))
			d.HTTPStatus = 0
			continue
		}
		codigo := drenar(resp)
		d.HTTPStatus = codigo
		if codigo >= 200 && codigo < 300 {
			d.OK, d.Error, d.ErrorType = true, "", ""
			return
		}
		*d = fallo(*d, ErrorTypeHTTP, fmt.Sprintf("el receptor respondió %d", codigo))
		d.HTTPStatus = codigo
		if codigo < 500 {
			return
		}
	}
}

// esperar duerme el backoff y devuelve false si el contexto se cancela.
func (n *Notifier) esperar(ctx context.Context, d time.Duration) bool {
	if d <= 0 {
		return ctx.Err() == nil
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

// cerrar registra la entrega en el estado y en el Sink. Un Sink que falla se
// queda en el log: la red ya se ha usado y el resultado no cambia.
func (n *Notifier) cerrar(d Delivery) Delivery {
	n.registrar(d)
	if n.sink == nil {
		return d
	}
	if err := n.sink.AppendDelivery(d); err != nil {
		n.opts.Logger.Error("no se pudo registrar la entrega", "canal", d.Channel, "entrega", d.ID, "error", err)
	}
	return d
}

// fallo marca la entrega como fallida con su motivo.
func fallo(d Delivery, tipo, motivo string) Delivery {
	d.OK = false
	d.ErrorType = tipo
	d.Error = motivo
	return d
}

// drenar consume y cierra el cuerpo de la respuesta (hasta 4 KiB) para que
// la conexión se pueda reutilizar, y devuelve el código.
func drenar(resp *http.Response) int {
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4096))
	_ = resp.Body.Close()
	return resp.StatusCode
}

// transporte extrae el motivo real de un error de red. http.Client.Do
// devuelve *url.Error, cuyo Error() incluye la URL COMPLETA, query con
// credenciales incluida; guardarlo tal cual filtraría en deliveries.jsonl el
// secreto que destino() acaba de redactar.
func transporte(err error, target string) string {
	var ue *url.Error
	if errors.As(err, &ue) && ue.Err != nil {
		return fmt.Sprintf("%s %s: %s", ue.Op, target, ue.Err.Error())
	}
	return err.Error()
}

// destino devuelve la URL sin userinfo, query ni fragmento: es lo único que
// se escribe en deliveries.jsonl y se publica en health.
func destino(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil || u.Host == "" {
		return ""
	}
	u.User = nil
	u.RawQuery = ""
	u.ForceQuery = false
	u.Fragment = ""
	u.RawFragment = ""
	return u.String()
}

// catalogado dice si el tipo de evento está en el catálogo de la spec.
func catalogado(kind string) bool { return contieneCadena(settings.WebhookEvents, kind) }

// suscrito dice si el canal pidió este tipo de evento.
func suscrito(events []string, kind string) bool { return contieneCadena(events, kind) }

func contieneCadena(ss []string, s string) bool {
	for _, v := range ss {
		if v == s {
			return true
		}
	}
	return false
}

// nuevoIDAleatorio genera el id de entrega por defecto: 16 bytes de
// crypto/rand en hexadecimal. Si el lector del sistema falla (no ocurre en
// las plataformas soportadas), cae a un id derivado del reloj para que la
// entrega siga teniendo identidad y el receptor pueda deduplicar reintentos.
func nuevoIDAleatorio() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "del-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	}
	return "del-" + hex.EncodeToString(b[:])
}
