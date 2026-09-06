package store

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"sync"
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

func TestOrgDevuelveLaMismaInstancia(t *testing.T) {
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	o1, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	o2, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	if o1 != o2 {
		t.Fatal("Org debería devolver la misma instancia para el mismo id")
	}
	o3, err := s.Org("otra")
	if err != nil {
		t.Fatal(err)
	}
	if o1 == o3 {
		t.Fatal("Org debería devolver instancias distintas para ids distintos")
	}
}

func TestOrgConcurrenteNoDuplica(t *testing.T) {
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	const n = 20
	results := make([]*OrgStore, n)
	errs := make([]error, n)
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func(i int) {
			defer wg.Done()
			results[i], errs[i] = s.Org("default")
		}(i)
	}
	wg.Wait()
	for i, err := range errs {
		if err != nil {
			t.Fatalf("goroutine %d: %v", i, err)
		}
	}
	for i := 1; i < n; i++ {
		if results[i] != results[0] {
			t.Fatalf("goroutine %d obtuvo una instancia distinta de OrgStore", i)
		}
	}
}

func TestOpenFallaSiLaRaizEsUnFichero(t *testing.T) {
	root := filepath.Join(t.TempDir(), "no-es-un-dir")
	if err := os.WriteFile(root, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(root); err == nil {
		t.Fatal("Open debería fallar si la raíz es un fichero regular")
	}
}

func TestReadJSONMalformado(t *testing.T) {
	path := filepath.Join(t.TempDir(), "x.json")
	if err := os.WriteFile(path, []byte("{"), 0o600); err != nil {
		t.Fatal(err)
	}
	var got map[string]int
	err := ReadJSON(path, &got)
	if err == nil || errors.Is(err, ErrNotFound) {
		t.Fatalf("esperaba error de parseo distinto de ErrNotFound, got %v", err)
	}
}

func TestAppendJSONLSinDirectorio(t *testing.T) {
	path := filepath.Join(t.TempDir(), "no-existe", "e.jsonl")
	if err := AppendJSONL(path, map[string]int{"n": 1}); err == nil {
		t.Fatal("AppendJSONL debería fallar si el directorio padre no existe")
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
