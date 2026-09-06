package store

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestOpenCreaDirectorios0700(t *testing.T) {
	root := filepath.Join(t.TempDir(), "data")
	s, err := Open(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, d := range []string{"orgs", "auth", "secrets", "cache"} {
		info, err := os.Stat(filepath.Join(root, d))
		if err != nil {
			t.Fatal(err)
		}
		if runtime.GOOS != "windows" && info.Mode().Perm() != 0o700 {
			t.Fatalf("%s: permisos %o", d, info.Mode().Perm())
		}
	}
	if s.Root() != root || s.AuthDir() != filepath.Join(root, "auth") || s.CacheDir() != filepath.Join(root, "cache") {
		t.Fatal("rutas")
	}
}

func TestOrgValidaIDYCreaDir(t *testing.T) {
	s, _ := Open(t.TempDir())
	for _, bad := range []string{"", "Default", "a b", "../x", "x/y"} {
		if _, err := s.Org(bad); err == nil {
			t.Fatalf("org %q debería fallar", bad)
		}
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	if o.ID() != "default" || o.Dir() != filepath.Join(s.Root(), "orgs", "default") || o.Path("fences.json") != filepath.Join(o.Dir(), "fences.json") {
		t.Fatal("rutas de org")
	}
}

func TestWriteJSONAtomicoYReadJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "x.json")
	var got map[string]int
	if err := ReadJSON(path, &got); !errors.Is(err, ErrNotFound) {
		t.Fatalf("esperaba ErrNotFound, got %v", err)
	}
	if err := WriteJSON(path, map[string]int{"a": 1}); err != nil {
		t.Fatal(err)
	}
	if err := ReadJSON(path, &got); err != nil || got["a"] != 1 {
		t.Fatalf("round-trip: %v %v", err, got)
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 {
		t.Fatalf("no deben quedar temporales: %v", entries)
	}
	if runtime.GOOS != "windows" {
		info, _ := os.Stat(path)
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("permisos %o", info.Mode().Perm())
		}
	}
	// Un valor no serializable no debe tocar el fichero existente.
	if err := WriteJSON(path, make(chan int)); err == nil {
		t.Fatal("esperaba error de serialización")
	}
	if err := ReadJSON(path, &got); err != nil || got["a"] != 1 {
		t.Fatal("el fichero previo debe seguir intacto")
	}
}

func TestJSONLAppendYUltimasN(t *testing.T) {
	path := filepath.Join(t.TempDir(), "e.jsonl")
	if lines, err := ReadJSONL(path, 10); err != nil || len(lines) != 0 {
		t.Fatalf("fichero ausente: %v %v", err, lines)
	}
	for i := 1; i <= 5; i++ {
		if err := AppendJSONL(path, map[string]int{"n": i}); err != nil {
			t.Fatal(err)
		}
	}
	lines, err := ReadJSONL(path, 2)
	if err != nil || len(lines) != 2 || string(lines[0]) != `{"n":4}` || string(lines[1]) != `{"n":5}` {
		t.Fatalf("últimas 2: %v %s", err, lines)
	}
	all, _ := ReadJSONL(path, 0)
	if len(all) != 5 {
		t.Fatalf("todas: %d", len(all))
	}
}
