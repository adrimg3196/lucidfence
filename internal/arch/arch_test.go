package arch

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
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

// goModDirectiveRe detecta una línea "replace" o "exclude", en forma de una
// línea o de apertura de bloque ("replace (" / "exclude ("): ninguna de las
// dos se gestiona con la allowlist (spec §5.8), así que su sola presencia es
// un fallo.
var goModDirectiveRe = regexp.MustCompile(`(?m)^\s*(replace|exclude)\s+\S`)

// goModRequireLineRe es el regex adicional del brief C2 para cazar un
// require de una línea ("require mod v1.2.3") o una línea de un bloque
// require ("\tmod v1.2.3"), en paralelo a "go list -m all".
var goModRequireLineRe = regexp.MustCompile(`(?m)^\s*(?:require\s+)?([\w./-]+)\s+v[0-9][^\s]*`)

// goModDirectives devuelve, en orden, cada directiva "replace"/"exclude"
// encontrada en el go.mod de modPath.
func goModDirectives(modPath string) ([]string, error) {
	data, err := os.ReadFile(modPath)
	if err != nil {
		return nil, err
	}
	var found []string
	for _, m := range goModDirectiveRe.FindAllStringSubmatch(string(data), -1) {
		found = append(found, m[1])
	}
	return found, nil
}

// goModRequireLines devuelve los módulos que goModRequireLineRe encuentra en
// el go.mod de modPath.
func goModRequireLines(modPath string) ([]string, error) {
	data, err := os.ReadFile(modPath)
	if err != nil {
		return nil, err
	}
	var mods []string
	for _, m := range goModRequireLineRe.FindAllStringSubmatch(string(data), -1) {
		mods = append(mods, m[1])
	}
	return mods, nil
}

// goListModules ejecuta "go list -m -f {{.Path}} all" desde root y devuelve
// las rutas de módulo que no son el propio módulo del repo.
func goListModules(t *testing.T, root string) []string {
	t.Helper()
	self := goList(t, root, "-f", "{{.Path}}")
	out := goList(t, root, "-f", "{{.Path}}", "all")
	var mods []string
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || line == self {
			continue
		}
		mods = append(mods, line)
	}
	return mods
}

// goList ejecuta "go list -m <args...>" desde root y devuelve su salida.
func goList(t *testing.T, root string, args ...string) string {
	t.Helper()
	cmd := exec.Command("go", append([]string{"list", "-m"}, args...)...)
	cmd.Dir = root
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("go list -m %v: %v", args, err)
	}
	return strings.TrimSpace(string(out))
}

func TestGoDependencyAllowlist(t *testing.T) {
	root := repoRoot(t)
	allowed := readAllowlist(t, filepath.Join(root, "internal/arch/allowlist_go.txt"))
	goModPath := filepath.Join(root, "go.mod")

	directives, err := goModDirectives(goModPath)
	if err != nil {
		t.Fatal(err)
	}
	for _, d := range directives {
		t.Errorf("go.mod contiene una directiva %q; las dependencias solo se gestionan con require + allowlist (spec §5.8)", d)
	}

	for _, mod := range goListModules(t, root) {
		if !allowed[mod] {
			t.Errorf("go.mod requiere (go list) %q, que no está en internal/arch/allowlist_go.txt (spec §5.8)", mod)
		}
	}

	reqs, err := goModRequireLines(goModPath)
	if err != nil {
		t.Fatal(err)
	}
	for _, mod := range reqs {
		if !allowed[mod] {
			t.Errorf("go.mod requiere (línea) %q, que no está en internal/arch/allowlist_go.txt (spec §5.8)", mod)
		}
	}
}

func TestGoAllowlistDetectaRequireDeUnaLineaYReplace(t *testing.T) {
	modPath := filepath.Join(t.TempDir(), "go.mod")
	writeTempFile(t, modPath, `module example.com/temp

go 1.27

require example.com/onelineref v1.2.3

replace example.com/onelineref => example.com/fork v1.2.3
`)

	directives, err := goModDirectives(modPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(directives) == 0 {
		t.Fatal("un go.mod con replace debería detectarse como directiva prohibida")
	}

	mods, err := goModRequireLines(modPath)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, m := range mods {
		if m == "example.com/onelineref" {
			found = true
		}
	}
	if !found {
		t.Fatalf("el require de una línea debería detectarse, mods=%v", mods)
	}
}

// npmAliasTarget resuelve el paquete real al que apunta una dependencia de
// package.json cuando su versión es un alias (spec §7.2): "npm:<nombre>@<v>"
// apunta a <nombre>; "git+", "file:", "http" y "github:" no tienen un nombre
// real verificable, así que se etiquetan con la clave + " (alias)" para que
// nunca casen por accidente con una entrada legítima de la allowlist.
func npmAliasTarget(name, version string) string {
	if rest, ok := strings.CutPrefix(version, "npm:"); ok {
		if i := strings.LastIndex(rest, "@"); i > 0 {
			return rest[:i]
		}
		return rest
	}
	for _, prefix := range []string{"git+", "file:", "http", "github:"} {
		if strings.HasPrefix(version, prefix) {
			return name + " (alias)"
		}
	}
	return name
}

// npmAllowlistViolations lista, como "clave -> destino real", cada
// dependencia de pkgPath cuyo destino resuelto no está en allowlistPath.
func npmAllowlistViolations(pkgPath, allowlistPath string) ([]string, error) {
	data, err := os.ReadFile(pkgPath)
	if err != nil {
		return nil, err
	}
	var pkg struct {
		Dependencies    map[string]string `json:"dependencies"`
		DevDependencies map[string]string `json:"devDependencies"`
	}
	if err := json.Unmarshal(data, &pkg); err != nil {
		return nil, err
	}
	allowed, err := loadAllowlist(allowlistPath)
	if err != nil {
		return nil, err
	}
	var violations []string
	for _, deps := range []map[string]string{pkg.Dependencies, pkg.DevDependencies} {
		for name, version := range deps {
			target := npmAliasTarget(name, version)
			if !allowed[target] {
				violations = append(violations, fmt.Sprintf("%s -> %s", name, target))
			}
		}
	}
	return violations, nil
}

func TestNpmDependencyAllowlist(t *testing.T) {
	root := repoRoot(t)
	pkgPath := filepath.Join(root, "web/package.json")
	if _, err := os.Stat(pkgPath); err != nil {
		t.Skipf("web/package.json no existe todavía: %v", err)
	}
	violations, err := npmAllowlistViolations(pkgPath, filepath.Join(root, "internal/arch/allowlist_npm.txt"))
	if err != nil {
		t.Fatal(err)
	}
	for _, v := range violations {
		t.Errorf("web/package.json depende de %s, que no está en internal/arch/allowlist_npm.txt (spec §7.2)", v)
	}
}

func TestNpmAllowlistDetectaAlias(t *testing.T) {
	root := repoRoot(t)
	allowlistPath := filepath.Join(root, "internal/arch/allowlist_npm.txt")

	malicious := filepath.Join(t.TempDir(), "package.json")
	writeTempFile(t, malicious, `{"dependencies":{"react":"npm:paquete-malicioso@1.0.0"}}`)
	violations, err := npmAllowlistViolations(malicious, allowlistPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(violations) == 0 {
		t.Fatal("un alias npm: hacia un paquete no listado debería fallar la allowlist")
	}

	legit := filepath.Join(t.TempDir(), "package.json")
	writeTempFile(t, legit, `{"dependencies":{"@typescript/native":"npm:typescript@7.0.2"}}`)
	violations, err = npmAllowlistViolations(legit, allowlistPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(violations) != 0 {
		t.Fatalf("un alias npm: hacia un paquete ya permitido no debería fallar: %v", violations)
	}
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
