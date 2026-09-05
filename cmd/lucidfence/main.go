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
  version   imprime la versión del binario
`

type command func(args []string, stdout, stderr io.Writer) int

func commands() map[string]command {
	return map[string]command{
		"version": runVersion,
	}
}

func run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return 2
	}
	cmd, ok := commands()[args[0]]
	if !ok {
		fmt.Fprintf(stderr, "subcomando desconocido %q\n\n%s", args[0], usage)
		return 2
	}
	return cmd(args[1:], stdout, stderr)
}

func runVersion(_ []string, stdout, _ io.Writer) int {
	fmt.Fprintln(stdout, version.String())
	return 0
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}
