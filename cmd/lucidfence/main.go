// Command lucidfence es el binario único de LucidFence 2.0: servidor,
// dashboard, CLI y MCP. main() solo despacha subcomandos; la lógica vive en
// internal/.
package main

import (
	"fmt"
	"io"
	"os"

	"github.com/adrimg3196/lucidfence/internal/version"
)

const usage = `uso: lucidfence <subcomando> [opciones]

subcomandos:
  serve     arranca el servidor y el dashboard (127.0.0.1:8765 por defecto)
  doctor    diagnostica la instalación local
  open      abre el dashboard en el navegador si el servidor responde
  version   imprime la versión del binario

opciones comunes: -config config.json  -data <dir>  -listen host:puerto
`

type command func(args []string, stdout, stderr io.Writer) int

func commands() map[string]command {
	return map[string]command{
		"version": runVersion,
		"serve":   runServe,
		"doctor":  runDoctor,
		"open":    runOpen,
	}
}

func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		_, _ = fmt.Fprint(stderr, usage)
		return 2
	}
	cmd, ok := commands()[args[0]]
	if !ok {
		_, _ = fmt.Fprintf(stderr, "subcomando desconocido %q\n\n%s", args[0], usage)
		return 2
	}
	return cmd(args[1:], stdout, stderr)
}

func runVersion(_ []string, stdout, _ io.Writer) int {
	_, _ = fmt.Fprintln(stdout, version.String())
	return 0
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}
