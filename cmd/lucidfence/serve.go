package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

type netListenConfig struct{}

func (netListenConfig) listen(addr string) (net.Listener, error) { return net.Listen("tcp", addr) }

// serve arranca el servidor y el motor; termina cuando ctx se cancela.
func serve(ctx context.Context, f commonFlags, autostart bool, stdout, stderr io.Writer) int {
	logger := newLogger("info", stderr)
	a, err := buildApp(f, logger)
	if err != nil {
		_, _ = fmt.Fprintf(stderr, "lucidfence serve: %v\n", err)
		return 1
	}
	logger = newLogger(a.cfg.LogLevel, stderr)
	ln, err := netListenConfig{}.listen(a.cfg.Listen)
	if err != nil {
		_, _ = fmt.Fprintf(stderr, "lucidfence serve: no se puede escuchar en %s: %v\n", a.cfg.Listen, err)
		return 1
	}
	_, _ = fmt.Fprintf(stdout, "listening on http://%s\n", ln.Addr())
	_, _ = fmt.Fprintf(stdout, "modo=%s enforcement=observe datos=%s dashboard=%v\n", a.cfg.Mode, a.cfg.DataDir, a.engine != nil)
	if autostart {
		a.engine.Start(ctx)
	}
	srv := &http.Server{Handler: a.handler, ReadHeaderTimeout: 10 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 60 * time.Second, IdleTimeout: 2 * time.Minute}
	errCh := make(chan error, 1)
	go func() { errCh <- srv.Serve(ln) }()
	select {
	case <-ctx.Done():
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			_, _ = fmt.Fprintf(stderr, "lucidfence serve: %v\n", err)
			return 1
		}
	}
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Warn("apagado forzado", "error", err)
	}
	a.engine.Stop()
	_, _ = fmt.Fprintln(stdout, "parado")
	return 0
}

func runServe(args []string, stdout, stderr io.Writer) int {
	var noAutostart bool
	f, fs, err := parseCommon("serve", args, stderr, func(fs *flag.FlagSet) {
		fs.BoolVar(&noAutostart, "no-autostart", false, "no lanzar el ciclo periódico (solo API)")
	})
	if err != nil {
		return 2
	}
	if fs.NArg() > 0 {
		_, _ = fmt.Fprintf(stderr, "lucidfence serve: argumento inesperado %q\n", fs.Arg(0))
		return 2
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return serve(ctx, f, !noAutostart, stdout, stderr)
}
