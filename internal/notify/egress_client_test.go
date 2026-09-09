package notify

import (
	"context"
	"errors"
	"net"
	"net/http"
	"testing"
	"time"
)

// Los tests de Client viven aparte de los de Check: egress_test.go se acercaba
// al límite de 400 líneas de TestFileLimits y las Global Constraints del hito
// mandan dividir en dos ficheros del mismo paquete. El corte es el mismo que en
// el código: Check es la política, Client es el transporte.

func TestDialIgnoraLaDireccionQuePideElTransporte(t *testing.T) {
	// Prueba directa del pinning: se marca la IP validada aunque el transporte
	// pida la dirección a la que rebindió el atacante.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = ln.Close() }()
	go func() {
		if c, err := ln.Accept(); err == nil {
			_ = c.Close()
		}
	}()
	_, port, err := net.SplitHostPort(ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	target := Target{Host: "hooks.ejemplo.test", Port: port, IPs: []net.IP{net.ParseIP("127.0.0.1")}}
	tr, ok := (&Egress{}).Client(target, 2*time.Second).Transport.(*http.Transport)
	if !ok {
		t.Fatal("Client debe devolver un *http.Transport propio")
	}
	if tr.TLSClientConfig.ServerName != "hooks.ejemplo.test" {
		t.Fatalf("SNI = %q; debe pinnearse al nombre original", tr.TLSClientConfig.ServerName)
	}
	conn, err := tr.DialContext(context.Background(), "tcp", "169.254.169.254:443")
	if err != nil {
		t.Fatalf("el dial debía ir a la IP validada: %v", err)
	}
	defer func() { _ = conn.Close() }()
	if conn.RemoteAddr().String() != ln.Addr().String() {
		t.Fatalf("conectó a %s, quiero %s", conn.RemoteAddr(), ln.Addr())
	}
}

func TestDialRecorreLasDireccionesValidadas(t *testing.T) {
	// Dual-stack: la primera dirección validada no encamina y la segunda sí.
	// Fijar solo la primera dejaría el destino sin salida en los tres intentos
	// de T11, porque el Target y el cliente son los mismos en los tres, con
	// DisableKeepAlives y sin re-resolución. El Target se construye a mano, como
	// en TestDialIgnoraLaDireccionQuePideElTransporte: lo que se prueba es el
	// transporte, no la política.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = ln.Close() }()
	go func() {
		if c, err := ln.Accept(); err == nil {
			_ = c.Close()
		}
	}()
	_, port, err := net.SplitHostPort(ln.Addr().String())
	if err != nil {
		t.Fatal(err)
	}
	// 192.0.2.1 es TEST-NET-1 (RFC 5737): no encamina a ningún sitio, así que el
	// primer dial falla dentro del timeout y el segundo es el que entrega.
	target := Target{
		Host: "hooks.ejemplo.test",
		Port: port,
		IPs:  []net.IP{net.ParseIP("192.0.2.1"), net.ParseIP("127.0.0.1")},
	}
	tr, ok := (&Egress{}).Client(target, 500*time.Millisecond).Transport.(*http.Transport)
	if !ok {
		t.Fatal("Client debe devolver un *http.Transport propio")
	}
	conn, err := tr.DialContext(context.Background(), "tcp", "169.254.169.254:443")
	if err != nil {
		t.Fatalf("el dial debía caer a la segunda dirección validada: %v", err)
	}
	defer func() { _ = conn.Close() }()
	if conn.RemoteAddr().String() != ln.Addr().String() {
		t.Fatalf("conectó a %s, quiero %s", conn.RemoteAddr(), ln.Addr())
	}
}

func TestClientSinDireccionValidadaNoDial(t *testing.T) {
	e := egress(t, []string{"hooks.ejemplo.com"}, false, nil)
	_, err := e.Client(Target{Host: "hooks.ejemplo.com", Port: "443"}, 0).Get("https://hooks.ejemplo.com/x")
	if !errors.Is(err, ErrUnresolvable) {
		t.Fatalf("un Target sin IPs no puede abrir socket, got %v", err)
	}
}
