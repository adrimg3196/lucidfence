// Package store persiste el estado de LucidFence en JSON y JSONL en disco
// (ADR: sin base de datos). Escrituras atómicas (temporal + rename), permisos
// 0600/0700, un lock por organización.
package store

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sync"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// ErrNotFound indica que el fichero o documento no existe.
var ErrNotFound = errors.New("no existe")

var orgIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,39}$`)

// Store es la raíz del directorio de datos.
type Store struct {
	root          string
	mu            sync.Mutex
	orgs          map[string]*OrgStore
	secretsMu     sync.Mutex
	defaultEgress settings.Egress
}

// Option configura el Store al abrirlo.
type Option func(*Store)

// WithDefaultEgress fija la allowlist de salida con la que se siembra
// settings.json la primera vez que se leen los ajustes de una organización
// (spec §5.8). Sin esta opción la siembra sale vacía. store no importa
// internal/config (spec §5.2, store → domain): el llamante (cmd/, que ya
// importa config) convierte config.EgressConfig a settings.Egress.
func WithDefaultEgress(egress settings.Egress) Option {
	return func(s *Store) {
		s.defaultEgress = settings.Egress{
			Hosts:        append([]string(nil), egress.Hosts...),
			AllowPrivate: egress.AllowPrivate,
		}
	}
}

// Open crea la estructura de directorios si falta.
func Open(root string, opts ...Option) (*Store, error) {
	for _, d := range []string{"", "orgs", "auth", "secrets", "cache"} {
		if err := os.MkdirAll(filepath.Join(root, d), 0o700); err != nil {
			return nil, fmt.Errorf("crear %s: %w", filepath.Join(root, d), err)
		}
	}
	s := &Store{root: root, orgs: make(map[string]*OrgStore)}
	for _, opt := range opts {
		opt(s)
	}
	return s, nil
}

// Root devuelve el directorio de datos.
func (s *Store) Root() string { return s.root }

// AuthDir devuelve el directorio de usuarios y sesiones.
func (s *Store) AuthDir() string { return filepath.Join(s.root, "auth") }

// CacheDir devuelve el directorio de cachés (CVE).
func (s *Store) CacheDir() string { return filepath.Join(s.root, "cache") }

// Org abre (creando si falta) el almacén de una organización. Devuelve
// siempre la misma instancia para un id; el lock es por organización.
func (s *Store) Org(id string) (*OrgStore, error) {
	if !orgIDPattern.MatchString(id) {
		return nil, fmt.Errorf("id de organización %q inválido", id)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if o, ok := s.orgs[id]; ok {
		return o, nil
	}
	dir := filepath.Join(s.root, "orgs", id)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	o := &OrgStore{id: id, dir: dir, defaultEgress: s.defaultEgress}
	s.orgs[id] = o
	return o, nil
}

// WriteJSON escribe v de forma atómica con permisos 0600.
func WriteJSON(path string, v any) error {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return fmt.Errorf("serializar %s: %w", filepath.Base(path), err)
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	defer func() { _ = os.Remove(tmp.Name()) }()
	if err := tmp.Chmod(0o600); err != nil {
		_ = tmp.Close()
		return err
	}
	if _, err := tmp.Write(append(data, '\n')); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmp.Name(), path)
}

// ReadJSON lee un fichero JSON; ErrNotFound si falta.
func ReadJSON(path string, v any) error {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return ErrNotFound
	}
	if err != nil {
		return err
	}
	if err := json.Unmarshal(data, v); err != nil {
		return fmt.Errorf("leer %s: %w", filepath.Base(path), err)
	}
	return nil
}
