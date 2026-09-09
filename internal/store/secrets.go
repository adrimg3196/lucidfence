package store

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// SecretEnvPrefix es el prefijo de las variables de entorno que llevan
// secretos. Una variable definida gana al fichero (spec §5.8). La variable es
// global al proceso: gana para todas las organizaciones, así que el fichero es
// la vía multi-tenant y la variable la de un despliegue de una sola org.
const SecretEnvPrefix = "LUCIDFENCE_"

// secretNamePattern acota el nombre de un secreto a un slug en minúsculas.
// Es lo que impide que "../../auth/local-token" sea un nombre válido.
var secretNamePattern = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]{0,63}$`)

// secretDoc es el fichero de un secreto: {"schema_version": 1, "value": "..."}.
type secretDoc struct {
	SchemaVersion int    `json:"schema_version"`
	Value         string `json:"value"`
}

// SecretsDir devuelve <data>/secrets/<org>/.
func (s *Store) SecretsDir(org string) string {
	return filepath.Join(s.root, "secrets", org)
}

// SecretEnvName traduce el nombre de un secreto a su variable de entorno:
// "webhook_secret" → "LUCIDFENCE_WEBHOOK_SECRET".
func SecretEnvName(name string) string {
	return SecretEnvPrefix + strings.ToUpper(strings.ReplaceAll(name, "-", "_"))
}

func (s *Store) secretPath(org, name string) (string, error) {
	if !orgIDPattern.MatchString(org) {
		return "", fmt.Errorf("id de organización %q inválido", org)
	}
	if !secretNamePattern.MatchString(name) {
		return "", fmt.Errorf("nombre de secreto %q inválido (minúsculas, dígitos, guiones)", name)
	}
	return filepath.Join(s.SecretsDir(org), name+".json"), nil
}

// Secret devuelve el valor de un secreto. La variable LUCIDFENCE_<NAME> gana
// al fichero; si no hay ninguno de los dos devuelve ErrNotFound. El valor no
// se registra en ningún log ni se serializa en ninguna respuesta.
func (s *Store) Secret(org, name string) (string, error) {
	path, err := s.secretPath(org, name)
	if err != nil {
		return "", err
	}
	if v := strings.TrimSpace(os.Getenv(SecretEnvName(name))); v != "" {
		return v, nil
	}
	s.secretsMu.Lock()
	defer s.secretsMu.Unlock()
	var doc secretDoc
	if err := ReadJSON(path, &doc); err != nil {
		return "", err
	}
	if doc.Value == "" {
		return "", ErrNotFound
	}
	return doc.Value, nil
}

// SaveSecret escribe el secreto de forma atómica con permisos 0600 dentro de
// <data>/secrets/<org>/ (0700). Un valor vacío es un error: para quitar un
// secreto está DeleteSecret.
func (s *Store) SaveSecret(org, name, value string) error {
	path, err := s.secretPath(org, name)
	if err != nil {
		return err
	}
	if value == "" {
		return errors.New("el valor del secreto no puede estar vacío")
	}
	s.secretsMu.Lock()
	defer s.secretsMu.Unlock()
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	return WriteJSON(path, secretDoc{SchemaVersion: schemaVersion, Value: value})
}

// DeleteSecret borra el fichero del secreto. Borrar uno que no existe no es
// un error. No toca la variable de entorno: si LUCIDFENCE_<NAME> sigue
// definida, Secret la seguirá devolviendo.
func (s *Store) DeleteSecret(org, name string) error {
	path, err := s.secretPath(org, name)
	if err != nil {
		return err
	}
	s.secretsMu.Lock()
	defer s.secretsMu.Unlock()
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}
