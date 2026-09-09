package notify

import (
	"net"
	"testing"
)

// addressTable es la tabla dorada de IsPrivate: 20 direcciones que el producto
// nunca debe alcanzar sin allow_private y 10 públicas legítimas que el filtro
// no puede romper (equivalente a _BLOCKED/_ALLOWED de
// legacy/tests/test_ssrf_ip_encoding_bypass.py, ampliado a IPv6).
var addressTable = []struct {
	ip      string
	private bool
	motivo  string
}{
	{"10.0.0.5", true, "RFC1918 /8"},
	{"172.16.0.1", true, "RFC1918 /12 inicio"},
	{"172.31.255.254", true, "RFC1918 /12 final"},
	{"192.168.1.1", true, "RFC1918 /16"},
	{"127.0.0.1", true, "loopback"},
	{"127.1.2.3", true, "loopback /8 completo"},
	{"169.254.169.254", true, "metadata de nube (link-local)"},
	{"0.0.0.0", true, "sin especificar"},
	{"255.255.255.255", true, "broadcast"},
	{"100.64.0.1", true, "CGNAT RFC6598"},
	{"224.0.0.1", true, "multicast IPv4"},
	{"198.18.0.1", true, "benchmarking RFC2544"},
	{"192.0.2.10", true, "TEST-NET-1"},
	{"::1", true, "loopback IPv6"},
	{"::", true, "sin especificar IPv6"},
	{"fc00::1", true, "ULA fc00::/7"},
	{"fd00::abcd", true, "ULA fd00::/8"},
	{"fe80::1", true, "link-local IPv6"},
	{"ff02::1", true, "multicast IPv6"},
	{"::ffff:10.0.0.5", true, "IPv4 privada mapeada en IPv6"},
	{"::10.0.0.5", true, "IPv4 privada en forma compatible ::a.b.c.d (RFC 4291)"},
	{"::127.0.0.1", true, "loopback en forma compatible"},
	{"::169.254.169.254", true, "metadata de nube en forma compatible"},
	{"2002:0a00:0005::1", true, "IPv4 privada en 6to4 (RFC 3056)"},
	{"2002:7f00:0001::1", true, "loopback en 6to4"},
	{"2002:a9fe:a9fe::1", true, "metadata de nube en 6to4"},
	{"8.8.8.8", false, "pública"},
	{"1.1.1.1", false, "pública"},
	{"93.184.216.34", false, "pública"},
	{"9.255.255.255", false, "justo antes de 10/8"},
	{"172.15.255.255", false, "justo antes de 172.16/12"},
	{"172.32.0.1", false, "justo después de 172.31/12"},
	{"100.128.0.1", false, "justo después de CGNAT"},
	{"198.20.0.1", false, "justo después de 198.18/15"},
	{"2001:4860:4860::8888", false, "pública IPv6"},
	{"2606:4700::1111", false, "pública IPv6"},
	{"2002:0808:0808::1", false, "6to4 de una IPv4 pública: se juzga lo empotrado, no el prefijo"},
}

func TestIsPrivateTablaDeDirecciones(t *testing.T) {
	for _, c := range addressTable {
		ip := net.ParseIP(c.ip)
		if ip == nil {
			t.Fatalf("dirección de la tabla ilegible: %q", c.ip)
		}
		if got := IsPrivate(ip); got != c.private {
			t.Errorf("IsPrivate(%s) = %v, quiero %v (%s)", c.ip, got, c.private, c.motivo)
		}
	}
}

func TestIsPrivateRechazaDireccionesInutilizables(t *testing.T) {
	// Sin dirección o con longitud imposible no se sale a ningún sitio: el
	// defecto seguro es "privada", nunca "pública".
	for _, ip := range []net.IP{nil, {}, {1, 2}, make(net.IP, 5)} {
		if !IsPrivate(ip) {
			t.Errorf("IsPrivate(%v) debe denegar una dirección inutilizable", []byte(ip))
		}
	}
}

func TestAlwaysBlockedSoloLinkLocalYMetadata(t *testing.T) {
	// Estas se deniegan aunque el operador active allow_private: por ahí no hay
	// destino legítimo, solo el pivote hacia las credenciales de instancia
	// (legacy: test_webhook_resolve_blocks_pivot_address).
	for _, s := range []string{"169.254.169.254", "169.254.0.1", "fe80::1", "fd00:ec2::254", "::ffff:169.254.169.254", "::169.254.169.254", "2002:a9fe:a9fe::1"} {
		if !alwaysBlocked(net.ParseIP(s)) {
			t.Errorf("alwaysBlocked(%s) = false; link-local y metadata no salen nunca", s)
		}
	}
	// Estas sí las abre allow_private: son el caso on-prem real.
	for _, s := range []string{"10.0.0.5", "127.0.0.1", "fc00::1", "192.168.1.1", "8.8.8.8", "::1", "::10.0.0.5", "2002:0808:0808::1"} {
		if alwaysBlocked(net.ParseIP(s)) {
			t.Errorf("alwaysBlocked(%s) = true; allow_private debe poder abrir este destino", s)
		}
	}
}

func TestParseIPAnyCanonicalizaCodificacionesNumericas(t *testing.T) {
	// Casos dorados de legacy/tests/test_ssrf_ip_encoding_bypass.py: formas que
	// getaddrinfo resuelve y net.ParseIP rechaza.
	casos := map[string]string{
		"127.0.0.1":          "127.0.0.1",
		"2130706433":         "127.0.0.1",
		"0x7f000001":         "127.0.0.1",
		"017700000001":       "127.0.0.1",
		"127.1":              "127.0.0.1",
		"0x7f.1":             "127.0.0.1",
		"127.0.1":            "127.0.0.1",
		"2852039166":         "169.254.169.254",
		"::ffff:127.0.0.1":   "127.0.0.1",
		"8.8.8.8":            "8.8.8.8",
		"2001:4860:4860::88": "2001:4860:4860::88",
	}
	for in, want := range casos {
		ip := parseIPAny(in)
		if ip == nil {
			t.Fatalf("parseIPAny(%q) = nil, esperaba %s", in, want)
		}
		if ip.String() != want {
			t.Errorf("parseIPAny(%q) = %s, quiero %s", in, ip, want)
		}
	}
}

func TestParseIPAnyNoConfundeHostnames(t *testing.T) {
	// Un hostname legítimo nunca puede convertirse en IP: rompería la allowlist
	// de los clientes (legacy: test_legit_external_https_hosts_still_allowed).
	for _, h := range []string{
		"api.applivery.io", "hooks.ejemplo.com", "cafe.ba", "0777.com",
		"1.2.3.4.5", "", "localhost", "12345.ejemplo.com", "0x.1", "08.1", "1..2",
	} {
		if ip := parseIPAny(h); ip != nil {
			t.Errorf("parseIPAny(%q) = %s; debe tratarse como hostname", h, ip)
		}
	}
}

func TestNormalizeHostCanonicaliza(t *testing.T) {
	casos := map[string]struct {
		host    string
		literal bool
	}{
		"Hooks.Ejemplo.COM.": {"hooks.ejemplo.com", false},
		" hooks.ejemplo.com": {"hooks.ejemplo.com", false},
		"0X7F000001":         {"127.0.0.1", true},
		"10.0.0.5":           {"10.0.0.5", true},
		"::ffff:127.0.0.1":   {"127.0.0.1", true},
	}
	for in, want := range casos {
		host, ip, err := normalizeHost(in)
		if err != nil {
			t.Fatalf("normalizeHost(%q): %v", in, err)
		}
		if host != want.host || (ip != nil) != want.literal {
			t.Errorf("normalizeHost(%q) = (%q, %v), quiero (%q, literal=%v)", in, host, ip, want.host, want.literal)
		}
	}
}

func TestNormalizeHostRechazaVacioYNoASCII(t *testing.T) {
	// Los corchetes de una URL IPv6 los quita url.Hostname antes de llegar aquí;
	// si aparecen es que el host viene de otro sitio y no es de fiar.
	for _, h := range []string{"", "   ", "...", "hooks.ejempló.com", "hooks.ejemplo.com%25eth0", "hooks.ejemplo.com/x", "[::1]"} {
		if _, _, err := normalizeHost(h); err == nil {
			t.Errorf("normalizeHost(%q) debía fallar (sin IDNA, solo ASCII)", h)
		}
	}
}
