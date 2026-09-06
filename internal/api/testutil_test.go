package api

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
)

type testEnv struct {
	t      *testing.T
	srv    *httptest.Server
	auth   *auth.Store
	org    *store.OrgStore
	cookie *http.Cookie
	csrf   string
}

func newTestEnv(t *testing.T) *testEnv {
	t.Helper()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	clock := func() time.Time { return now }
	st, _ := store.Open(t.TempDir())
	org, _ := st.Org("default")
	as, err := auth.Open(st.AuthDir(), clock)
	if err != nil {
		t.Fatal(err)
	}
	// Sin conectores: internal/api nunca importa un conector concreto, ni
	// siquiera en tests (spec §5.2, depguard); estos tests solo ejercen la
	// capa HTTP, no el ciclo del motor, así que un motor sin adaptadores
	// basta para ejercitar health/auth.
	eng := engine.New(org, nil, engine.Options{Mode: "simulation", Interval: time.Hour, Now: clock})
	h, _ := New(Deps{Engine: eng, Org: org, Auth: as, Web: http.NotFoundHandler(), Config: config.Default(), Now: clock})
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	return &testEnv{t: t, srv: srv, auth: as, org: org}
}

func (e *testEnv) do(method, path string, body any, authed bool) (*http.Response, map[string]any) {
	e.t.Helper()
	var buf bytes.Buffer
	if body != nil {
		_ = json.NewEncoder(&buf).Encode(body)
	}
	req, _ := http.NewRequest(method, e.srv.URL+path, &buf)
	req.Header.Set("Content-Type", "application/json")
	if authed && e.cookie != nil {
		req.AddCookie(e.cookie)
		req.Header.Set(CSRFHeader, e.csrf)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	_ = res.Body.Close()
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	return res, out
}

func (e *testEnv) setup(mode string) map[string]any {
	e.t.Helper()
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "adri@example.com", "name": "Adri", "password": "contraseña-larga-1", "mode": mode}, false)
	if res.StatusCode != 201 {
		e.t.Fatalf("setup: %d %v", res.StatusCode, out)
	}
	for _, c := range res.Cookies() {
		if c.Name == CookieName {
			e.cookie = c
		}
	}
	e.csrf, _ = out["csrf"].(string)
	if e.cookie == nil || e.csrf == "" {
		e.t.Fatalf("setup sin cookie/csrf: %v", out)
	}
	return out
}

func newRequest(e *testEnv, method, path string) (*http.Request, error) {
	return http.NewRequest(method, e.srv.URL+path, nil)
}

func send(e *testEnv, req *http.Request) (*http.Response, map[string]any) {
	e.t.Helper()
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	_ = res.Body.Close()
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	return res, out
}
