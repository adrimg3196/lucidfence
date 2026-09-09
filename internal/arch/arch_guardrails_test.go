package arch

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// escrituraDryRun casa con una asignación al campo DryRun de un action.Result
// (`res.DryRun = …`), que es la marca de "aquí se decide si una orden sale en
// vivo". No casa con un literal (`action.Result{DryRun: true}`), que es lo que
// construyen los conectores y los tests, ni con una comparación (`==`, `!=`).
var escrituraDryRun = regexp.MustCompile(`\.DryRun\s*=[^=]`)

// TestSoloLosGuardarrailesFijanDryRun cierra por raíl lo que dicen la spec
// §5.4 ("los guardarraíles viven exclusivamente en engine/guardrails.go"), las
// restricciones del hito y el bloque de CODEOWNERS: dentro de internal/engine,
// el único código de producción que sella el dry_run del resultado auditado
// vive en un fichero guardrails*, que es el que exige aprobación del
// propietario (spec §9.2).
func TestSoloLosGuardarrailesFijanDryRun(t *testing.T) {
	dir := filepath.Join(repoRoot(t), "internal", "engine")
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	sellos := 0
	for _, entry := range entries {
		name := entry.Name()
		if entry.IsDir() || !strings.HasSuffix(name, ".go") || strings.HasSuffix(name, "_test.go") {
			continue
		}
		source, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			t.Fatal(err)
		}
		if !escrituraDryRun.Match(source) {
			continue
		}
		sellos++
		if !strings.HasPrefix(name, "guardrails") {
			t.Errorf("%s fija dry_run fuera de los guardarraíles: esa decisión va en internal/engine/guardrails*.go, que es lo que protege CODEOWNERS (spec §5.4 y §9.2)", name)
		}
	}
	if sellos == 0 {
		t.Fatal("nadie sella dry_run en internal/engine: el raíl estaría vigilando un invariante que ya no existe")
	}
}
