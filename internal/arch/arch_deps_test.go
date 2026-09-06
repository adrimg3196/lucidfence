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

// npmOverrideAliasTarget resuelve el destino real de una entrada del bloque
// overrides (spec §7.2, ruling M1-R27 C17): un alias explícito
// "npm:<pkg>@<versión>" se resuelve igual que en dependencies/devDependencies
// (npmAliasTarget); un alias "$<pkg>" reutiliza, por semántica de npm, la
// versión ya declarada para <pkg> en el resto del manifest — si esa versión
// es a su vez un alias, se resuelve igual.
func npmOverrideAliasTarget(key, version string, rootDeps map[string]string) string {
	if name, ok := strings.CutPrefix(version, "$"); ok {
		if v, ok := rootDeps[name]; ok {
			return npmAliasTarget(name, v)
		}
		return name + " (alias sin declarar)"
	}
	return npmAliasTarget(key, version)
}

// npmOverridesViolations recorre, recursivamente, el bloque overrides (puede
// anidar objetos para redirigir la dependencia de una dependencia) y exige
// que tanto cada clave de override como cada destino resuelto estén en
// allowed: overrides puede sustituir un paquete transitivo entero sin tocar
// dependencies ni devDependencies (ruling M1-R27, C17).
func npmOverridesViolations(overrides map[string]json.RawMessage, prefix string, rootDeps map[string]string, allowed map[string]bool) []string {
	var violations []string
	for key, raw := range overrides {
		path := key
		if prefix != "" {
			path = prefix + "." + key
		}
		if !allowed[key] {
			violations = append(violations, fmt.Sprintf("overrides.%s -> %s", path, key))
		}

		var version string
		if err := json.Unmarshal(raw, &version); err == nil {
			if target := npmOverrideAliasTarget(key, version, rootDeps); target != key && !allowed[target] {
				violations = append(violations, fmt.Sprintf("overrides.%s -> %s", path, target))
			}
			continue
		}

		var nested map[string]json.RawMessage
		if err := json.Unmarshal(raw, &nested); err == nil {
			violations = append(violations, npmOverridesViolations(nested, path, rootDeps, allowed)...)
		}
	}
	return violations
}

// npmAllowlistViolations lista, como "clave -> destino real", cada
// dependencia (incluidas overrides, resolutions, optionalDependencies y
// peerDependencies) de pkgPath cuyo destino resuelto no está en
// allowlistPath.
func npmAllowlistViolations(pkgPath, allowlistPath string) ([]string, error) {
	data, err := os.ReadFile(pkgPath)
	if err != nil {
		return nil, err
	}
	var pkg struct {
		Dependencies         map[string]string          `json:"dependencies"`
		DevDependencies      map[string]string          `json:"devDependencies"`
		OptionalDependencies map[string]string          `json:"optionalDependencies"`
		PeerDependencies     map[string]string          `json:"peerDependencies"`
		Resolutions          map[string]string          `json:"resolutions"`
		Overrides            map[string]json.RawMessage `json:"overrides"`
	}
	if err := json.Unmarshal(data, &pkg); err != nil {
		return nil, err
	}
	allowed, err := loadAllowlist(allowlistPath)
	if err != nil {
		return nil, err
	}
	var violations []string
	for _, deps := range []map[string]string{
		pkg.Dependencies, pkg.DevDependencies, pkg.OptionalDependencies, pkg.PeerDependencies, pkg.Resolutions,
	} {
		for name, version := range deps {
			target := npmAliasTarget(name, version)
			if !allowed[target] {
				violations = append(violations, fmt.Sprintf("%s -> %s", name, target))
			}
		}
	}

	rootDeps := map[string]string{}
	for _, deps := range []map[string]string{pkg.Dependencies, pkg.DevDependencies, pkg.OptionalDependencies, pkg.PeerDependencies} {
		for name, version := range deps {
			rootDeps[name] = version
		}
	}
	violations = append(violations, npmOverridesViolations(pkg.Overrides, "", rootDeps, allowed)...)

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

// TestNpmAllowlistDetectaOverridesAnidados fija la ruling M1-R27 (C17): el
// bloque overrides (anidado, con alias "npm:pkg@ver" y "$alias") puede
// redirigir un paquete transitivo entero sin tocar dependencies ni
// devDependencies, así que la allowlist debe vigilarlo igual que a un alias
// directo.
func TestNpmAllowlistDetectaOverridesAnidados(t *testing.T) {
	root := repoRoot(t)
	allowlistPath := filepath.Join(root, "internal/arch/allowlist_npm.txt")

	malicious := filepath.Join(t.TempDir(), "package.json")
	writeTempFile(t, malicious, `{
		"devDependencies": {"typescript": "npm:@typescript/typescript6@6.0.2"},
		"overrides": {"openapi-typescript": {"typescript": "npm:paquete-malicioso@1.0.0"}}
	}`)
	violations, err := npmAllowlistViolations(malicious, allowlistPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(violations) == 0 {
		t.Fatal("un override anidado hacia un paquete no listado debería fallar la allowlist")
	}

	// El override real de web/package.json: reenvía "typescript" (una
	// dependencia de openapi-typescript) al "typescript" ya declarado en
	// devDependencies mediante el alias "$typescript" (spec §7.2, permitido).
	legit := filepath.Join(t.TempDir(), "package.json")
	writeTempFile(t, legit, `{
		"devDependencies": {"typescript": "npm:@typescript/typescript6@6.0.2"},
		"overrides": {"openapi-typescript": {"typescript": "$typescript"}}
	}`)
	violations, err = npmAllowlistViolations(legit, allowlistPath)
	if err != nil {
		t.Fatal(err)
	}
	if len(violations) != 0 {
		t.Fatalf("el override openapi-typescript.typescript=$typescript ya permitido no debería fallar: %v", violations)
	}
}
