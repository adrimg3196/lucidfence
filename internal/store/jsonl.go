package store

import (
	"bufio"
	"encoding/json"
	"errors"
	"os"
)

// AppendJSONL añade una línea JSON al final del fichero (solo append).
func AppendJSONL(path string, v any) error {
	line, err := json.Marshal(v)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return err
	}
	defer func() { _ = f.Close() }()
	_, err = f.Write(append(line, '\n'))
	return err
}

// ReadJSONL devuelve las últimas limit líneas (todas si limit <= 0) en orden
// cronológico. Un fichero ausente equivale a vacío. Lee el fichero completo:
// suficiente para volúmenes de flota; no es un log de big data.
func ReadJSONL(path string, limit int) ([]json.RawMessage, error) {
	f, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	defer func() { _ = f.Close() }()
	var out []json.RawMessage
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 8*1024*1024)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		out = append(out, json.RawMessage(append([]byte(nil), line...)))
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if limit > 0 && len(out) > limit {
		out = out[len(out)-limit:]
	}
	return out, nil
}

// pageJSONL devuelve una ventana de líneas de la más reciente a la más
// antigua. Un cursor vacío empieza por el final del fichero; el cursor
// devuelto apunta a la siguiente línea hacia atrás y es "" cuando ya no queda
// nada. limit se normaliza y un cursor ilegible devuelve ErrBadCursor. Un
// cursor por delante del final (fichero rotado) se ajusta a la última línea.
func pageJSONL(path string, limit int, cursor string) ([]json.RawMessage, string, error) {
	raws, err := ReadJSONL(path, 0)
	if err != nil {
		return nil, "", err
	}
	end := len(raws) - 1
	if cursor != "" {
		index, err := DecodeCursor(cursor)
		if err != nil {
			return nil, "", err
		}
		if index < end {
			end = index
		}
	}
	if end < 0 {
		return []json.RawMessage{}, "", nil
	}
	start := end - normalizeLimit(limit) + 1
	if start < 0 {
		start = 0
	}
	out := make([]json.RawMessage, 0, end-start+1)
	for i := end; i >= start; i-- {
		out = append(out, raws[i])
	}
	return out, EncodeCursor(start - 1), nil
}
