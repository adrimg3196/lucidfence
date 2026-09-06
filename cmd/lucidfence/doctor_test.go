package main

import (
	"bytes"
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
