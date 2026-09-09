package store

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"strconv"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

// ErrBadCursor lo devuelve DecodeCursor ante un cursor manipulado o de otro
// origen. La API lo traduce a 400 invalid, nunca a 500 (spec §6.1).
var ErrBadCursor = errors.New("cursor inválido")

const (
	// MaxPageLimit es el tamaño máximo de página; un limit mayor se acota.
	MaxPageLimit = 500
	// DefaultPageLimit es el tamaño cuando no se pide límite: el mismo
	// defecto que ya usan GET /api/v1/events y /api/v1/actions.
	DefaultPageLimit = 100
)

// EncodeCursor codifica en base64url sin relleno el índice absoluto de línea
// desde el principio del fichero. Los JSONL son solo append, así que un
// índice ya emitido nunca se desplaza. Un índice negativo (no queda nada por
// delante) es el cursor vacío.
func EncodeCursor(index int) string {
	if index < 0 {
		return ""
	}
	return base64.RawURLEncoding.EncodeToString([]byte(strconv.Itoa(index)))
}

// DecodeCursor deshace EncodeCursor. Cualquier cursor que no sea base64url de
// un entero no negativo devuelve ErrBadCursor.
func DecodeCursor(cursor string) (int, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return 0, ErrBadCursor
	}
	index, err := strconv.Atoi(string(raw))
	if err != nil || index < 0 {
		return 0, ErrBadCursor
	}
	return index, nil
}

// normalizeLimit acota el tamaño de página pedido.
func normalizeLimit(limit int) int {
	switch {
	case limit <= 0:
		return DefaultPageLimit
	case limit > MaxPageLimit:
		return MaxPageLimit
	default:
		return limit
	}
}

// pageLines decodifica al tipo T una página de líneas crudas.
func pageLines[T any](o *OrgStore, name string, limit int, cursor string) ([]T, string, error) {
	o.mu.RLock()
	raws, next, err := pageJSONL(o.Path(name), limit, cursor)
	o.mu.RUnlock()
	if err != nil {
		return nil, "", err
	}
	out := make([]T, 0, len(raws))
	for _, r := range raws {
		var v T
		if err := json.Unmarshal(r, &v); err != nil {
			return nil, "", err
		}
		out = append(out, v)
	}
	return out, next, nil
}

// EventsPage devuelve una página de transiciones, de la más reciente a la más
// antigua; next es "" cuando no queda nada por delante.
func (o *OrgStore) EventsPage(limit int, cursor string) (items []transition.Transition, next string, err error) {
	return pageLines[transition.Transition](o, "events.jsonl", limit, cursor)
}

// ActionsPage devuelve una página de resultados de acciones, del más reciente
// al más antiguo; next es "" cuando no queda nada por delante.
func (o *OrgStore) ActionsPage(limit int, cursor string) (items []action.Result, next string, err error) {
	return pageLines[action.Result](o, "actions.jsonl", limit, cursor)
}
