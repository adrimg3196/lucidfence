// Package battery es la batería runtime de LucidFence: cada claim de producto
// se ejecuta contra el binario real (spec §9.1 paso 5). CI la corre; el
// resultado es RUNTIME: N/N.
package battery

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"strings"
)

// Env es el entorno compartido por los checks.
type Env struct {
	Bin     string       // ruta al binario lucidfence compilado
	Tmp     string       // directorio temporal para datos
	BaseURL string       // http://127.0.0.1:<port> cuando hay servidor
	Client  *http.Client // con cookie jar; lo rellena StartServer
	CSRF    string       // token CSRF de la sesión abierta por el check de setup
	stop    func()
}

// Check es un claim verificable.
type Check struct {
	Name string
	Run  func(ctx context.Context, env *Env) error
}

// Run ejecuta los checks en orden e imprime el tally.
func Run(ctx context.Context, env *Env, checks []Check, w io.Writer) (passed, total int) {
	for _, c := range checks {
		total++
		if err := c.Run(ctx, env); err != nil {
			_, _ = fmt.Fprintf(w, "FAIL %s: %v\n", c.Name, err)
			continue
		}
		passed++
		_, _ = fmt.Fprintf(w, "PASS %s\n", c.Name)
	}
	_, _ = fmt.Fprintf(w, "RUNTIME: %d/%d\n", passed, total)
	return passed, total
}

// Checks devuelve todos los checks registrados, en orden.
func Checks() []Check {
	return append(checksM0(), checksM1()...)
}

func runBin(ctx context.Context, env *Env, args ...string) (string, error) {
	out, err := exec.CommandContext(ctx, env.Bin, args...).CombinedOutput()
	return strings.TrimSpace(string(out)), err
}
