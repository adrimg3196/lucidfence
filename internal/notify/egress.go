package notify

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// Motivos tipados de denegación. T11 los traduce a Delivery.ErrorType y T21 a
// un mensaje del formulario de ajustes; ninguno lleva la URL completa.
var (
	ErrSchemeNotAllowed = errors.New("esquema no permitido")
	ErrHostNotAllowed   = errors.New("host fuera de la allowlist de egress")
	ErrPrivateAddress   = errors.New("destino en red privada")
	ErrUnresolvable     = errors.New("host no resuelve")
)

// Egress es la puerta de salida del producto. Resolver es inyectable para que
// los tests no dependan del DNS de la máquina; Logger recibe cada denegación.
type Egress struct {
	Hosts        []string
	AllowPrivate bool
	Resolver     func(ctx context.Context, host string) ([]net.IP, error)
	Logger       *slog.Logger
}

// NewEgress construye la puerta desde los ajustes de la organización. Las
// entradas se normalizan igual que los hosts que se comprueban: minúsculas, sin
// punto inicial (".slack.com" de 1.x == "slack.com") ni final, y las
// direcciones a su forma canónica. El comodín "*" se descarta: sería un
// allow-all que anula la allowlist entera (EgressAllowListPolicy.parse de 1.x).
func NewEgress(cfg settings.Egress) *Egress {
	hosts := make([]string, 0, len(cfg.Hosts))
	for _, raw := range cfg.Hosts {
		if e := normalizeEntry(raw); e != "" {
			hosts = append(hosts, e)
		}
	}
	return &Egress{Hosts: hosts, AllowPrivate: cfg.AllowPrivate, Resolver: lookupIP, Logger: slog.Default()}
}

func normalizeEntry(raw string) string {
	e := strings.ToLower(strings.TrimSpace(raw))
	e = strings.TrimRight(strings.TrimPrefix(e, "."), ".")
	if e == "" || strings.ContainsAny(e, "*/ \t") {
		return ""
	}
	if ip := parseIPAny(e); ip != nil {
		return ip.String()
	}
	return e
}

// Allowed indica si el host está en la allowlist. Coincidencia exacta o de
// sufijo con punto: "ejemplo.com" cubre "hooks.ejemplo.com" pero no
// "malejemplo.com" ni "ejemplo.com.evil.test". Una allowlist vacía deniega
// todo: en 2.0 no existe el modo permisivo de 1.x.
func (e *Egress) Allowed(host string) bool {
	h := normalizeEntry(host)
	if h == "" {
		return false
	}
	for _, raw := range e.Hosts {
		entry := normalizeEntry(raw)
		if entry == "" {
			continue
		}
		if h == entry || strings.HasSuffix(h, "."+entry) {
			return true
		}
	}
	return false
}

// Target es un destino ya validado: la URL con el host canónico, el host y el
// puerto por separado y TODAS las direcciones de la única resolución. Solo
// Check lo construye; Client no vuelve a mirar el DNS.
type Target struct {
	URL  *url.URL
	Host string
	Port string
	IPs  []net.IP
}

// Check es la única puerta de salida: ninguna petición del producto sale sin
// pasar por aquí. El orden importa: esquema, host, allowlist y solo entonces
// DNS, porque un host denegado no debe generar ni una consulta.
func (e *Egress) Check(ctx context.Context, rawURL string) (Target, error) {
	u, err := url.Parse(rawURL)
	if err != nil {
		return Target{}, e.deny("", fmt.Errorf("%w: url ilegible", ErrSchemeNotAllowed))
	}
	scheme := strings.ToLower(u.Scheme)
	if scheme != "https" && scheme != "http" {
		return Target{}, e.deny(u.Hostname(), fmt.Errorf("%w: %q", ErrSchemeNotAllowed, u.Scheme))
	}
	host, literal, err := normalizeHost(u.Hostname())
	if err != nil {
		return Target{}, e.deny(u.Hostname(), fmt.Errorf("%w: %v", ErrHostNotAllowed, err))
	}
	if !e.Allowed(host) {
		return Target{}, e.deny(host, fmt.Errorf("%w: %s", ErrHostNotAllowed, host))
	}
	ips, err := e.resolve(ctx, host, literal)
	if err != nil {
		return Target{}, e.deny(host, err)
	}
	if err := e.checkAddresses(host, ips, scheme); err != nil {
		return Target{}, e.deny(host, err)
	}
	port := u.Port()
	if port == "" {
		port = defaultPort(scheme)
	}
	out := *u
	out.Host = net.JoinHostPort(host, port)
	return Target{URL: &out, Host: host, Port: port, IPs: ips}, nil
}

// deny registra el motivo y devuelve el error tipado: una denegación nunca es
// silenciosa. Solo se registran host y motivo; la ruta de un webhook lleva el
// token del destino y no puede aparecer en los logs (spec §7).
func (e *Egress) deny(host string, err error) error {
	defaultLogger(e.Logger).Warn("egress denegado", "host", host, "motivo", err.Error())
	return err
}

// resolve consulta el DNS UNA SOLA VEZ. Las direcciones devueltas son las que
// Client fija en el dial: resolver otra vez en el connect es justo el TOCTOU de
// DNS rebinding de legacy/tests/test_webhook_toctou_pinning.py.
func (e *Egress) resolve(ctx context.Context, host string, literal net.IP) ([]net.IP, error) {
	if literal != nil {
		return []net.IP{literal}, nil // una IP literal no habla DNS
	}
	resolver := e.Resolver
	if resolver == nil {
		resolver = lookupIP
	}
	ips, err := resolver(ctx, host)
	if err != nil {
		return nil, fmt.Errorf("%w: %s: %v", ErrUnresolvable, host, err)
	}
	out := make([]net.IP, 0, len(ips))
	for _, ip := range ips {
		if len(ip) > 0 {
			out = append(out, ip)
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("%w: %s no devolvió direcciones", ErrUnresolvable, host)
	}
	return out, nil
}

// checkAddresses valida TODAS las direcciones: basta una privada para denegar el
// destino entero, porque un host con varias A no puede colar una interna. El
// link-local y la metadata de nube se deniegan aunque allow_private esté
// activo. El esquema http solo se acepta cuando el destino es privado entero y
// allow_private está activo (SIEM on-prem sin TLS); texto plano hacia internet
// no sale nunca.
func (e *Egress) checkAddresses(host string, ips []net.IP, scheme string) error {
	private := 0
	for _, ip := range ips {
		if alwaysBlocked(ip) {
			return fmt.Errorf("%w: %s resuelve a %s (link-local o metadata de instancia)", ErrPrivateAddress, host, ip)
		}
		if !IsPrivate(ip) {
			continue
		}
		private++
		if !e.AllowPrivate {
			return fmt.Errorf("%w: %s resuelve a %s", ErrPrivateAddress, host, ip)
		}
	}
	if scheme == "http" && private != len(ips) {
		return fmt.Errorf("%w: http solo hacia destinos privados con allow_private", ErrSchemeNotAllowed)
	}
	return nil
}

// Client devuelve el http.Client con el que se entrega a este destino y solo a
// este: DialContext ignora la dirección que pida el transporte y recorre, en
// orden, las direcciones que Check ya validó, mientras Host y SNI siguen siendo
// el nombre original, así que el certificado se valida contra el nombre y la
// conexión no puede desviarse aunque el DNS cambie entre Check y la entrega. La
// lista se congela aquí: Client no vuelve a mirar el DNS. Recorrerla en vez de
// fijar la primera no amplía en una dirección el conjunto alcanzable (todas
// salieron de checkAddresses) y evita que un destino dual-stack se quede sin
// salida cuando la primera no encamina: aquí no hay Happy Eyeballs ni
// re-resolución, y T11 reutiliza este mismo cliente en los tres intentos. El
// recorrido reparte el presupuesto entre los candidatos, porque timeout acota la
// petición entera y el primero se lo gastaría entero. Sin proxy (HTTP_PROXY
// saltaría el pinning) y sin seguir redirecciones (un 30x apuntaría fuera del
// destino validado).
func (e *Egress) Client(t Target, timeout time.Duration) *http.Client {
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	pinned := make([]string, 0, len(t.IPs))
	for _, ip := range t.IPs {
		pinned = append(pinned, net.JoinHostPort(ip.String(), t.Port))
	}
	tr := &http.Transport{
		Proxy: nil,
		DialContext: func(ctx context.Context, network, _ string) (net.Conn, error) {
			if len(pinned) == 0 {
				return nil, fmt.Errorf("%w: destino sin dirección validada", ErrUnresolvable)
			}
			// timeout acota la petición entera (es el Timeout del http.Client de
			// abajo), así que un candidato con TODO el presupuesto deja al
			// siguiente sin turno: cuando el primero no falla rápido sino que se
			// traga el tiempo —la ruta v6 agujereada que descarta en silencio, que
			// es justo el caso para el que existe el recorrido— la petición muere
			// antes del segundo intento. Cada candidato se lleva su parte de lo
			// que queda, y lo que uno no gasta (ECONNREFUSED, ENETUNREACH) vuelve
			// al reparto del siguiente. Con una sola dirección la parte es el
			// presupuesto entero, igual que antes.
			fin := time.Now().Add(timeout)
			err := fmt.Errorf("%w: sin presupuesto para abrir socket", ErrUnresolvable)
			for i, addr := range pinned {
				parte := time.Until(fin) / time.Duration(len(pinned)-i)
				if parte <= 0 {
					break // sin tiempo no se abre otro socket
				}
				d := net.Dialer{Timeout: parte}
				var conn net.Conn
				if conn, err = d.DialContext(ctx, network, addr); err == nil {
					return conn, nil
				}
				if ctx.Err() != nil {
					break // el contexto cancelado corta el recorrido, no lo agota
				}
			}
			return nil, err
		},
		TLSClientConfig:     &tls.Config{ServerName: t.Host, MinVersion: tls.VersionTLS12},
		TLSHandshakeTimeout: timeout,
		ForceAttemptHTTP2:   true,
		DisableKeepAlives:   true,
	}
	return &http.Client{
		Transport: tr,
		Timeout:   timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

func lookupIP(ctx context.Context, host string) ([]net.IP, error) {
	return net.DefaultResolver.LookupIP(ctx, "ip", host)
}

func defaultPort(scheme string) string {
	if scheme == "http" {
		return "80"
	}
	return "443"
}
