package auth

import (
	"errors"
	"fmt"
	"testing"
	"time"
)

// Tests del limitador de intentos de login (internal/auth/throttle.go).

func TestThrottleTrasCincoFallos(t *testing.T) {
	s, _ := openStore(t)
	_, _ = s.Setup("a@x.com", "A", "contraseña-larga-1", "default")
	for i := 0; i < 5; i++ {
		if _, err := s.Login("a@x.com", "mal", "default"); !errors.Is(err, ErrInvalidCredentials) {
			t.Fatalf("intento %d: %v", i, err)
		}
	}
	if _, err := s.Login("a@x.com", "contraseña-larga-1", "default"); !errors.Is(err, ErrThrottled) {
		t.Fatalf("sexto intento bloqueado aunque sea correcto: %v", err)
	}
}

// TestFailsSePodaTrasLaVentana comprueba que, pasada failWindow, la entrada
// del email desaparece del mapa de fallos en vez de quedar con una lista
// vacía indefinidamente (fuga de memoria con un email distinto por
// atacante).
func TestFailsSePodaTrasLaVentana(t *testing.T) {
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	s, err := Open(t.TempDir(), func() time.Time { return now })
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Login("a@x.com", "mal", "default"); !errors.Is(err, ErrInvalidCredentials) {
		t.Fatalf("login mal: %v", err)
	}
	if len(s.fails["a@x.com"]) != 1 {
		t.Fatalf("esperaba un fallo registrado, got %v", s.fails["a@x.com"])
	}
	now = now.Add(failWindow + time.Second)
	if s.throttled("a@x.com") {
		t.Fatal("no debería seguir bloqueado tras la ventana")
	}
	if _, ok := s.fails["a@x.com"]; ok {
		t.Fatal("la clave debería haberse podado del mapa tras la ventana")
	}
}

// TestInundarElMapaNoReiniciaElThrottle deja a una víctima con maxFails
// intentos recientes y luego inunda el mapa de fallos con más de
// maxTrackedFailEmails emails inexistentes: la víctima debe seguir
// bloqueada. Vaciar el mapa entero al llegar al tope (implementación
// previa) convertía el límite de la spec §6.2 en algo que se salta a
// voluntad —5 intentos, inundación, 5 intentos, ...— y la inundación es
// barata porque un login de email inexistente ni siquiera deriva argon2
// (hallazgo C7).
func TestInundarElMapaNoReiniciaElThrottle(t *testing.T) {
	s, _ := openStore(t)
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < maxFails; i++ {
		if _, err := s.Login("a@x.com", "mal", "default"); !errors.Is(err, ErrInvalidCredentials) {
			t.Fatalf("intento %d: %v", i, err)
		}
	}
	for i := 0; i < maxTrackedFailEmails+10; i++ {
		s.registerFail(fmt.Sprintf("flood%d@x.com", i))
	}
	if len(s.fails) > maxTrackedFailEmails {
		t.Fatalf("mapa de fallos sin acotar: %d entradas", len(s.fails))
	}
	if _, err := s.Login("a@x.com", "contraseña-larga-1", "default"); !errors.Is(err, ErrThrottled) {
		t.Fatalf("la víctima debe seguir bloqueada tras la inundación: %v", err)
	}
}

// TestRegistrarFalloPodaMapaGrande comprueba que el mapa de fallos no crece
// sin límite: superado maxTrackedFailEmails se hace hueco expulsando
// entradas (comportamiento documentado en registerFail/makeRoomForFail) en
// vez de acumular una entrada por cada email distinto que un atacante pueda
// enviar.
func TestRegistrarFalloPodaMapaGrande(t *testing.T) {
	s, _ := openStore(t)
	for i := 0; i < maxTrackedFailEmails+1; i++ {
		s.registerFail(fmt.Sprintf("u%d@x.com", i))
	}
	if len(s.fails) > maxTrackedFailEmails {
		t.Fatalf("mapa de fallos sin podar: %d entradas", len(s.fails))
	}
}
