package notify

import (
	"bytes"
	"errors"
	"fmt"
	"net"
	"strconv"
	"strings"
)

// reservedNets son rangos que nunca son un destino legítimo de un webhook y que
// no cubren los predicados de net.IP: "esta red", CGNAT, asignaciones de
// protocolo, redes de documentación y pruebas, el bloque reservado 240/4 (que
// incluye el broadcast 255.255.255.255), NAT64 y el prefijo de descarte.
var reservedNets = mustCIDRs(
	"0.0.0.0/8",       // "esta red" (RFC 1122)
	"100.64.0.0/10",   // CGNAT (RFC 6598)
	"192.0.0.0/24",    // asignaciones de protocolo IETF
	"192.0.2.0/24",    // TEST-NET-1
	"198.18.0.0/15",   // benchmarking (RFC 2544)
	"198.51.100.0/24", // TEST-NET-2
	"203.0.113.0/24",  // TEST-NET-3
	"240.0.0.0/4",     // reservado + broadcast
	"64:ff9b::/96",    // NAT64 (RFC 6052)
	"100::/64",        // descarte (RFC 6666)
	"2001:db8::/32",   // documentación
)

// blockedNets son los destinos que se deniegan SIEMPRE, también con
// allow_private activo: el link-local por el que se pivota y la metadata de
// nube que vive en él. 1.x hacía lo mismo: _webhook_resolve permitía RFC1918
// pero levantaba ValueError ante link-local
// (legacy/tests/test_webhook_toctou_pinning.py::test_webhook_resolve_blocks_pivot_address).
var blockedNets = mustCIDRs(
	"169.254.0.0/16", // link-local IPv4 y con ella 169.254.169.254
	"fe80::/10",      // link-local IPv6
	"fd00:ec2::/64",  // metadata IPv6 de instancia
)

func mustCIDRs(cidrs ...string) []*net.IPNet {
	out := make([]*net.IPNet, 0, len(cidrs))
	for _, c := range cidrs {
		_, n, err := net.ParseCIDR(c)
		if err != nil {
			panic("CIDR inválido en internal/notify: " + c)
		}
		out = append(out, n)
	}
	return out
}

func inAny(nets []*net.IPNet, ip net.IP) bool {
	for _, n := range nets {
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

// usable normaliza la dirección para juzgarla: descarta longitudes imposibles y
// convierte las IPv4 mapeadas en IPv6 a su forma de 4 bytes, para que
// ::ffff:10.0.0.5 se juzgue como 10.0.0.5.
func usable(ip net.IP) (net.IP, bool) {
	if len(ip) != net.IPv4len && len(ip) != net.IPv6len {
		return nil, false
	}
	if v4 := ip.To4(); v4 != nil {
		return v4, true
	}
	return ip, true
}

// wrappedV4Prefixes son los prefijos fijos de 96 bits que llevan una IPv4 en sus
// últimos 32 bits y que net.IP.To4 NO reconoce: la forma compatible ::a.b.c.d
// (RFC 4291), el prefijo bien conocido de NAT64 64:ff9b::/96 (RFC 6052) y la
// forma traducida ::ffff:0:a.b.c.d (RFC 2765). Los prefijos específicos de red
// del RFC 6052 (cualquier /32, /40, /48, /56 o /64 que el operador configure en
// su traductor) no se pueden reconocer sin conocer esa configuración y quedan
// fuera por construcción, igual que en cualquier otro filtro de egress.
var wrappedV4Prefixes = [][]byte{
	{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},             // ::a.b.c.d
	{0x00, 0x64, 0xff, 0x9b, 0, 0, 0, 0, 0, 0, 0, 0}, // 64:ff9b::/96
	{0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 0, 0},       // ::ffff:0:a.b.c.d
}

// embeddedV4 devuelve la IPv4 que una dirección IPv6 lleva dentro en las
// codificaciones que net.IP.To4 NO reconoce: 6to4 2002:<v4>::/16 (RFC 3056), que
// la lleva en los 32 bits siguientes al prefijo, y los tres prefijos de
// wrappedV4Prefixes, que la llevan al final. Sin esto, ::169.254.169.254,
// 2002:a9fe:a9fe::1 y 64:ff9b::169.254.169.254 son la misma metadata de
// instancia escrita de otra manera y no la deniega alwaysBlocked: el mismo
// bypass por codificación que parseIPAny cierra en IPv4, mudado a IPv6. Se juzga
// lo empotrado en vez de denegar los prefijos enteros porque el bloque dejaría
// ::1 fuera del alcance de allow_private (el SIEM on-prem) y denegaría un 6to4
// legítimo de una IPv4 pública. Devuelve nil cuando no hay IPv4 empotrada; :: y
// ::1 son direcciones por derecho propio, no un envoltorio.
func embeddedV4(ip net.IP) net.IP {
	if len(ip) != net.IPv6len || ip.To4() != nil || ip.IsUnspecified() || ip.IsLoopback() {
		return nil
	}
	if ip[0] == 0x20 && ip[1] == 0x02 { // 6to4: la IPv4 va en los 32 bits siguientes
		return net.IPv4(ip[2], ip[3], ip[4], ip[5]).To4()
	}
	for _, prefijo := range wrappedV4Prefixes {
		if bytes.Equal(ip[:12], prefijo) {
			return net.IPv4(ip[12], ip[13], ip[14], ip[15]).To4()
		}
	}
	return nil
}

// alwaysBlocked marca los destinos que no salen nunca, ni siquiera con
// allow_private: no hay ahí un servicio del operador, solo el pivote hacia las
// credenciales de instancia. Juzga también la IPv4 empotrada, para que
// ::169.254.169.254 y 2002:a9fe:a9fe::1 pesen lo mismo que 169.254.169.254.
func alwaysBlocked(ip net.IP) bool {
	norm, ok := usable(ip)
	if !ok {
		return true
	}
	if inAny(blockedNets, norm) {
		return true
	}
	if v4 := embeddedV4(norm); v4 != nil {
		return inAny(blockedNets, v4)
	}
	return false
}

// IsPrivate dice si la dirección pertenece a la red interna, al bucle local o a
// un rango reservado: destinos que una entrega saliente no debe alcanzar salvo
// que el operador active allow_private. Cubre RFC1918, loopback, link-local (y
// con ella la metadata de nube 169.254.169.254), ULA fc00::/7, la dirección sin
// especificar, multicast y las IPv4 empotradas en IPv6 en sus tres formas:
// mapeada (::ffff:a.b.c.d), compatible (::a.b.c.d) y 6to4 (2002:<v4>::/16). Una
// dirección ausente o de longitud imposible cuenta como privada: el defecto
// seguro es no salir.
func IsPrivate(ip net.IP) bool {
	norm, ok := usable(ip)
	if !ok {
		return true
	}
	if privateAddr(norm) {
		return true
	}
	if v4 := embeddedV4(norm); v4 != nil {
		return privateAddr(v4)
	}
	return false
}

// privateAddr juzga una dirección ya normalizada sin mirar lo que pueda llevar
// empotrado. Está separado de IsPrivate para poder aplicarlo dos veces: a la
// dirección y a la IPv4 que envuelve.
func privateAddr(ip net.IP) bool {
	if ip.IsUnspecified() || ip.IsLoopback() || ip.IsPrivate() ||
		ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() ||
		ip.IsInterfaceLocalMulticast() || ip.IsMulticast() {
		return true
	}
	return inAny(reservedNets, ip) || inAny(blockedNets, ip)
}

// errBadHost es el motivo interno; Check lo envuelve en ErrHostNotAllowed.
var errBadHost = errors.New("host no válido")

// normalizeHost deja el host en la forma canónica con la que se compara la
// allowlist: sin espacios, sin punto final, en minúsculas ASCII y, si es una
// dirección escrita en cualquier codificación numérica, en su forma canónica.
// Devuelve también la IP cuando el host es literal (entonces no hay DNS que
// consultar y por tanto no hay superficie de rebinding que cerrar).
func normalizeHost(raw string) (string, net.IP, error) {
	h := strings.TrimRight(strings.TrimSpace(raw), ".")
	if h == "" {
		return "", nil, fmt.Errorf("%w: vacío", errBadHost)
	}
	if err := asciiHost(h); err != nil {
		return "", nil, err
	}
	h = strings.ToLower(h)
	if ip := parseIPAny(h); ip != nil {
		return ip.String(), ip, nil
	}
	return h, nil, nil
}

// asciiHost rechaza lo que no sea un host ASCII. Sin IDNA en la stdlib
// (golang.org/x/net no está en internal/arch/allowlist_go.txt) un nombre con
// caracteres Unicode no se puede convertir a punycode y comparar de forma
// fiable contra la allowlist, y ahí es donde vive el ataque de homógrafos
// (ejemplo.com con una "e" cirílica). El operador escribe la forma xn--.
func asciiHost(h string) error {
	for i := 0; i < len(h); i++ {
		c := h[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9':
		case c == '.', c == '-', c == '_', c == ':':
		default:
			return fmt.Errorf("%w: byte %#x (usa la forma punycode xn--)", errBadHost, c)
		}
	}
	return nil
}

// parseIPAny acepta la forma canónica y, además, las codificaciones numéricas
// que inet_aton (y por tanto getaddrinfo) resuelve y net.ParseIP rechaza:
// decimal (2130706433), hexadecimal (0x7f000001), octal (017700000001) y las
// formas cortas (127.1, 0x7f.1). Sin esto un destino interno escrito en forma
// no canónica se colaría como "hostname externo": es el bypass SSRF que 1.x
// arregló el 2026-08-18 (legacy/tests/test_ssrf_ip_encoding_bypass.py).
func parseIPAny(host string) net.IP {
	if ip := net.ParseIP(host); ip != nil {
		return ip
	}
	return parseInetAton(host)
}

func parseInetAton(host string) net.IP {
	parts := strings.Split(host, ".")
	if len(parts) > 4 {
		return nil
	}
	values := make([]uint64, 0, 4)
	for _, p := range parts {
		v, ok := parseNumericPart(p)
		if !ok {
			return nil
		}
		values = append(values, v)
	}
	// Las partes iniciales valen un byte cada una; la última absorbe el resto,
	// que es lo que hace que 127.1 y 2130706433 sean 127.0.0.1.
	last := len(values) - 1
	var addr uint64
	for i, v := range values[:last] {
		if v > 0xff {
			return nil
		}
		addr |= v << (8 * (3 - uint(i)))
	}
	if values[last] > uint64(1)<<(8*(4-uint(last)))-1 {
		return nil
	}
	addr |= values[last]
	return net.IPv4(byte(addr>>24), byte(addr>>16), byte(addr>>8), byte(addr))
}

// parseNumericPart aplica la gramática de inet_aton: prefijo 0x hexadecimal,
// prefijo 0 octal, resto decimal. Una parte fuera de esa gramática significa
// que el host es un nombre, no una dirección.
func parseNumericPart(p string) (uint64, bool) {
	switch {
	case p == "":
		return 0, false
	case strings.HasPrefix(p, "0x"):
		v, err := strconv.ParseUint(strings.TrimPrefix(p, "0x"), 16, 64)
		return v, err == nil
	case len(p) > 1 && p[0] == '0':
		v, err := strconv.ParseUint(p[1:], 8, 64)
		return v, err == nil
	default:
		v, err := strconv.ParseUint(p, 10, 64)
		return v, err == nil
	}
}
