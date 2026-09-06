package main

import (
	"fmt"
	"io"
	"os/exec"
	"runtime"
	"time"
)

// browserOpener abre una URL en el navegador del sistema; los tests lo sustituyen.
var browserOpener = func(url string) error {
	switch runtime.GOOS {
	case "darwin":
		return exec.Command("open", url).Start()
	case "windows":
		return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	default:
		return exec.Command("xdg-open", url).Start()
	}
}

func runOpen(args []string, stdout, stderr io.Writer) int {
	f, fs, err := parseCommon("open", args, stderr, nil)
	if err != nil {
		return 2
	}
	if fs.NArg() > 0 {
		_, _ = fmt.Fprintf(stderr, "lucidfence open: argumento inesperado %q\n", fs.Arg(0))
		return 2
	}
	cfg, err := loadConfig(f)
	if err != nil {
		_, _ = fmt.Fprintf(stderr, "lucidfence open: %v\n", err)
		return 1
	}
	url := "http://" + dialAddr(cfg.Listen) + "/"
	if !healthy(cfg.Listen, 2*time.Second) {
		_, _ = fmt.Fprintf(stderr, "lucidfence open: el servidor no responde en %s; arranca con `lucidfence serve`\n", url)
		return 1
	}
	if err := browserOpener(url); err != nil {
		_, _ = fmt.Fprintf(stderr, "lucidfence open: no se pudo abrir el navegador: %v\nabre %s manualmente\n", err, url)
		return 1
	}
	_, _ = fmt.Fprintf(stdout, "abriendo %s\n", url)
	return 0
}
