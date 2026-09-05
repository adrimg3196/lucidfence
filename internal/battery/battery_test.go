package battery

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRunCuentaPassYFail(t *testing.T) {
	checks := []Check{
		{Name: "ok", Run: func(context.Context, *Env) error { return nil }},
		{Name: "ko", Run: func(context.Context, *Env) error { return errors.New("boom") }},
	}
	var out bytes.Buffer
	passed, total := Run(context.Background(), &Env{}, checks, &out)
	if passed != 1 || total != 2 {
		t.Fatalf("passed=%d total=%d", passed, total)
	}
	s := out.String()
	for _, want := range []string{"PASS ok", "FAIL ko: boom", "RUNTIME: 1/2"} {
		if !strings.Contains(s, want) {
			t.Fatalf("salida %q sin %q", s, want)
		}
	}
}

func TestChecksM0IncluyeVersion(t *testing.T) {
	names := map[string]bool{}
	for _, c := range Checks() {
		names[c.Name] = true
	}
	if !names["version imprime lucidfence y la versión"] {
		t.Fatalf("checks=%v", names)
	}
}

func fakeBin(t *testing.T, script string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "lucidfence")
	if err := os.WriteFile(path, []byte("#!/bin/sh\n"+script+"\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestCheckVersionConBinarioFalso(t *testing.T) {
	ok := &Env{Bin: fakeBin(t, `echo "lucidfence 2.0.0-dev (unknown, go1.27.1, darwin/arm64)"`)}
	if err := checkVersion(context.Background(), ok); err != nil {
		t.Fatal(err)
	}
	bad := &Env{Bin: fakeBin(t, `echo "otra cosa"`)}
	if err := checkVersion(context.Background(), bad); err == nil {
		t.Fatal("salida inesperada debe fallar")
	}
	broken := &Env{Bin: fakeBin(t, `echo boom >&2; exit 1`)}
	if err := checkVersion(context.Background(), broken); err == nil {
		t.Fatal("exit 1 debe fallar")
	}
}
