package notify

import (
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

// alwaysBlocked marca los destinos que no salen nunca, ni siquiera con
// allow_private: no hay ahí un servicio del operador, solo el pivote hacia las
// credenciales de instancia.
func alwaysBlocked(ip net.IP) bool {
	norm, ok := usable(ip)
	if !ok {
		return true
	}
	return inAny(blockedNets, norm)
}

// IsPrivate dice si la dirección pertenece a la red interna, al bucle local o a
// un rango reservado: destinos que una entrega saliente no debe alcanzar salvo
// que el operador active allow_private. Cubre RFC1918, loopback, link-local (y
// con ella la metadata de nube 169.254.169.254), ULA fc00::/7, la dirección sin
// especificar, multicast y las IPv4 mapeadas en IPv6. Una dirección ausente o
// de longitud imposible cuenta como privada: el defecto seguro es no salir.
func IsPrivate(ip net.IP) bool {
	norm, ok := usable(ip)
	if !ok {
		return true
	}
	if norm.IsUnspecified() || norm.IsLoopback() || norm.IsPrivate() ||
		norm.IsLinkLocalUnicast() || norm.IsLinkLocalMulticast() ||
		norm.IsInterfaceLocalMulticast() || norm.IsMulticast() {
		return true
	}
	return inAny(reservedNets, norm) || inAny(blockedNets, norm)
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
