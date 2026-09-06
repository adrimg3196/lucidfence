package arch

import (
	"bufio"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

const (
	maxGoLines  = 400
	maxTSXLines = 300
)

func repoRoot(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatal("no encuentro go.mod hacia arriba")
		}
		dir = parent
	}
}

func countLines(t *testing.T, path string) int {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = f.Close() }()
	n := 0
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 1024*1024)
	for sc.Scan() {
		n++
	}
	return n
}

func skipDir(name string) bool {
	return name == ".git" || name == "node_modules" || name == "dist" || name == "bin" || name == ".claude"
}

func firstLineAllows(t *testing.T, path string) bool {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = f.Close() }()
	sc := bufio.NewScanner(f)
	if sc.Scan() {
		return regexp.MustCompile(`limits:allow #\d+`).MatchString(sc.Text())
	}
	return false
}

func TestFileLimits(t *testing.T) {
	root := repoRoot(t)
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() && skipDir(d.Name()) {
			return filepath.SkipDir
		}
		if d.IsDir() {
			return nil
		}
		limit := 0
		switch {
		case strings.HasSuffix(path, ".go"):
			limit = maxGoLines
		case strings.HasSuffix(path, ".tsx"):
			limit = maxTSXLines
		default:
			return nil
		}
		if n := countLines(t, path); n > limit && !firstLineAllows(t, path) {
			t.Errorf("%s: %d líneas > %d (spec §9.1). Divide el fichero o añade `limits:allow #<issue>` en la primera línea", path, n, limit)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

func loadAllowlist(path string) (map[string]bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = f.Close() }()
	out := map[string]bool{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		out[line] = true
	}
	return out, sc.Err()
}

func readAllowlist(t *testing.T, path string) map[string]bool {
	t.Helper()
	out, err := loadAllowlist(path)
	if err != nil {
		t.Fatal(err)
	}
	return out
}

func writeTempFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func goPackages(t *testing.T, root string) []string {
	t.Helper()
	seen := map[string]bool{}
	var pkgs []string
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() && skipDir(d.Name()) {
			return filepath.SkipDir
		}
		if d.IsDir() || !strings.HasSuffix(path, ".go") {
			return nil
		}
		rel, _ := filepath.Rel(root, filepath.Dir(path))
		if (!strings.HasPrefix(rel, "internal") && !strings.HasPrefix(rel, "cmd")) || seen[rel] {
			return nil
		}
		seen[rel] = true
		pkgs = append(pkgs, filepath.ToSlash(rel))
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return pkgs
}

func TestArchitectureDocListsEveryPackage(t *testing.T) {
	root := repoRoot(t)
	doc, err := os.ReadFile(filepath.Join(root, "ARCHITECTURE.md"))
	if err != nil {
		t.Fatalf("ARCHITECTURE.md obligatorio (spec §9.2): %v", err)
	}
	for _, pkg := range goPackages(t, root) {
		if !strings.Contains(string(doc), "`"+pkg+"`") {
			t.Errorf("el paquete %s no aparece en ARCHITECTURE.md; documenta su responsabilidad", pkg)
		}
	}
}
