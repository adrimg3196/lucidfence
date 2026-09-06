package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHealthEsPublicoYNoFiltraSecretos(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("GET", "/api/v1/health", nil, false)
	if res.StatusCode != 200 || out["status"] != "ok" || out["setup_required"] != true || out["mode"] != "simulation" || out["enforcement"] != "observe" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	if _, has := out["local_token"]; has {
		t.Fatal("health nunca expone secretos")
	}
	if res.Header.Get("X-Content-Type-Options") != "nosniff" || res.Header.Get("X-Request-ID") == "" {
		t.Fatal("cabeceras de seguridad y request id")
	}
	res, out = e.do("GET", "/api/v1/readyz", nil, false)
	if res.StatusCode != 200 || out["ready"] != true {
		t.Fatalf("readyz: %d %v", res.StatusCode, out)
	}
}

func TestRutaProtegidaSinSesion401YDesconocida404(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("GET", "/api/v1/devices", nil, false)
	if res.StatusCode != 401 || out["code"] != "unauthenticated" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/nada", nil, false)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
}

func TestTokenLocalPorBearerDesdeLoopback(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	req, _ := newRequest(e, "GET", "/api/v1/auth/me")
	req.Header.Set("Authorization", "Bearer "+e.auth.LocalToken())
	res, out := send(e, req)
	if res.StatusCode != 200 || out["user"].(map[string]any)["via"] != "local-token" || out["user"].(map[string]any)["role"] != "admin" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	req, _ = newRequest(e, "GET", "/api/v1/auth/me")
	req.Header.Set("Authorization", "Bearer incorrecto")
	if res, _ := send(e, req); res.StatusCode != 401 {
		t.Fatal("bearer incorrecto → 401")
	}
}

func TestDecodeJSONQueryIntWriteErrorDetail(t *testing.T) {
	bad := httptest.NewRequest(http.MethodPost, "/x", strings.NewReader(`{"a":1,"sobra":2}`))
	var v struct {
		A int `json:"a"`
	}
	if err := decodeJSON(bad, &v); err == nil {
		t.Fatal("decodeJSON debería rechazar campos desconocidos")
	}

	if got := queryInt(httptest.NewRequest(http.MethodGet, "/x?limit=5", nil), "limit", 10, 100); got != 5 {
		t.Fatalf("queryInt con valor válido = %d, quería 5", got)
	}
	if got := queryInt(httptest.NewRequest(http.MethodGet, "/x", nil), "page", 20, 100); got != 20 {
		t.Fatalf("queryInt sin parámetro = %d, quería el valor por defecto 20", got)
	}
	if got := queryInt(httptest.NewRequest(http.MethodGet, "/x?cursor=no-es-numero", nil), "cursor", 30, 100); got != 30 {
		t.Fatalf("queryInt inválido = %d, quería el valor por defecto 30", got)
	}
	if got := queryInt(httptest.NewRequest(http.MethodGet, "/x?n=500", nil), "n", 10, 200); got != 200 {
		t.Fatalf("queryInt por encima del máximo = %d, quería el tope 200", got)
	}

	w := httptest.NewRecorder()
	writeErrorDetail(w, http.StatusBadRequest, "invalid", "mensaje", "detalle")
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if w.Code != http.StatusBadRequest || body["code"] != "invalid" || body["detail"] != "detalle" {
		t.Fatalf("writeErrorDetail: %d %v", w.Code, body)
	}
}
