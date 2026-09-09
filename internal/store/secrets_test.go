package store

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func newStore(t *testing.T) *Store {
	t.Helper()
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func TestSecretEnvNameTraduceElNombre(t *testing.T) {
	if got := SecretEnvName("webhook_secret"); got != "LUCIDFENCE_WEBHOOK_SECRET" {
		t.Fatalf("SecretEnvName: %q", got)
	}
	if got := SecretEnvName("ntfy-token"); got != "LUCIDFENCE_NTFY_TOKEN" {
		t.Fatalf("SecretEnvName con guiones: %q", got)
	}
	if !strings.HasPrefix(SecretEnvName("x"), SecretEnvPrefix) {
		t.Fatal("el prefijo es LUCIDFENCE_")
	}
}

func TestSecretAusenteDevuelveErrNotFound(t *testing.T) {
	s := newStore(t)
	if _, err := s.Secret("default", "webhook_secret"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("esperaba ErrNotFound, got %v", err)
	}
}

func TestSaveSecretCreaFichero0600YDirectorio0700(t *testing.T) {
	s := newStore(t)
	if err := s.SaveSecret("default", "webhook_secret", "s3cr3to"); err != nil {
		t.Fatal(err)
	}
	got, err := s.Secret("default", "webhook_secret")
	if err != nil || got != "s3cr3to" {
		t.Fatalf("round-trip: %v %q", err, got)
	}
	dir := s.SecretsDir("default")
	if dir != filepath.Join(s.Root(), "secrets", "default") {
		t.Fatalf("SecretsDir: %q", dir)
	}
	if runtime.GOOS == "windows" {
		return
	}
	di, err := os.Stat(dir)
	if err != nil || di.Mode().Perm() != 0o700 {
		t.Fatalf("directorio de secretos: %v %o", err, di.Mode().Perm())
	}
	fi, err := os.Stat(filepath.Join(dir, "webhook_secret.json"))
	if err != nil || fi.Mode().Perm() != 0o600 {
		t.Fatalf("fichero de secreto: %v %o", err, fi.Mode().Perm())
	}
}

func TestSecretosDeDosOrganizacionesNoSeMezclan(t *testing.T) {
	s := newStore(t)
	if err := s.SaveSecret("default", "webhook_secret", "de-default"); err != nil {
		t.Fatal(err)
	}
	if err := s.SaveSecret("otra", "webhook_secret", "de-otra"); err != nil {
		t.Fatal(err)
	}
	if v, _ := s.Secret("default", "webhook_secret"); v != "de-default" {
		t.Fatalf("default: %q", v)
	}
	if v, _ := s.Secret("otra", "webhook_secret"); v != "de-otra" {
		t.Fatalf("otra: %q", v)
	}
}

func TestLaVariableDeEntornoGanaAlFichero(t *testing.T) {
	s := newStore(t)
	if err := s.SaveSecret("default", "webhook_secret", "el-del-fichero"); err != nil {
		t.Fatal(err)
	}
	t.Setenv("LUCIDFENCE_WEBHOOK_SECRET", "el-del-entorno")
	got, err := s.Secret("default", "webhook_secret")
	if err != nil || got != "el-del-entorno" {
		t.Fatalf("la variable debe ganar: %v %q", err, got)
	}
	t.Setenv("LUCIDFENCE_WEBHOOK_SECRET", "   ")
	if got, _ := s.Secret("default", "webhook_secret"); got != "el-del-fichero" {
		t.Fatalf("una variable en blanco no cuenta: %q", got)
	}
}

func TestDeleteSecretEsIdempotente(t *testing.T) {
	s := newStore(t)
	if err := s.DeleteSecret("default", "webhook_secret"); err != nil {
		t.Fatalf("borrar lo que no existe no falla: %v", err)
	}
	if err := s.SaveSecret("default", "webhook_secret", "x"); err != nil {
		t.Fatal(err)
	}
	if err := s.DeleteSecret("default", "webhook_secret"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Secret("default", "webhook_secret"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("tras borrar: %v", err)
	}
	if err := s.DeleteSecret("default", "webhook_secret"); err != nil {
		t.Fatalf("segundo borrado: %v", err)
	}
}

func TestSaveSecretRechazaValorVacio(t *testing.T) {
	s := newStore(t)
	if err := s.SaveSecret("default", "webhook_secret", ""); err == nil {
		t.Fatal("guardar un secreto vacío debería fallar: para eso está DeleteSecret")
	}
}

func TestNombresInvalidosNoEscapanDelDirectorio(t *testing.T) {
	s := newStore(t)
	for _, name := range []string{"", "../../auth/local-token", "Webhook", "a/b", ".hidden", strings.Repeat("x", 65)} {
		if err := s.SaveSecret("default", name, "x"); err == nil {
			t.Fatalf("SaveSecret(%q) debería fallar", name)
		}
		if _, err := s.Secret("default", name); err == nil || errors.Is(err, ErrNotFound) {
			t.Fatalf("Secret(%q) debe fallar por nombre inválido, no por ausencia: %v", name, err)
		}
		if err := s.DeleteSecret("default", name); err == nil {
			t.Fatalf("DeleteSecret(%q) debería fallar", name)
		}
	}
	for _, orgID := range []string{"", "Default", "../otra", "a b"} {
		if err := s.SaveSecret(orgID, "webhook_secret", "x"); err == nil {
			t.Fatalf("SaveSecret con org %q debería fallar", orgID)
		}
	}
	entries, _ := os.ReadDir(filepath.Join(s.Root(), "secrets"))
	if len(entries) != 0 {
		t.Fatalf("ningún nombre inválido puede haber creado nada: %v", entries)
	}
}

func TestUnSecretoJamasApareceEnLaSalidaDeSettings(t *testing.T) {
	s := newStore(t)
	const valor = "no-debe-salir-de-aqui"
	if err := s.SaveSecret("default", "webhook_secret", valor); err != nil {
		t.Fatal(err)
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	set, err := o.Settings()
	if err != nil {
		t.Fatal(err)
	}
	set.Webhook.URL = "https://siem.example.com/hec"
	set.Webhook.Enabled = true
	set.Webhook.SecretSet = true
	if err := o.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	back, err := o.Settings()
	if err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(back)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), valor) {
		t.Fatalf("el valor del secreto se ha colado en Settings: %s", data)
	}
	if !back.Webhook.SecretSet {
		t.Fatal("secret_set sí debe viajar: es solo un indicador de presencia")
	}
	raw, err := os.ReadFile(o.Path("settings.json"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), valor) {
		t.Fatalf("el valor del secreto se ha colado en settings.json: %s", raw)
	}
}
