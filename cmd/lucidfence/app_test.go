package main

import (
	"bytes"
	"context"
	"log/slog"
	"path/filepath"
	"strings"
	"testing"
)

func TestBuildAppSimulacionPorDefecto(t *testing.T) {
	dir := t.TempDir()
	a, err := buildApp(commonFlags{ConfigPath: filepath.Join(dir, "config.json"), DataDir: filepath.Join(dir, "data")}, slog.New(slog.NewTextHandler(&bytes.Buffer{}, nil)))
	if err != nil {
		t.Fatal(err)
	}
	if a.cfg.Mode != "simulation" || a.engine == nil || a.handler == nil || a.auth == nil || a.org.ID() != "default" {
		t.Fatalf("%+v", a.cfg)
	}
}

func TestBuildAppModoLiveNoDisponibleEnM1(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "config.json")
	writeFile(t, cfg, `{"mode":"live"}`)
	_, err := buildApp(commonFlags{ConfigPath: cfg, DataDir: filepath.Join(dir, "data")}, slog.Default())
	if err == nil || !strings.Contains(err.Error(), "live") {
		t.Fatalf("esperaba error de modo live: %v", err)
	}
}

func TestAppForServeRespetaLogLevel(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "config.json")
	writeFile(t, cfg, `{"log_level":"debug"}`)
	a, err := appForServe(commonFlags{ConfigPath: cfg, DataDir: filepath.Join(dir, "data")}, &bytes.Buffer{})
	if err != nil {
		t.Fatal(err)
	}
	if !a.logger.Enabled(context.Background(), slog.LevelDebug) {
		t.Fatal("con log_level=debug el logger debería aceptar Debug")
	}

	dir2 := t.TempDir()
	cfg2 := filepath.Join(dir2, "config.json")
	writeFile(t, cfg2, `{"log_level":"error"}`)
	a2, err := appForServe(commonFlags{ConfigPath: cfg2, DataDir: filepath.Join(dir2, "data")}, &bytes.Buffer{})
	if err != nil {
		t.Fatal(err)
	}
	if a2.logger.Enabled(context.Background(), slog.LevelInfo) {
		t.Fatal("con log_level=error el logger no debería aceptar Info")
	}
}

func TestDialAddrSustituyeHostComodin(t *testing.T) {
	cases := map[string]string{
		":8765":          "127.0.0.1:8765",
		"0.0.0.0:8765":   "127.0.0.1:8765",
		"[::]:8765":      "127.0.0.1:8765",
		"127.0.0.1:8765": "127.0.0.1:8765",
	}
	for in, want := range cases {
		if got := dialAddr(in); got != want {
			t.Errorf("dialAddr(%q) = %q, quiero %q", in, got, want)
		}
	}
}

func TestPosicionalesRechazados(t *testing.T) {
	for _, cmd := range []string{"serve", "doctor", "open"} {
		var out, errb bytes.Buffer
		code := run([]string{cmd, "extra"}, &out, &errb)
		want := `lucidfence ` + cmd + `: argumento inesperado "extra"`
		if code != 2 || !strings.Contains(errb.String(), want) {
			t.Fatalf("%s: exit=%d stderr=%q, quiero exit=2 y %q", cmd, code, errb.String(), want)
		}
	}
}

func TestParseCommonFlags(t *testing.T) {
	var errb bytes.Buffer
	f, _, err := parseCommon("serve", []string{"-data", "/tmp/x", "-listen", "127.0.0.1:1"}, &errb, nil)
	if err != nil || f.DataDir != "/tmp/x" || f.Listen != "127.0.0.1:1" || f.ConfigPath != "config.json" {
		t.Fatalf("%v %+v", err, f)
	}
	if _, _, err := parseCommon("serve", []string{"-nope"}, &errb, nil); err == nil {
		t.Fatal("flag desconocido debe fallar")
	}
}
