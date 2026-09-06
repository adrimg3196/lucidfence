package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
)

func TestOpenAbreSiHealthResponde(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v1/health" {
			_, _ = w.Write([]byte(`{"status":"ok"}`))
			return
		}
		http.NotFound(w, r)
	}))
	defer srv.Close()
	var opened string
	prev := browserOpener
	browserOpener = func(url string) error { opened = url; return nil }
	defer func() { browserOpener = prev }()
	var out, errb bytes.Buffer
	code := runOpen([]string{"-config", filepath.Join(t.TempDir(), "config.json"), "-listen", strings.TrimPrefix(srv.URL, "http://")}, &out, &errb)
	if code != 0 || opened != srv.URL+"/" {
		t.Fatalf("exit=%d opened=%q stderr=%s", code, opened, errb.String())
	}
}

func TestOpenSinServidorExplica(t *testing.T) {
	prev := browserOpener
	browserOpener = func(string) error { t.Fatal("no debe abrir"); return nil }
	defer func() { browserOpener = prev }()
	var out, errb bytes.Buffer
	code := runOpen([]string{"-config", filepath.Join(t.TempDir(), "config.json"), "-listen", "127.0.0.1:1"}, &out, &errb)
	if code != 1 || !strings.Contains(errb.String(), "lucidfence serve") {
		t.Fatalf("exit=%d stderr=%q", code, errb.String())
	}
}
