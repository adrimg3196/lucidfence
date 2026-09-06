// Package api monta la API HTTP /api/v1 (spec §6.1): un fichero por recurso,
// registro de rutas con capacidad obligatoria, errores con forma única y el
// dashboard embebido en /.
package api

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strconv"
)

type errorBody struct {
	Error  string `json:"error"`
	Code   string `json:"code"`
	Detail any    `json:"detail,omitempty"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, errorBody{Error: msg, Code: code})
}

func writeErrorDetail(w http.ResponseWriter, status int, code, msg string, detail any) {
	writeJSON(w, status, errorBody{Error: msg, Code: code, Detail: detail})
}

// writeInternalError registra el error real del store (que puede llevar
// rutas de fichero u otros detalles internos) en el logger del servidor y
// responde al cliente sin filtrar nada de eso. El log lleva el id de
// petición que securityHeaders ya fijó en la cabecera (y que el cliente ve
// en X-Request-ID), única forma de correlacionar el id que reporta el
// usuario con la línea del error real (spec §11).
func writeInternalError(w http.ResponseWriter, logger *slog.Logger, op string, err error) {
	logger.Error("api", "op", op, "request_id", w.Header().Get("X-Request-ID"), "error", err)
	writeError(w, http.StatusInternalServerError, "internal", "error interno")
}

const maxBody = 1 << 20

var errBadJSON = errors.New("cuerpo JSON inválido")

// decodeJSON lee hasta 1 MiB, rechaza campos desconocidos.
func decodeJSON(r *http.Request, v any) error {
	dec := json.NewDecoder(io.LimitReader(r.Body, maxBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return fmt.Errorf("%w: %v", errBadJSON, err)
	}
	return nil
}

func queryInt(r *http.Request, name string, def, max int) int {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return def
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n < 1 {
		return def
	}
	if n > max {
		return max
	}
	return n
}
