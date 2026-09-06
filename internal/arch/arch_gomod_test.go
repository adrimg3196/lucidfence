// Tests de la allowlist de dependencias Go y de las directivas de go.mod
// que se la saltarían (spec §5.8). Separado de arch_deps_test.go (allowlist
// npm y cobertura depguard) para que ningún fichero supere el límite de 400
// líneas (spec §9.1).
//
// Ruling M1-R13: la allowlist gobierna los módulos directos; los
// transitivos deben ser alcanzables desde un módulo permitido en go mod
// graph.
package arch

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
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

// goModDirectRequireRe detecta cada línea "require <módulo> <versión>" de
// go.mod, tanto en forma de una línea ("require mod v1.2.3") como dentro de
// un bloque require ("\tmod v1.2.3"), capturando además si termina en el
// comentario "// indirect" que "go mod tidy" mantiene para las dependencias
// transitivas (ruling M1-R13, punto 2).
var goModDirectRequireRe = regexp.MustCompile(`(?m)^\s*(?:require\s+)?([\w./-]+)\s+v[0-9][^\s]*(\s*//\s*indirect\b)?`)

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

// goModDirectRequires devuelve los módulos que gomod declara con "require" y
// que NO llevan el comentario "// indirect": son los módulos directos que la
// ruling M1-R13 exige tener en internal/arch/allowlist_go.txt.
func goModDirectRequires(gomod string) []string {
	var mods []string
	for _, m := range goModDirectRequireRe.FindAllStringSubmatch(gomod, -1) {
		if strings.TrimSpace(m[2]) != "" {
			continue // marcado "// indirect": no es un módulo directo.
		}
		mods = append(mods, m[1])
	}
	return mods
}

// modulePathOf recorta el sufijo "@versión" de un nodo de "go mod graph"
// (p.ej. "golang.org/x/crypto@v0.56.0" -> "golang.org/x/crypto").
func modulePathOf(node string) string {
	if i := strings.LastIndex(node, "@"); i >= 0 {
		return node[:i]
	}
	return node
}

// goModGraphEdges parsea la salida de "go mod graph" (líneas "A@v B@v") en
// un mapa de adyacencia por ruta de módulo (sin versión) y el conjunto de
// todas las rutas que aparecen en el grafo, como origen o como destino.
func goModGraphEdges(graph string) (edges map[string][]string, nodes map[string]bool) {
	edges = map[string][]string{}
	nodes = map[string]bool{}
	for _, line := range strings.Split(graph, "\n") {
		fields := strings.Fields(line)
		if len(fields) != 2 {
			continue
		}
		from, to := modulePathOf(fields[0]), modulePathOf(fields[1])
		edges[from] = append(edges[from], to)
		nodes[from] = true
		nodes[to] = true
	}
	return edges, nodes
}

// goAllowlistViolations implementa la ruling M1-R13: la allowlist gobierna
// los módulos directos (los "require" de go.mod sin "// indirect"); los
// módulos transitivos no necesitan estar en la allowlist siempre que sean
// alcanzables, en "go mod graph", partiendo de algún módulo permitido. Es
// lógica pura (sin exec.Command ni acceso a disco) para poder testearla con
// fixtures deterministas además de con la salida real de "go" (spec §5.8).
func goAllowlistViolations(allowed map[string]bool, gomod, graph string, all []string) []string {
	var violations []string

	for _, mod := range goModDirectRequires(gomod) {
		if !allowed[mod] {
			violations = append(violations, fmt.Sprintf(
				"go.mod requiere directamente %q, que no está en internal/arch/allowlist_go.txt (spec §5.8, ruling M1-R13)", mod))
		}
	}

	edges, nodes := goModGraphEdges(graph)
	reachable := map[string]bool{}
	var queue []string
	for mod := range allowed {
		if nodes[mod] {
			reachable[mod] = true
			queue = append(queue, mod)
		}
	}
	for len(queue) > 0 {
		cur := queue[0]
		queue = queue[1:]
		for _, next := range edges[cur] {
			if !reachable[next] {
				reachable[next] = true
				queue = append(queue, next)
			}
		}
	}

	for _, mod := range all {
		if !reachable[mod] {
			violations = append(violations, fmt.Sprintf(
				"%q (go list -m all) no es alcanzable desde ningún módulo de internal/arch/allowlist_go.txt en go mod graph (ruling M1-R13)", mod))
		}
	}

	return violations
}

// goModule es el subconjunto de "go list -m -json" que necesitamos: su ruta
// y si es el módulo principal del repo, que no se compara ni con la
// allowlist ni con el grafo.
type goModule struct {
	Path string
	Main bool
}

// goListAllJSON ejecuta "go list -m -json all" desde root y devuelve las
// rutas de todos los módulos salvo el módulo principal (ruling M1-R13,
// punto 3).
func goListAllJSON(t *testing.T, root string) []string {
	t.Helper()
	cmd := exec.Command("go", "list", "-m", "-json", "all")
	cmd.Dir = root
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("go list -m -json all: %v", err)
	}
	dec := json.NewDecoder(strings.NewReader(string(out)))
	var mods []string
	for {
		var m goModule
		if err := dec.Decode(&m); err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			t.Fatalf("decodificando go list -m -json all: %v", err)
		}
		if !m.Main {
			mods = append(mods, m.Path)
		}
	}
	return mods
}

// goModGraph ejecuta "go mod graph" desde root y devuelve su salida cruda.
func goModGraph(t *testing.T, root string) string {
	t.Helper()
	cmd := exec.Command("go", "mod", "graph")
	cmd.Dir = root
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("go mod graph: %v", err)
	}
	return string(out)
}

// TestGoDependencyAllowlist aplica la ruling M1-R13: la allowlist gobierna
// los módulos directos; los transitivos deben ser alcanzables desde un
// módulo permitido en go mod graph.
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

	gomod, err := os.ReadFile(goModPath)
	if err != nil {
		t.Fatal(err)
	}

	graph := goModGraph(t, root)
	all := goListAllJSON(t, root)
	for _, v := range goAllowlistViolations(allowed, string(gomod), graph, all) {
		t.Error(v)
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

	data, err := os.ReadFile(modPath)
	if err != nil {
		t.Fatal(err)
	}
	mods := goModDirectRequires(string(data))
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

// TestGoAllowlistTransitivosYIndirectColado fija con fixtures la ruling
// M1-R13: un módulo transitivo (golang.org/x/sys, golang.org/x/net) no
// necesita estar en la allowlist si "go mod graph" lo cuelga de un módulo
// permitido (golang.org/x/crypto), pero un "require ... // indirect" colado
// a mano que solo cuelga del módulo principal (evil.example/x) sigue siendo
// un fallo porque no es alcanzable desde ninguna raíz permitida.
func TestGoAllowlistTransitivosYIndirectColado(t *testing.T) {
	allowed := map[string]bool{"golang.org/x/crypto": true}
	gomod := `module github.com/adrimg3196/lucidfence

go 1.27

require golang.org/x/crypto v0.56.0

require (
	golang.org/x/sys v0.39.0 // indirect
	evil.example/x v1.0.0 // indirect
)
`
	graph := strings.Join([]string{
		"github.com/adrimg3196/lucidfence golang.org/x/crypto@v0.56.0",
		"golang.org/x/crypto@v0.56.0 golang.org/x/sys@v0.39.0",
		"golang.org/x/crypto@v0.56.0 golang.org/x/net@v0.51.0",
		"github.com/adrimg3196/lucidfence evil.example/x@v1.0.0",
	}, "\n")
	all := []string{"golang.org/x/crypto", "golang.org/x/sys", "golang.org/x/net", "evil.example/x"}

	violations := goAllowlistViolations(allowed, gomod, graph, all)
	joined := strings.Join(violations, "\n")

	for _, transitive := range []string{"golang.org/x/sys", "golang.org/x/net"} {
		if strings.Contains(joined, transitive) {
			t.Errorf("%s es alcanzable desde golang.org/x/crypto en go mod graph; no debería reportarse: %v", transitive, violations)
		}
	}
	if !strings.Contains(joined, "evil.example/x") {
		t.Fatalf("evil.example/x solo cuelga del módulo principal (no de un módulo permitido) y debería reportarse; violations=%v", violations)
	}
}
