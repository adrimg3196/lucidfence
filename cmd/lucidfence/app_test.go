package main

import (
	"bytes"
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
