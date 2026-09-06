package main

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDoctorInstalacionLimpia(t *testing.T) {
	dir := t.TempDir()
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", filepath.Join(dir, "config.json"), "-data", filepath.Join(dir, "data"), "-listen", "127.0.0.1:1"}, &out, &errb)
	s := out.String()
	for _, want := range []string{"OK    binario", "OK    config.json", "OK    directorio de datos", "WARN  usuarios", "WARN  servidor"} {
		if !strings.Contains(s, want) {
			t.Fatalf("falta %q en:\n%s", want, s)
		}
	}
	if code != 0 {
		t.Fatalf("sin FAIL el exit es 0, got %d", code)
	}
}

// servidorDeSalud levanta un servidor que responde el cuerpo dado en
// /api/v1/health y devuelve su dirección, para que doctor lo sondee como si
// fuera un lucidfence serve en marcha.
func servidorDeSalud(t *testing.T, cuerpo string) string {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/health" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, cuerpo)
	}))
	t.Cleanup(srv.Close)
	return strings.TrimPrefix(srv.URL, "http://")
}

// TestDoctorReportaPersistenciaDegradada comprueba que doctor deja de decir
// que todo está bien cuando el servidor responde pero no puede guardar: la
// degradación de persistencia sale como fila FAIL con el motivo y el exit es
// 1 (spec §11 "doctor lo explica", hallazgo C21).
func TestDoctorReportaPersistenciaDegradada(t *testing.T) {
	dir := t.TempDir()
	addr := servidorDeSalud(t, `{"status":"ok","persistence":{"ok":false,"last_error":"open devices.json: permission denied"}}`)
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", filepath.Join(dir, "config.json"), "-data", filepath.Join(dir, "data"), "-listen", addr}, &out, &errb)
	if code != 1 {
		t.Fatalf("exit=%d, quiero 1\n%s", code, out.String())
	}
	s := out.String()
	if !strings.Contains(s, "FAIL  persistencia") || !strings.Contains(s, "open devices.json: permission denied") {
		t.Fatalf("falta la fila de persistencia degradada con su motivo:\n%s", s)
	}
}

// TestDoctorReportaPersistenciaSana comprueba la otra cara: con el servidor
// respondiendo persistence.ok, doctor añade la fila en OK y no falla.
func TestDoctorReportaPersistenciaSana(t *testing.T) {
	dir := t.TempDir()
	addr := servidorDeSalud(t, `{"status":"ok","persistence":{"ok":true}}`)
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", filepath.Join(dir, "config.json"), "-data", filepath.Join(dir, "data"), "-listen", addr}, &out, &errb)
	s := out.String()
	if code != 0 || !strings.Contains(s, "OK    persistencia") || !strings.Contains(s, "OK    servidor") {
		t.Fatalf("exit=%d\n%s", code, s)
	}
}

// TestDoctorAvisaSiElServidorNoInformaDePersistencia cubre el servidor de
// otra versión: responde a /health sin el objeto persistence, así que doctor
// avisa en vez de dar por buena una persistencia que nadie ha declarado.
func TestDoctorAvisaSiElServidorNoInformaDePersistencia(t *testing.T) {
	dir := t.TempDir()
	addr := servidorDeSalud(t, `{"status":"ok"}`)
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", filepath.Join(dir, "config.json"), "-data", filepath.Join(dir, "data"), "-listen", addr}, &out, &errb)
	s := out.String()
	if code != 0 || !strings.Contains(s, "WARN  persistencia") {
		t.Fatalf("exit=%d\n%s", code, s)
	}
}

func TestDoctorFallaSiOrgNoLegible(t *testing.T) {
	dir := t.TempDir()
	dataDir := filepath.Join(dir, "data")
	// store.Org crea "<data>/orgs/<id>" bajo demanda (Store.Open solo
	// prepara "<data>/orgs"); si ya existe como fichero regular, st.Org
	// falla al intentar MkdirAll sobre él.
	if err := os.MkdirAll(filepath.Join(dataDir, "orgs"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "orgs", "default"), []byte("no soy un directorio"), 0o600); err != nil {
		t.Fatal(err)
	}
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", filepath.Join(dir, "config.json"), "-data", dataDir}, &out, &errb)
	if code != 1 {
		t.Fatalf("exit=%d, quiero 1\n%s", code, out.String())
	}
	if !strings.Contains(out.String(), "FAIL  seed de simulación") {
		t.Fatalf("falta FAIL de seed de simulación en:\n%s", out.String())
	}
}

func TestDoctorFallaConConfigInvalida(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "config.json")
	_ = os.WriteFile(cfg, []byte(`{"interval_seconds": 1}`), 0o600)
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", cfg, "-data", filepath.Join(dir, "data")}, &out, &errb)
	if code != 1 || !strings.Contains(out.String(), "FAIL  config.json") || !strings.Contains(out.String(), "interval_seconds") {
		t.Fatalf("exit=%d\n%s", code, out.String())
	}
}
