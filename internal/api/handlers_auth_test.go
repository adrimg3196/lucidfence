package api

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestSetupLoginMeLogout delega cada paso en una función con nombre propio
// para mantener la complejidad ciclomática de cada una bajo el umbral de
// gocyclo (15): un closure anidado en t.Run cuenta para la complejidad de la
// función que lo contiene, así que la única forma de separar la métrica es
// una función de nivel superior por paso. El estado (e.cookie/e.csrf) es
// compartido entre pasos y se ejecutan en el mismo orden que el caso
// original de una sola función.
func TestSetupLoginMeLogout(t *testing.T) {
	e := newTestEnv(t)
	t.Run("status antes de setup", func(t *testing.T) { checkStatusAntesDeSetup(t, e) })
	t.Run("setup crea el owner y siembra demo", func(t *testing.T) { checkSetupCreaOwnerYSiembraDemo(t, e) })
	t.Run("segundo setup es conflicto", func(t *testing.T) { checkSegundoSetupEsConflicto(t, e) })
	t.Run("me con sesión", func(t *testing.T) { checkMeConSesion(t, e) })
	t.Run("login incorrecto y correcto", func(t *testing.T) { checkLoginIncorrectoYCorrecto(t, e) })
	t.Run("logout invalida la cookie", func(t *testing.T) { checkLogoutInvalidaCookie(t, e) })
}

func checkStatusAntesDeSetup(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/auth/status", nil, false)
	if res.StatusCode != 200 || out["setup_required"] != true {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
}

func checkSetupCreaOwnerYSiembraDemo(t *testing.T, e *testEnv) {
	t.Helper()
	out := e.setup("demo")
	user := out["user"].(map[string]any)
	if user["role"] != "owner" || user["email"] != "adri@example.com" || user["org"] != "default" {
		t.Fatalf("user: %v", user)
	}
	if _, has := user["password_hash"]; has {
		t.Fatal("nunca se devuelve el hash")
	}
	fs, _ := e.org.Fences()
	if len(fs) != 2 {
		t.Fatal("modo demo siembra geocercas")
	}
}

func checkSegundoSetupEsConflicto(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "x@x.com", "name": "X", "password": "contraseña-larga-1", "mode": "empty"}, false)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("segundo setup: %d %v", res.StatusCode, out)
	}
}

func checkMeConSesion(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("GET", "/api/v1/auth/me", nil, true)
	if res.StatusCode != 200 || out["user"].(map[string]any)["via"] != "session" || len(out["capabilities"].([]any)) == 0 {
		t.Fatalf("me: %d %v", res.StatusCode, out)
	}
}

func checkLoginIncorrectoYCorrecto(t *testing.T, e *testEnv) {
	t.Helper()
	res, out := e.do("POST", "/api/v1/auth/login", map[string]any{"email": "adri@example.com", "password": "mal"}, false)
	if res.StatusCode != 401 || out["code"] != "invalid_credentials" {
		t.Fatalf("login mal: %d %v", res.StatusCode, out)
	}
	res, _ = e.do("POST", "/api/v1/auth/login", map[string]any{"email": "adri@example.com", "password": "contraseña-larga-1"}, false)
	if res.StatusCode != 200 {
		t.Fatalf("login: %d", res.StatusCode)
	}
}

func checkLogoutInvalidaCookie(t *testing.T, e *testEnv) {
	t.Helper()
	res, _ := e.do("POST", "/api/v1/auth/logout", nil, true)
	if res.StatusCode != 204 {
		t.Fatalf("logout: %d", res.StatusCode)
	}
	res, _ = e.do("GET", "/api/v1/auth/me", nil, true)
	if res.StatusCode != 401 {
		t.Fatal("tras logout la cookie no vale")
	}
}

// TestSetupNoFiltraErrorDeSiembra convierte fences.json en un directorio
// antes del setup en modo demo: engine.SeedDemo falla al leer/escribir esa
// colección y el 500 resultante debe llevar "error interno" en el cuerpo,
// nunca el mensaje de os.ReadFile/os.Rename (que incluye la ruta absoluta
// del fichero en la organización). Ronda de corrección M1-R17 (fugas
// residuales).
func TestSetupNoFiltraErrorDeSiembra(t *testing.T) {
	e := newTestEnv(t)
	if err := os.Mkdir(e.org.Path("fences.json"), 0o755); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "adri@example.com", "name": "Adri", "password": "contraseña-larga-1", "mode": "demo"}, false)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("500 error interno esperado: %d %v", res.StatusCode, out)
	}
	if strings.Contains(fmt.Sprintf("%v", out), e.org.Dir()) {
		t.Fatalf("el cuerpo filtra la ruta del store: %v", out)
	}
}

// TestSetupNoFiltraErrorDeUsuarios convierte users.json en un directorio: el
// fallo de auth.Setup deja de ser de validación y pasa a ser de
// persistencia, así que debe salir como 500 "error interno" y nunca como un
// 400 con el mensaje de os.Rename, que lleva la ruta absoluta del
// directorio de datos. Simétrico de TestSetupNoFiltraErrorDeSiembra por la
// otra vía de fallo del asistente (M1-R17, hallazgo C6): /auth/setup es
// público, así que la fuga la ve cualquiera que alcance el puerto antes de
// que exista un usuario.
func TestSetupNoFiltraErrorDeUsuarios(t *testing.T) {
	e := newTestEnv(t)
	if err := os.Mkdir(filepath.Join(e.authDir, "users.json"), 0o755); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "adri@example.com", "name": "Adri", "password": "contraseña-larga-1", "mode": "empty"}, false)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("500 error interno esperado: %d %v", res.StatusCode, out)
	}
	if strings.Contains(fmt.Sprintf("%v", out), e.authDir) {
		t.Fatalf("el cuerpo filtra la ruta del store: %v", out)
	}
}

// TestLoginConPersistenciaRotaEs500 rompe sessions.json (directorio en vez
// de fichero) y hace login con las credenciales correctas: el fallo de
// escritura debe salir como 500 "error interno", no como 401 "email o
// contraseña incorrectos", que daba al usuario y al operador un
// diagnóstico falso ante un problema de disco o de permisos (hallazgo C8).
func TestLoginConPersistenciaRotaEs500(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	sessions := filepath.Join(e.authDir, "sessions.json")
	if err := os.Remove(sessions); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(sessions, 0o755); err != nil {
		t.Fatal(err)
	}
	res, out := e.do("POST", "/api/v1/auth/login", map[string]any{"email": "adri@example.com", "password": "contraseña-larga-1"}, false)
	if res.StatusCode != 500 || out["code"] != "internal" || out["error"] != "error interno" {
		t.Fatalf("500 error interno esperado: %d %v", res.StatusCode, out)
	}
	if strings.Contains(fmt.Sprintf("%v", out), e.authDir) {
		t.Fatalf("el cuerpo filtra la ruta del store: %v", out)
	}
}

func TestSetupValidaYCSRF(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "sin-arroba", "name": "", "password": "corta", "mode": "demo"}, false)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	e.setup("empty")
	req, _ := newRequest(e, "POST", "/api/v1/auth/logout")
	req.AddCookie(e.cookie)
	if res, out := send(e, req); res.StatusCode != 403 || out["code"] != "csrf" {
		t.Fatalf("mutación con cookie sin cabecera CSRF: %d %v", res.StatusCode, out)
	}
}
