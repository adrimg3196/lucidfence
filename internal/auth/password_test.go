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
