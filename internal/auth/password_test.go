package auth

import (
	"strings"
	"testing"
)

func TestHashYVerify(t *testing.T) {
	h, err := HashPassword("correcto-caballo-bateria")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(h, "argon2id$v=19$m=65536,t=3,p=2$") {
		t.Fatalf("formato: %s", h)
	}
	if !VerifyPassword("correcto-caballo-bateria", h) || VerifyPassword("otra", h) || VerifyPassword("x", "basura") {
		t.Fatal("verify")
	}
	h2, _ := HashPassword("correcto-caballo-bateria")
	if h == h2 {
		t.Fatal("la sal debe ser aleatoria")
	}
	if _, err := HashPassword("corta"); err != ErrWeakPassword {
		t.Fatalf("esperaba ErrWeakPassword, got %v", err)
	}
}

// TestVerifyPasswordSinPanicoConParametrosInvalidos comprueba que un hash
// manipulado con parámetros fuera de rango (t=0, p=0, sal o hash vacíos tras
// decodificar) devuelve false en vez de propagar el pánico que
// argon2.IDKey lanza para t<1 o p<1. El recover() convierte cualquier
// pánico residual en un fallo explícito del test.
func TestVerifyPasswordSinPanicoConParametrosInvalidos(t *testing.T) {
	valid, err := HashPassword("correcto-caballo-bateria")
	if err != nil {
		t.Fatal(err)
	}
	parts := strings.Split(valid, "$")
	salt, hash := parts[3], parts[4]
	cases := map[string]string{
		"t=0":        "argon2id$v=19$m=65536,t=0,p=2$" + salt + "$" + hash,
		"p=0":        "argon2id$v=19$m=65536,t=3,p=0$" + salt + "$" + hash,
		"hash vacío": "argon2id$v=19$m=65536,t=3,p=2$" + salt + "$",
		"sal vacía":  "argon2id$v=19$m=65536,t=3,p=2$$" + hash,
	}
	for name, encoded := range cases {
		encoded := encoded
		t.Run(name, func(t *testing.T) {
			defer func() {
				if r := recover(); r != nil {
					t.Fatalf("pánico verificando %q: %v", name, r)
				}
			}()
			if VerifyPassword("cualquier-contraseña", encoded) {
				t.Fatalf("esperaba false para %q", name)
			}
		})
	}
}
