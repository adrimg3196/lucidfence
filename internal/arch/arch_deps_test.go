// Tests de fronteras de dependencias: allowlists de Go y npm, y directivas
// de go.mod que se saltarían la allowlist (spec §5.8, §7.2). Separado de
// arch_test.go (límites físicos y cobertura de ARCHITECTURE.md) para que
// ningún fichero supere el límite de 400 líneas (spec §9.1).
package arch

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

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

// depguardFilesLineRe casa una línea "files: [...]" de una regla depguard en
// .golangci.yml (spec §5.2); depguardGlobItemRe extrae cada glob entrecomillado
// de esa lista.
var (
	depguardFilesLineRe = regexp.MustCompile(`files:\s*\[(.*)\]`)
	depguardGlobItemRe  = regexp.MustCompile(`"([^"]+)"`)
)

// depguardFileGlobs lee, línea a línea y sin depender de un parser YAML, cada
// glob "files" de las reglas depguard en golangciPath.
func depguardFileGlobs(golangciPath string) ([]string, error) {
	data, err := os.ReadFile(golangciPath)
	if err != nil {
		return nil, err
	}
	var globs []string
	for _, line := range strings.Split(string(data), "\n") {
		m := depguardFilesLineRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		for _, item := range depguardGlobItemRe.FindAllStringSubmatch(m[1], -1) {
			globs = append(globs, item[1])
		}
	}
	return globs, nil
}

// globCoversPackage decide si un glob "**/<dir>/**" de depguard cubre el
// paquete pkg (p.ej. "internal/arch"): cubre tanto el propio directorio como
// cualquier subpaquete suyo.
func globCoversPackage(glob, pkg string) bool {
	dir := strings.TrimSuffix(strings.TrimPrefix(glob, "**/"), "/**")
	return pkg == dir || strings.HasPrefix(pkg, dir+"/")
}

// internalPackages filtra goPackages a los que viven bajo internal/, que son
// los que depguard debe cubrir (cmd/* puede importar cualquier cosa).
func internalPackages(t *testing.T, root string) []string {
	t.Helper()
	var out []string
	for _, pkg := range goPackages(t, root) {
		if strings.HasPrefix(pkg, "internal/") {
			out = append(out, pkg)
		}
	}
	return out
}

func TestDepguardCubreTodosLosPaquetes(t *testing.T) {
	root := repoRoot(t)
	globs, err := depguardFileGlobs(filepath.Join(root, ".golangci.yml"))
	if err != nil {
		t.Fatal(err)
	}
	for _, pkg := range internalPackages(t, root) {
		covered := false
		for _, g := range globs {
			if globCoversPackage(g, pkg) {
				covered = true
				break
			}
		}
		if !covered {
			t.Errorf("%s no está cubierto por ninguna regla depguard en .golangci.yml (spec §5.2)", pkg)
		}
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
