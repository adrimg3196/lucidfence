package auth

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"errors"
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
)

// User es un usuario local. password_hash nunca se serializa hacia la API.
type User struct {
	ID           string          `json:"id"`
	Email        string          `json:"email"`
	Name         string          `json:"name"`
	PasswordHash string          `json:"password_hash"`
	OrgRoles     map[string]Role `json:"org_roles"`
	CreatedAt    time.Time       `json:"created_at"`
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
	users      []User
	sessions   map[string]Session
	localToken string
	fails      map[string][]time.Time
	// verifyPassword deriva y compara la contraseña; por defecto es
	// VerifyPassword. Es inyectable (campo no exportado) para que los tests
	// puedan bloquearla de forma controlada y comprobar que Login nunca la
	// llama con s.mu tomado (ver TestLoginNoBloqueaResolve).
	verifyPassword func(pw, hash string) bool
}

// Open carga usuarios y sesiones y garantiza el token local.
func Open(dir string, now func() time.Time) (*Store, error) {
	if now == nil {
		now = time.Now
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	s := &Store{dir: dir, now: now, sessions: map[string]Session{}, fails: map[string][]time.Time{}, verifyPassword: VerifyPassword}
	var users collection[User]
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

func (s *Store) persistUsers(users []User) error {
	return store.WriteJSON(filepath.Join(s.dir, "users.json"), collection[User]{SchemaVersion: 1, Items: users})
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

// Setup crea el primer usuario como owner de la organización.
func (s *Store) Setup(email, name, password, orgID string) (User, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.users) > 0 {
		return User{}, ErrAlreadySetUp
	}
	email = normalizeEmail(email)
	if email == "" || !strings.Contains(email, "@") || strings.TrimSpace(name) == "" {
		return User{}, errors.New("email y nombre obligatorios")
	}
	hash, err := HashPassword(password)
	if err != nil {
		return User{}, err
	}
	u := User{ID: "usr_" + randomHex(8), Email: email, Name: strings.TrimSpace(name), PasswordHash: hash,
		OrgRoles: map[string]Role{orgID: Owner}, CreatedAt: s.now().UTC()}
	// Persistir sobre una copia y asignar a s.users solo si tiene éxito: un
	// error de escritura (disco lleno, permisos) no debe dejar el owner
	// "creado" en memoria sin estar en disco.
	candidate := append(append([]User{}, s.users...), u)
	if err := s.persistUsers(candidate); err != nil {
		return User{}, err
	}
	s.users = candidate
	return u, nil
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

// registerFail anota un intento fallido. Si el mapa ha crecido más allá de
// maxTrackedFailEmails (una avalancha de emails distintos, típica de un
// intento de agotar memoria) se descarta entero en vez de mantener un
// índice adicional de antigüedad solo para podarlo: es una salvaguarda de
// memoria, no una garantía de precisión del throttle a esa escala.
func (s *Store) registerFail(email string) {
	if len(s.fails) >= maxTrackedFailEmails {
		s.fails = make(map[string][]time.Time)
	}
	s.fails[email] = append(s.fails[email], s.now())
}

// Login valida credenciales y abre una sesión. La derivación de la clave
// (verifyPassword, cara en CPU/memoria por diseño de argon2id) se ejecuta
// fuera de s.mu: solo el throttle, la copia del usuario candidato y el
// registro final de fallo o sesión están protegidos por el lock, así
// Resolve y otros Login no esperan a que termine argon2id.
func (s *Store) Login(email, password, orgID string) (Session, error) {
	email = normalizeEmail(email)

	s.mu.Lock()
	if s.throttled(email) {
		s.mu.Unlock()
		return Session{}, ErrThrottled
	}
	var candidate User
	found := false
	for _, u := range s.users {
		if u.Email == email {
			candidate, found = u, true
			break
		}
	}
	verify := s.verifyPassword
	s.mu.Unlock()

	ok := found && verify(password, candidate.PasswordHash)
	if ok {
		if _, hasOrg := candidate.OrgRoles[orgID]; !hasOrg {
			ok = false
		}
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	if !ok {
		s.registerFail(email)
		return Session{}, ErrInvalidCredentials
	}
	now := s.now().UTC()
	sess := Session{Token: randomHex(32), UserID: candidate.ID, OrgID: orgID, CSRF: randomHex(16), CreatedAt: now, ExpiresAt: now.Add(SessionTTL)}
	s.sessions[sess.Token] = sess
	return sess, s.persistSessions()
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

func (s *Store) userByIDLocked(id string) (User, bool) {
	for _, u := range s.users {
		if u.ID == id {
			return u, true
		}
	}
	return User{}, false
}

// UserByID busca un usuario.
func (s *Store) UserByID(id string) (User, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.userByIDLocked(id)
}
