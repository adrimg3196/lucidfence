package auth

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"
)

func openStore(t *testing.T) (*Store, *time.Time) {
	t.Helper()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	s, err := Open(t.TempDir(), func() time.Time { return now })
	if err != nil {
		t.Fatal(err)
	}
	return s, &now
}

// TestSetupLoginResolveLogout delega cada tramo en una función privada
// (gocyclo mide cada func por separado, también las anidadas vía t.Run, así
// que solo funciones de nivel superior mantienen la complejidad de cada
// tramo por debajo del límite del proyecto, gocyclo ≤ 15) — el mismo motivo
// por el que internal/store/store_test.go divide sus round-trips en un test
// por tipo.
func TestSetupLoginResolveLogout(t *testing.T) {
	s, now := openStore(t)
	if s.HasUsers() {
		t.Fatal("vacío al abrir")
	}
	assertSetupCreaOwnerYRechazaRepetido(t, s)
	sess := assertLoginValidaCredencialesYReloj(t, s, now)
	assertResolveDevuelvePrincipalDeSesion(t, s, sess)
	assertLogoutInvalidaLaSesion(t, s, sess)
}

func assertSetupCreaOwnerYRechazaRepetido(t *testing.T, s *Store) {
	t.Helper()
	u, err := s.Setup("Adri@Example.com", "Adri", "contraseña-larga-1", "default")
	if err != nil || u.Email != "adri@example.com" || u.OrgRoles["default"] != Owner || u.ID == "" {
		t.Fatalf("setup: %v %+v", err, u)
	}
	if _, err := s.Setup("otro@example.com", "Otro", "contraseña-larga-1", "default"); !errors.Is(err, ErrAlreadySetUp) {
		t.Fatalf("segundo setup: %v", err)
	}
}

func assertLoginValidaCredencialesYReloj(t *testing.T, s *Store, now *time.Time) Session {
	t.Helper()
	if _, err := s.Login("adri@example.com", "mal", "default"); !errors.Is(err, ErrInvalidCredentials) {
		t.Fatalf("login mal: %v", err)
	}
	sess, err := s.Login("adri@example.com", "contraseña-larga-1", "default")
	if err != nil || sess.Token == "" || sess.CSRF == "" || sess.OrgID != "default" || !sess.ExpiresAt.After(sess.CreatedAt) {
		t.Fatalf("login: %v %+v", err, sess)
	}
	if !sess.CreatedAt.Equal(*now) {
		t.Fatalf("login debería usar el reloj inyectado: %v != %v", sess.CreatedAt, *now)
	}
	return sess
}

func assertResolveDevuelvePrincipalDeSesion(t *testing.T, s *Store, sess Session) {
	t.Helper()
	p, err := s.Resolve(sess.Token)
	if err != nil || p.Role != Owner || p.Email != "adri@example.com" || p.Via != "session" || p.CSRF != sess.CSRF {
		t.Fatalf("resolve: %v %+v", err, p)
	}
}

func assertLogoutInvalidaLaSesion(t *testing.T, s *Store, sess Session) {
	t.Helper()
	if err := s.Logout(sess.Token); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Resolve(sess.Token); !errors.Is(err, ErrUnauthenticated) {
		t.Fatalf("tras logout: %v", err)
	}
	if _, err := s.Resolve("token-inventado"); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("token inventado")
	}
}

// TestLoginNoBloqueaResolve prueba que la derivación de la clave (cara en
// CPU/memoria por diseño) se ejecuta fuera de s.mu: sustituye verifyPassword
// por una función que se bloquea en un canal y comprueba que Resolve sigue
// respondiendo mientras varios Login están atascados dentro de ella. Con el
// mutex tomado durante todo Login (implementación previa a este fix) este
// test agota el timeout porque Resolve no puede tomar el lock.
func TestLoginNoBloqueaResolve(t *testing.T) {
	s, _ := openStore(t)
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
		t.Fatal(err)
	}
	sess, err := s.Login("a@x.com", "contraseña-larga-1", "default")
	if err != nil {
		t.Fatal(err)
	}

	release := make(chan struct{})
	entered := make(chan struct{}, 4)
	s.verifyPassword = func(_, _ string) bool {
		entered <- struct{}{}
		<-release
		return false
	}

	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = s.Login("a@x.com", "mal", "default")
		}()
	}
	<-entered // al menos un Login está bloqueado dentro de verifyPassword

	done := make(chan struct{})
	go func() {
		for i := 0; i < 20; i++ {
			if _, err := s.Resolve(sess.Token); err != nil {
				t.Errorf("resolve %d: %v", i, err)
			}
		}
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("Resolve se bloqueó mientras verifyPassword estaba en curso")
	}

	close(release)
	wg.Wait()
}

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

// TestSetupNoMutaSiPersistenciaFalla comprueba que, si persistUsers falla
// (directorio de solo lectura), Setup no deja el usuario en memoria: debe
// persistir sobre una copia y solo asignarla a s.users si tiene éxito, así
// HasUsers() sigue siendo false y un reintento puede volver a crear el
// owner.
func TestSetupNoMutaSiPersistenciaFalla(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("los permisos POSIX de solo lectura no aplican en Windows")
	}
	if os.Geteuid() == 0 {
		t.Skip("root ignora los permisos de solo lectura del directorio")
	}
	dir := t.TempDir()
	s, err := Open(dir, time.Now)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o500); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = os.Chmod(dir, 0o700) }() // para que TempDir pueda limpiar
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err == nil {
		t.Fatal("esperaba un error de persistencia con el directorio en solo lectura")
	}
	if s.HasUsers() {
		t.Fatal("Setup no debe mutar el estado en memoria si persistUsers falla")
	}
}

// TestUserPublicoNoExponeElHash comprueba que el tipo público User (el que
// devuelven Setup y UserByID) no serializa el hash de la contraseña: solo
// userRecord, que es lo que se persiste en users.json, lo lleva.
func TestUserPublicoNoExponeElHash(t *testing.T) {
	u := User{ID: "usr_1", Email: "a@x.com", Name: "A", OrgRoles: map[string]Role{"default": Owner}, CreatedAt: time.Now()}
	data, err := json.Marshal(u)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), "password_hash") {
		t.Fatalf("User no debe serializar el hash de la contraseña: %s", data)
	}
}

// TestUsersJSONPersisteElHash comprueba que el fichero users.json sí lleva
// el hash (vía userRecord), aunque el tipo público User no lo exponga.
func TestUsersJSONPersisteElHash(t *testing.T) {
	dir := t.TempDir()
	s, err := Open(dir, time.Now)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(dir, "users.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(data), "password_hash") {
		t.Fatalf("users.json debería persistir el hash: %s", data)
	}
}

// TestLoginRechazaOrgAjena comprueba que un usuario con rol solo en una
// organización no puede iniciar sesión en otra: Login debe devolver
// ErrInvalidCredentials (no filtrar que las credenciales eran correctas
// para otra organización) y contar como fallo de throttle.
func TestLoginRechazaOrgAjena(t *testing.T) {
	s, _ := openStore(t)
	if _, err := s.Setup("a@x.com", "A", "contraseña-larga-1", "default"); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Login("a@x.com", "contraseña-larga-1", "otra"); !errors.Is(err, ErrInvalidCredentials) {
		t.Fatalf("login de organización ajena: %v", err)
	}
	if len(s.fails["a@x.com"]) != 1 {
		t.Fatalf("debería contar como fallo de throttle: %v", s.fails["a@x.com"])
	}
}

func TestSesionCaducaYPersiste(t *testing.T) {
	dir := t.TempDir()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	s, _ := Open(dir, func() time.Time { return now })
	_, _ = s.Setup("a@x.com", "A", "contraseña-larga-1", "default")
	sess, _ := s.Login("a@x.com", "contraseña-larga-1", "default")
	s2, err := Open(dir, func() time.Time { return now.Add(time.Hour) })
	if err != nil {
		t.Fatal(err)
	}
	if !s2.HasUsers() {
		t.Fatal("usuarios persistidos")
	}
	if _, err := s2.Resolve(sess.Token); err != nil {
		t.Fatalf("sesión persistida: %v", err)
	}
	s3, _ := Open(dir, func() time.Time { return now.Add(SessionTTL + time.Minute) })
	if _, err := s3.Resolve(sess.Token); !errors.Is(err, ErrUnauthenticated) {
		t.Fatalf("caducada: %v", err)
	}
	if u, ok := s3.UserByID(sess.UserID); !ok || u.Name != "A" {
		t.Fatal("UserByID")
	}
}

func TestTokenLocal(t *testing.T) {
	dir := t.TempDir()
	s, _ := openStoreIn(t, dir)
	tok := s.LocalToken()
	if len(tok) != 64 {
		t.Fatalf("token hex de 32 bytes: %q", tok)
	}
	info, err := os.Stat(filepath.Join(dir, "local-token"))
	if err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS != "windows" && info.Mode().Perm() != 0o600 {
		t.Fatalf("permisos %o", info.Mode().Perm())
	}
	p, err := s.ResolveLocal(tok, "default")
	if err != nil || p.Role != Admin || p.Via != "local-token" || p.OrgID != "default" {
		t.Fatalf("%v %+v", err, p)
	}
	if _, err := s.ResolveLocal("x", "default"); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("token incorrecto")
	}
	s2, _ := openStoreIn(t, dir)
	if s2.LocalToken() != tok {
		t.Fatal("el token local se reutiliza entre arranques")
	}
}

func openStoreIn(t *testing.T, dir string) (*Store, error) {
	t.Helper()
	return Open(dir, time.Now)
}
