package auth

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/store"
)

// Errores de autenticación.
var (
	ErrAlreadySetUp       = errors.New("la instalación ya tiene usuarios")
	ErrInvalidCredentials = errors.New("credenciales incorrectas")
	ErrInvalidUser        = errors.New("email y nombre obligatorios")
	ErrPersistence        = errors.New("no se pudo guardar el estado de sesión")
	ErrThrottled          = errors.New("demasiados intentos; espera un minuto")
	ErrUnauthenticated    = errors.New("no autenticado")
)

// SessionTTL es la vida de una sesión.
const SessionTTL = 12 * time.Hour

const (
	maxFails   = 5
	failWindow = time.Minute
	// maxTrackedFailEmails acota la memoria que puede consumir el mapa de
	// fallos: sin límite, un atacante que pruebe un email distinto por
	// intento haría crecer s.fails sin fin.
	maxTrackedFailEmails = 10000
	// maxConcurrentKDF acota cuántas derivaciones argon2id (el
	// verifyPassword de Login, el HashPassword de Setup) pueden estar en
	// curso a la vez: cada una reserva argonMemory (64 MiB), así que el
	// límite de 4 mantiene el consumo del KDF en 4 × 64 MiB = 256 MiB como
	// máximo, sin importar cuántos Login/Setup lleguen de golpe.
	maxConcurrentKDF = 4
)

// User es un usuario local tal como se expone hacia la API. Nunca lleva el
// hash de la contraseña: ese dato solo existe en userRecord, el tipo
// interno que se persiste en users.json.
type User struct {
	ID        string          `json:"id"`
	Email     string          `json:"email"`
	Name      string          `json:"name"`
	OrgRoles  map[string]Role `json:"org_roles"`
	CreatedAt time.Time       `json:"created_at"`
}

// userRecord es la forma persistida en users.json: el usuario público más
// el hash de la contraseña. No sale nunca de este paquete.
type userRecord struct {
	User
	PasswordHash string `json:"password_hash"`
}

// Session es una sesión de cookie.
type Session struct {
	Token     string    `json:"token"`
	UserID    string    `json:"user_id"`
	OrgID     string    `json:"org_id"`
	CSRF      string    `json:"csrf"`
	CreatedAt time.Time `json:"created_at"`
	ExpiresAt time.Time `json:"expires_at"`
}

// Principal es la identidad resuelta de una petición.
type Principal struct {
	UserID string `json:"user_id"`
	Email  string `json:"email"`
	Name   string `json:"name"`
	OrgID  string `json:"org_id"`
	Role   Role   `json:"role"`
	Via    string `json:"via"`
	CSRF   string `json:"-"`
}

type collection[T any] struct {
	SchemaVersion int `json:"schema_version"`
	Items         []T `json:"items"`
}

// Store persiste usuarios y sesiones en <data>/auth.
type Store struct {
	dir        string
	now        func() time.Time
	mu         sync.Mutex
	users      []userRecord
	sessions   map[string]Session
	localToken string
	fails      map[string][]time.Time
	// kdf es el semáforo de las derivaciones argon2id: un canal con buffer
	// de maxConcurrentKDF huecos. acquireKDF/releaseKDF son los únicos que
	// lo tocan; nada más lee ni escribe s.kdf.
	kdf chan struct{}
	// verifyPassword deriva y compara la contraseña; por defecto es
	// VerifyPassword. Es inyectable (campo no exportado) para que los tests
	// puedan bloquearla de forma controlada y comprobar que Login nunca la
	// llama con s.mu tomado (ver TestLoginNoBloqueaResolve).
	verifyPassword func(pw, hash string) bool
}

// acquireKDF bloquea hasta que haya hueco para una derivación argon2id más
// (como máximo maxConcurrentKDF a la vez); releaseKDF libera el hueco.
// Envuelven las dos únicas derivaciones del paquete: el verifyPassword de
// Login y el HashPassword de Setup.
func (s *Store) acquireKDF() { s.kdf <- struct{}{} }
func (s *Store) releaseKDF() { <-s.kdf }

// Open carga usuarios y sesiones y garantiza el token local.
func Open(dir string, now func() time.Time) (*Store, error) {
	if now == nil {
		now = time.Now
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	s := &Store{dir: dir, now: now, sessions: map[string]Session{}, fails: map[string][]time.Time{}, kdf: make(chan struct{}, maxConcurrentKDF), verifyPassword: VerifyPassword}
	var users collection[userRecord]
	if err := store.ReadJSON(filepath.Join(dir, "users.json"), &users); err != nil && !errors.Is(err, store.ErrNotFound) {
		return nil, err
	}
	s.users = users.Items
	var sessions collection[Session]
	if err := store.ReadJSON(filepath.Join(dir, "sessions.json"), &sessions); err != nil && !errors.Is(err, store.ErrNotFound) {
		return nil, err
	}
	for _, sess := range sessions.Items {
		if sess.ExpiresAt.After(now()) {
			s.sessions[sess.Token] = sess
		}
	}
	tok, err := ensureLocalToken(filepath.Join(dir, "local-token"))
	if err != nil {
		return nil, err
	}
	s.localToken = tok
	return s, nil
}

func ensureLocalToken(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err == nil && len(strings.TrimSpace(string(data))) == 64 {
		return strings.TrimSpace(string(data)), nil
	}
	tok := randomHex(32)
	if err := os.WriteFile(path, []byte(tok+"\n"), 0o600); err != nil {
		return "", err
	}
	return tok, nil
}

func randomHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic("sin entropía: " + err.Error())
	}
	return hex.EncodeToString(b)
}

func normalizeEmail(e string) string { return strings.ToLower(strings.TrimSpace(e)) }

func (s *Store) persistUsers(records []userRecord) error {
	return store.WriteJSON(filepath.Join(s.dir, "users.json"), collection[userRecord]{SchemaVersion: 1, Items: records})
}

func (s *Store) persistSessions() error {
	items := make([]Session, 0, len(s.sessions))
	for _, sess := range s.sessions {
		items = append(items, sess)
	}
	return store.WriteJSON(filepath.Join(s.dir, "sessions.json"), collection[Session]{SchemaVersion: 1, Items: items})
}

// HasUsers indica si la instalación ya tiene un owner.
func (s *Store) HasUsers() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.users) > 0
}

// Setup crea el primer usuario como owner de la organización. El hash de la
// contraseña (derivación argon2id, cara en CPU/memoria por diseño) se
// calcula fuera de s.mu, igual que el verifyPassword de Login: se prepara y
// valida bajo el lock, se deriva fuera (acotado por acquireKDF/releaseKDF)
// y se vuelve a bloquear para insertar y persistir.
func (s *Store) Setup(email, name, password, orgID string) (User, error) {
	s.mu.Lock()
	if len(s.users) > 0 {
		s.mu.Unlock()
		return User{}, ErrAlreadySetUp
	}
	email = normalizeEmail(email)
	if email == "" || !strings.Contains(email, "@") || strings.TrimSpace(name) == "" {
		s.mu.Unlock()
		return User{}, ErrInvalidUser
	}
	s.mu.Unlock()

	s.acquireKDF()
	hash, err := HashPassword(password)
	s.releaseKDF()
	if err != nil {
		return User{}, err
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	// Repetir la comprobación: entre soltar el lock para derivar y volver a
	// tomarlo, otro Setup pudo haber ganado la carrera y creado ya el owner.
	if len(s.users) > 0 {
		return User{}, ErrAlreadySetUp
	}
	rec := userRecord{
		User: User{ID: "usr_" + randomHex(8), Email: email, Name: strings.TrimSpace(name),
			OrgRoles: map[string]Role{orgID: Owner}, CreatedAt: s.now().UTC()},
		PasswordHash: hash,
	}
	// Persistir sobre una copia y asignar a s.users solo si tiene éxito: un
	// error de escritura (disco lleno, permisos) no debe dejar el owner
	// "creado" en memoria sin estar en disco.
	candidate := append(append([]userRecord{}, s.users...), rec)
	if err := s.persistUsers(candidate); err != nil {
		return User{}, err
	}
	s.users = candidate
	return rec.User, nil
}

// throttled poda del email los intentos fuera de failWindow y decide si
// sigue bloqueado. Si no quedan intentos recientes, la clave se borra del
// mapa en vez de dejar una entrada vacía indefinidamente.
func (s *Store) throttled(email string) bool {
	cutoff := s.now().Add(-failWindow)
	var recent []time.Time
	for _, t := range s.fails[email] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	if len(recent) == 0 {
		delete(s.fails, email)
	} else {
		s.fails[email] = recent
	}
	return len(recent) >= maxFails
}

// registerFail anota un intento fallido. El mapa sigue acotado a
// maxTrackedFailEmails claves (una avalancha de emails distintos no puede
// hacerlo crecer sin fin), pero hacer hueco nunca reinicia el contador de
// un email ya bloqueado: vaciar el mapa entero al llegar al tope permitía
// saltarse el límite de la spec §6.2 a voluntad, porque inundar con emails
// inexistentes es barato (ese camino ni siquiera deriva argon2). Un email
// ya seguido siempre se anota; uno nuevo, solo si makeRoomForFail
// encuentra sitio.
func (s *Store) registerFail(email string) {
	if _, tracked := s.fails[email]; !tracked && !s.makeRoomForFail() {
		return
	}
	s.fails[email] = append(s.fails[email], s.now())
}

// makeRoomForFail deja hueco para una clave nueva en el mapa de fallos:
// primero borra las entradas caducadas (su último intento cae fuera de
// failWindow, así que ya no cuentan para throttled) y, si el mapa sigue
// lleno, expulsa la más antigua de entre las que todavía no bloquean
// (menos de maxFails intentos). Devuelve false si todas las entradas están
// bloqueando: antes que soltar a una víctima, se prefiere no seguir la
// clave nueva.
func (s *Store) makeRoomForFail() bool {
	if len(s.fails) < maxTrackedFailEmails {
		return true
	}
	cutoff := s.now().Add(-failWindow)
	for email, ts := range s.fails {
		if len(ts) == 0 || !ts[len(ts)-1].After(cutoff) {
			delete(s.fails, email)
		}
	}
	for len(s.fails) >= maxTrackedFailEmails {
		oldest, at, found := "", time.Time{}, false
		for email, ts := range s.fails {
			if len(ts) >= maxFails {
				continue
			}
			if last := ts[len(ts)-1]; !found || last.Before(at) {
				oldest, at, found = email, last, true
			}
		}
		if !found {
			return false
		}
		delete(s.fails, oldest)
	}
	return true
}

// Login valida credenciales y abre una sesión. La derivación de la clave
// (verifyPassword, cara en CPU/memoria por diseño de argon2id, acotada a
// maxConcurrentKDF derivaciones a la vez por acquireKDF/releaseKDF) se
// ejecuta fuera de s.mu: solo el throttle, la copia del usuario candidato y
// el registro final de fallo o sesión están protegidos por el lock, así
// Resolve y otros Login no esperan a que termine argon2id. El rol también
// se lee bajo el lock (hasRole, más abajo): candidate.OrgRoles es el mismo
// mapa que el guardado en s.users (los mapas se comparten por referencia al
// copiar el struct), así que tocarlo después de soltar el lock sería una
// lectura sin sincronizar frente a una futura escritura concurrente.
func (s *Store) Login(email, password, orgID string) (Session, error) {
	email = normalizeEmail(email)

	s.mu.Lock()
	if s.throttled(email) {
		s.mu.Unlock()
		return Session{}, ErrThrottled
	}
	var candidate userRecord
	found := false
	for _, u := range s.users {
		if u.Email == email {
			candidate, found = u, true
			break
		}
	}
	var hasRole bool
	if found {
		_, hasRole = candidate.OrgRoles[orgID]
	}
	verify := s.verifyPassword
	s.mu.Unlock()

	s.acquireKDF()
	ok := found && verify(password, candidate.PasswordHash)
	s.releaseKDF()
	if ok && !hasRole {
		ok = false
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	if !ok {
		s.registerFail(email)
		return Session{}, ErrInvalidCredentials
	}
	return s.newSessionLocked(candidate.ID, orgID)
}

// newSessionLocked crea y persiste una sesión con s.mu tomado. Si la
// escritura falla, la sesión se retira del mapa y el error sale envuelto en
// ErrPersistence: dejarla viva en memoria acumulaba sesiones huérfanas que
// el cliente nunca recibía, y confundir ese fallo con unas credenciales
// malas daba un diagnóstico falso ante un problema de disco (hallazgo C8).
func (s *Store) newSessionLocked(userID, orgID string) (Session, error) {
	now := s.now().UTC()
	sess := Session{Token: randomHex(32), UserID: userID, OrgID: orgID, CSRF: randomHex(16), CreatedAt: now, ExpiresAt: now.Add(SessionTTL)}
	s.sessions[sess.Token] = sess
	if err := s.persistSessions(); err != nil {
		delete(s.sessions, sess.Token)
		return Session{}, fmt.Errorf("%w: %w", ErrPersistence, err)
	}
	return sess, nil
}

// StartSession abre una sesión para un usuario ya identificado, sin
// contraseña y sin pasar por el limitador de intentos: lo usa el asistente
// inicial, que acaba de fijar en el propio servidor la contraseña del owner
// recién creado. El limitador protege el adivinado de contraseñas en Login
// y ahí sigue; aquí no hay nada que adivinar, y hacerle caso dejaba una
// instalación con owner creado y sin sesión (spec §6.2, hallazgo C10).
// Falla con ErrUnauthenticated si el usuario no existe o no tiene rol en la
// organización.
func (s *Store) StartSession(userID, orgID string) (Session, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	u, ok := s.userByIDLocked(userID)
	if !ok {
		return Session{}, ErrUnauthenticated
	}
	if _, hasRole := u.OrgRoles[orgID]; !hasRole {
		return Session{}, ErrUnauthenticated
	}
	return s.newSessionLocked(u.ID, orgID)
}

// Logout cierra la sesión.
func (s *Store) Logout(token string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.sessions, token)
	return s.persistSessions()
}

// Resolve devuelve el principal de una sesión vigente.
func (s *Store) Resolve(token string) (*Principal, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[token]
	if !ok {
		return nil, ErrUnauthenticated
	}
	if !sess.ExpiresAt.After(s.now()) {
		delete(s.sessions, token)
		// Borrado best-effort: si falla, la sesión ya expiró y sigue
		// siendo inválida en memoria; el fichero se limpiará en el
		// siguiente Login/Logout que sí compruebe el error de persistSessions.
		_ = s.persistSessions()
		return nil, ErrUnauthenticated
	}
	u, ok := s.userByIDLocked(sess.UserID)
	if !ok {
		return nil, ErrUnauthenticated
	}
	return &Principal{UserID: u.ID, Email: u.Email, Name: u.Name, OrgID: sess.OrgID, Role: u.OrgRoles[sess.OrgID], Via: "session", CSRF: sess.CSRF}, nil
}

// LocalToken devuelve el token de CLI/MCP.
func (s *Store) LocalToken() string { return s.localToken }

// ResolveLocal acepta el token local como admin de la organización.
func (s *Store) ResolveLocal(token, orgID string) (*Principal, error) {
	if subtle.ConstantTimeCompare([]byte(token), []byte(s.localToken)) != 1 {
		return nil, ErrUnauthenticated
	}
	return &Principal{UserID: "local", Email: "local@lucidfence", Name: "Token local", OrgID: orgID, Role: Admin, Via: "local-token"}, nil
}

func (s *Store) userByIDLocked(id string) (userRecord, bool) {
	for _, u := range s.users {
		if u.ID == id {
			return u, true
		}
	}
	return userRecord{}, false
}

// UserByID busca un usuario. Devuelve el tipo público (sin el hash).
func (s *Store) UserByID(id string) (User, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rec, ok := s.userByIDLocked(id)
	return rec.User, ok
}
