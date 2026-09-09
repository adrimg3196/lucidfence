package notify

import (
	"bytes"
	"context"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// fakeResolver cuenta las llamadas y devuelve una respuesta distinta por
// llamada: así se comprueba que Check resuelve UNA sola vez.
type fakeResolver struct {
	answers [][]string
	err     error
	calls   atomic.Int64
}

func (r *fakeResolver) resolve(_ context.Context, _ string) ([]net.IP, error) {
	n := int(r.calls.Add(1))
	if r.err != nil {
		return nil, r.err
	}
	idx := n - 1
	if idx >= len(r.answers) {
		idx = len(r.answers) - 1
	}
	if idx < 0 {
		return nil, nil
	}
	out := make([]net.IP, 0, len(r.answers[idx]))
	for _, s := range r.answers[idx] {
		out = append(out, net.ParseIP(s))
	}
	return out, nil
}

// egress construye la puerta con la allowlist dada. Con r == nil el resolver
// falla el test: sirve para probar que un caso concreto no consulta el DNS.
func egress(t *testing.T, hosts []string, allowPrivate bool, r *fakeResolver) *Egress {
	t.Helper()
	e := NewEgress(settings.Egress{Hosts: hosts, AllowPrivate: allowPrivate})
	if r != nil {
		e.Resolver = r.resolve
	} else {
		e.Resolver = func(context.Context, string) ([]net.IP, error) {
			t.Error("no se esperaba ninguna resolución DNS")
			return nil, errors.New("resolución inesperada")
		}
	}
	e.Logger = slog.New(slog.NewTextHandler(&bytes.Buffer{}, nil))
	return e
}

func TestNewEgressNormalizaLaAllowlist(t *testing.T) {
	e := NewEgress(settings.Egress{Hosts: []string{" .Slack.com ", "*", "", "0x7f000001", "hooks.Ejemplo.COM."}})
	want := []string{"slack.com", "127.0.0.1", "hooks.ejemplo.com"}
	if len(e.Hosts) != len(want) {
		t.Fatalf("Hosts = %v, quiero %v", e.Hosts, want)
	}
	for i, h := range want {
		if e.Hosts[i] != h {
			t.Errorf("Hosts[%d] = %q, quiero %q", i, e.Hosts[i], h)
		}
	}
	if e.AllowPrivate {
		t.Fatal("allow_private por defecto debe ser false")
	}
	if e.Resolver == nil || e.Logger == nil {
		t.Fatal("NewEgress deja Resolver y Logger utilizables")
	}
}

func TestAllowlistVaciaDeniegaTodoYNoResuelve(t *testing.T) {
	e := egress(t, nil, false, nil)
	if _, err := e.Check(context.Background(), "https://hooks.ejemplo.com/x"); !errors.Is(err, ErrHostNotAllowed) {
		t.Fatalf("allowlist vacía debe denegar con ErrHostNotAllowed, got %v", err)
	}
	if e.Allowed("hooks.ejemplo.com") {
		t.Fatal("allowlist vacía no permite ningún host")
	}
}

func TestSufijoConPuntoSiSinPuntoNo(t *testing.T) {
	e := egress(t, []string{"ejemplo.com", ".slack.com"}, false, nil)
	permitidos := []string{"ejemplo.com", "hooks.ejemplo.com", "a.b.ejemplo.com", "slack.com", "hooks.slack.com"}
	for _, h := range permitidos {
		if !e.Allowed(h) {
			t.Errorf("Allowed(%q) = false, quiero true", h)
		}
	}
	denegados := []string{"malejemplo.com", "ejemplo.com.evil.test", "ejemplo.comx", "evil.test", ""}
	for _, h := range denegados {
		if e.Allowed(h) {
			t.Errorf("Allowed(%q) = true, quiero false", h)
		}
	}
}

func TestAllowPrivateGobiernaElAccesoALoopback(t *testing.T) {
	con := egress(t, []string{"127.0.0.1"}, true, nil)
	target, err := con.Check(context.Background(), "https://127.0.0.1:8443/hook")
	if err != nil {
		t.Fatalf("allow_private=true debe permitir 127.0.0.1: %v", err)
	}
	if target.Host != "127.0.0.1" || target.Port != "8443" || len(target.IPs) != 1 {
		t.Fatalf("target = %+v", target)
	}
	if target.URL.Host != "127.0.0.1:8443" {
		t.Fatalf("URL.Host = %q", target.URL.Host)
	}
	sin := egress(t, []string{"127.0.0.1"}, false, nil)
	if _, err := sin.Check(context.Background(), "https://127.0.0.1:8443/hook"); !errors.Is(err, ErrPrivateAddress) {
		t.Fatalf("allow_private=false debe denegar con ErrPrivateAddress, got %v", err)
	}
}

// encodedBypass son los destinos internos escritos en codificaciones
// alternativas de legacy/tests/test_ssrf_ip_encoding_bypass.py. Están todos en
// la allowlist en su forma canónica: aun así deben rechazarse por privados, que
// es lo que demuestra que la canonicalización va antes que la comparación.
var encodedBypass = []string{
	"https://2130706433",
	"https://2130706433:443/x",
	"https://0x7f000001",
	"https://017700000001",
	"https://127.1",
	"https://0x7f.1",
	"https://[::ffff:127.0.0.1]",
	"https://2852039166",
	"https://169.254.169.254/latest/meta-data",
	"https://10.0.0.5",
}

func TestBypassPorCodificacionSeRechazanTodos(t *testing.T) {
	e := egress(t, []string{"127.0.0.1", "169.254.169.254", "10.0.0.5"}, false, nil)
	for _, raw := range encodedBypass {
		if _, err := e.Check(context.Background(), raw); !errors.Is(err, ErrPrivateAddress) {
			t.Errorf("bypass SSRF no bloqueado: %s -> %v", raw, err)
		}
	}
}

func TestMetadataDeNubeSeDeniegaAunConAllowPrivate(t *testing.T) {
	e := egress(t, []string{"169.254.169.254", "fd00:ec2::254", "127.0.0.1"}, true, nil)
	for _, raw := range []string{"https://169.254.169.254/latest/meta-data", "https://[fd00:ec2::254]/latest"} {
		if _, err := e.Check(context.Background(), raw); !errors.Is(err, ErrPrivateAddress) {
			t.Errorf("Check(%q) = %v; la metadata de nube se deniega siempre", raw, err)
		}
	}
	// La excepción es solo para el pivote: el loopback sigue saliendo.
	if _, err := e.Check(context.Background(), "https://127.0.0.1:8443/hook"); err != nil {
		t.Fatalf("allow_private debe seguir permitiendo el loopback: %v", err)
	}
}

func TestDestinosExternosLegitimosSiguenPermitidos(t *testing.T) {
	r := &fakeResolver{answers: [][]string{{"93.184.216.34"}}}
	e := egress(t, []string{"8.8.8.8", "api.applivery.io", "hooks.ejemplo.com"}, false, r)
	for _, raw := range []string{"https://8.8.8.8", "https://api.applivery.io/v1", "https://hooks.ejemplo.com/incident"} {
		if _, err := e.Check(context.Background(), raw); err != nil {
			t.Errorf("host externo legítimo roto por el filtro: %s -> %v", raw, err)
		}
	}
}

func TestVariasDireccionesUnaPrivadaDeniegaElDestino(t *testing.T) {
	r := &fakeResolver{answers: [][]string{{"93.184.216.34", "10.9.8.7"}}}
	e := egress(t, []string{"hooks.ejemplo.com"}, false, r)
	if _, err := e.Check(context.Background(), "https://hooks.ejemplo.com/x"); !errors.Is(err, ErrPrivateAddress) {
		t.Fatalf("una sola A privada deniega el destino entero, got %v", err)
	}
}

func TestAAAAConIPv4EmpotradaSeDeniega(t *testing.T) {
	// Un AAAA que empotra una IPv4 interna en forma compatible (::a.b.c.d) o
	// 6to4 (2002:<v4>::/16) es el mismo pivote que ::ffff:a.b.c.d escrito de
	// otra manera, y llega por la misma vía: el DNS de un host allowlisted.
	for _, aaaa := range []string{"::10.0.0.5", "::127.0.0.1", "2002:0a00:0005::1", "::169.254.169.254", "::ffff:0:10.0.0.5"} {
		r := &fakeResolver{answers: [][]string{{aaaa}}}
		e := egress(t, []string{"hooks.ejemplo.com"}, false, r)
		if _, err := e.Check(context.Background(), "https://hooks.ejemplo.com/x"); !errors.Is(err, ErrPrivateAddress) {
			t.Errorf("AAAA privado %s aceptado: %v", aaaa, err)
		}
	}
	// La metadata de nube se deniega también con allow_private, en cualquier
	// codificación: es la excepción que el brief fija como "siempre".
	for _, aaaa := range []string{"::169.254.169.254", "2002:a9fe:a9fe::1", "64:ff9b::169.254.169.254", "::ffff:0:169.254.169.254"} {
		r := &fakeResolver{answers: [][]string{{aaaa}}}
		e := egress(t, []string{"hooks.ejemplo.com"}, true, r)
		if _, err := e.Check(context.Background(), "https://hooks.ejemplo.com/x"); !errors.Is(err, ErrPrivateAddress) {
			t.Errorf("AAAA de metadata %s aceptado con allow_private: %v", aaaa, err)
		}
	}
}

func TestEsquemasNoPermitidos(t *testing.T) {
	e := egress(t, []string{"hooks.ejemplo.com"}, false, nil)
	for _, raw := range []string{"ftp://hooks.ejemplo.com/x", "file:///etc/passwd", "hooks.ejemplo.com/x", "", "://x"} {
		if _, err := e.Check(context.Background(), raw); !errors.Is(err, ErrSchemeNotAllowed) {
			t.Errorf("Check(%q) = %v, quiero ErrSchemeNotAllowed", raw, err)
		}
	}
	if _, err := e.Check(context.Background(), "https://"); !errors.Is(err, ErrHostNotAllowed) {
		t.Fatal("una URL sin host es un host fuera de la allowlist")
	}
}

func TestHTTPSoloHaciaDestinoPrivado(t *testing.T) {
	pub := &fakeResolver{answers: [][]string{{"93.184.216.34"}}}
	e := egress(t, []string{"hooks.ejemplo.com"}, true, pub)
	if _, err := e.Check(context.Background(), "http://hooks.ejemplo.com/x"); !errors.Is(err, ErrSchemeNotAllowed) {
		t.Fatalf("http hacia internet debe denegarse, got %v", err)
	}
	priv := &fakeResolver{answers: [][]string{{"10.9.8.7"}}}
	onprem := egress(t, []string{"siem.internal"}, true, priv)
	target, err := onprem.Check(context.Background(), "http://siem.internal:8088/services/collector")
	if err != nil {
		t.Fatalf("http hacia un SIEM privado con allow_private es legítimo: %v", err)
	}
	if target.Port != "8088" {
		t.Fatalf("Port = %q", target.Port)
	}
}

func TestResolucionFallidaOVacia(t *testing.T) {
	fallo := &fakeResolver{err: errors.New("NXDOMAIN")}
	e := egress(t, []string{"hooks.ejemplo.com"}, false, fallo)
	if _, err := e.Check(context.Background(), "https://hooks.ejemplo.com/x"); !errors.Is(err, ErrUnresolvable) {
		t.Fatalf("resolución fallida = ErrUnresolvable, got %v", err)
	}
	vacio := &fakeResolver{answers: [][]string{{}}}
	e2 := egress(t, []string{"hooks.ejemplo.com"}, false, vacio)
	if _, err := e2.Check(context.Background(), "https://hooks.ejemplo.com/x"); !errors.Is(err, ErrUnresolvable) {
		t.Fatalf("resolución vacía = ErrUnresolvable, got %v", err)
	}
}

func TestTOCTOUSeResuelveUnaVezYSeFijaLaIP(t *testing.T) {
	// El servidor escucha en 127.0.0.1; el resolver devuelve esa IP en la
	// validación y 169.254.169.254 (metadata) en cualquier llamada posterior,
	// que es exactamente el rebinding de legacy/tests/test_webhook_toctou_pinning.py.
	var hostRecibido atomic.Value
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hostRecibido.Store(r.Host)
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()
	u, err := url.Parse(srv.URL)
	if err != nil {
		t.Fatal(err)
	}
	r := &fakeResolver{answers: [][]string{{"127.0.0.1"}, {"169.254.169.254"}}}
	e := egress(t, []string{"hooks.ejemplo.test"}, true, r)

	target, err := e.Check(context.Background(), "http://hooks.ejemplo.test:"+u.Port()+"/hook")
	if err != nil {
		t.Fatal(err)
	}
	if len(target.IPs) != 1 || target.IPs[0].String() != "127.0.0.1" {
		t.Fatalf("IPs = %v, quiero la dirección validada", target.IPs)
	}
	resp, err := e.Client(target, 3*time.Second).Get(target.URL.String())
	if err != nil {
		t.Fatalf("la entrega debía llegar a la IP fijada: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("status = %d", resp.StatusCode)
	}
	if n := r.calls.Load(); n != 1 {
		t.Fatalf("el DNS se consultó %d veces; debe resolverse una sola vez", n)
	}
	if got := hostRecibido.Load(); got != "hooks.ejemplo.test:"+u.Port() {
		t.Fatalf("Host recibido = %v; el nombre original debe ir pinneado", got)
	}
}

func TestDenegarNoAbreNingunSocket(t *testing.T) {
	var golpes atomic.Int64
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		golpes.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	u, err := url.Parse(srv.URL)
	if err != nil {
		t.Fatal(err)
	}
	r := &fakeResolver{answers: [][]string{{"127.0.0.1"}}}
	e := egress(t, []string{"hooks.ejemplo.test"}, false, r)
	if _, err := e.Check(context.Background(), "http://hooks.ejemplo.test:"+u.Port()+"/hook"); !errors.Is(err, ErrPrivateAddress) {
		t.Fatalf("esperaba ErrPrivateAddress, got %v", err)
	}
	if n := golpes.Load(); n != 0 {
		t.Fatalf("un destino denegado abrió %d conexiones; debe ser 0", n)
	}

	// Un host fuera de la allowlist ni siquiera consulta el DNS.
	fuera := egress(t, []string{"otro.ejemplo.test"}, false, r)
	antes := r.calls.Load()
	if _, err := fuera.Check(context.Background(), "https://hooks.ejemplo.test/x"); !errors.Is(err, ErrHostNotAllowed) {
		t.Fatalf("esperaba ErrHostNotAllowed, got %v", err)
	}
	if r.calls.Load() != antes {
		t.Fatal("un host denegado no debe generar consulta DNS")
	}
	if n := golpes.Load(); n != 0 {
		t.Fatalf("un host denegado abrió %d conexiones; debe ser 0", n)
	}
}

func TestDenegacionSeRegistraSinLaRuta(t *testing.T) {
	var buf bytes.Buffer
	e := egress(t, []string{"otro.ejemplo.com"}, false, nil)
	e.Logger = slog.New(slog.NewTextHandler(&buf, &slog.HandlerOptions{Level: slog.LevelWarn}))
	if _, err := e.Check(context.Background(), "https://hooks.ejemplo.com/services/T00/B00/secretoAAA"); err == nil {
		t.Fatal("esperaba denegación")
	}
	log := buf.String()
	if !strings.Contains(log, "egress denegado") || !strings.Contains(log, "hooks.ejemplo.com") {
		t.Fatalf("la denegación debe registrarse con host y motivo: %q", log)
	}
	if strings.Contains(log, "secretoAAA") || strings.Contains(log, "/services/") {
		t.Fatalf("la ruta del webhook lleva el token y no puede aparecer en el log: %q", log)
	}
}
