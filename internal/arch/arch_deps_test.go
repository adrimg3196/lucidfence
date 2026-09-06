// Tests de fronteras de dependencias: allowlist de npm (spec §7.2) y
// cobertura de depguard sobre los paquetes internos (spec §5.2). La
// allowlist de Go y la ruling M1-R13 viven en arch_gomod_test.go, y los
// límites físicos y la cobertura de ARCHITECTURE.md en arch_test.go, para
// que ningún fichero supere el límite de 400 líneas (spec §9.1).
package arch

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

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
