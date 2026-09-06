package battery

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var listenRe = regexp.MustCompile(`listening on (http://127\.0\.0\.1:\d+)`)

// lastLines devuelve como mucho las últimas n líneas de s, para adjuntar el
// final del stderr capturado a un error de apagado sin volcarlo entero.
func lastLines(s string, n int) string {
	lines := strings.Split(strings.TrimRight(s, "\n"), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}

// StartServer lanza el binario en un puerto libre con datos temporales.
func (env *Env) StartServer(ctx context.Context) error {
	dataDir := filepath.Join(env.Tmp, "data")
	cmd := exec.CommandContext(ctx, env.Bin, "serve", "-data", dataDir, "-config", filepath.Join(env.Tmp, "config.json"), "-listen", "127.0.0.1:0")
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		return err
	}
	env.stop = func() error {
		_ = cmd.Process.Signal(os.Interrupt)
		done := make(chan error, 1)
		go func() { done <- cmd.Wait() }()
		select {
		case waitErr := <-done:
			if waitErr != nil {
				return fmt.Errorf("%w; stderr:\n%s", waitErr, lastLines(stderr.String(), 20))
			}
			return nil
		case <-time.After(10 * time.Second):
			_ = cmd.Process.Kill()
			return fmt.Errorf("el servidor no atendió SIGINT en 10 s; se mató a la fuerza")
		}
	}
	lines := make(chan string, 1)
	go func() {
		sc := bufio.NewScanner(stdout)
		for sc.Scan() {
			if m := listenRe.FindStringSubmatch(sc.Text()); m != nil {
				lines <- m[1]
				break
			}
		}
		_, _ = io.Copy(io.Discard, stdout)
	}()
	select {
	case url := <-lines:
		env.BaseURL = url
	case <-time.After(15 * time.Second):
		_ = env.StopServer()
		return fmt.Errorf("el servidor no imprimió su dirección en 15 s; stderr: %s", stderr.String())
	case <-ctx.Done():
		return ctx.Err()
	}
	jar, _ := cookiejar.New(nil)
	env.Client = &http.Client{Jar: jar, Timeout: 30 * time.Second}
	return nil
}

// StopServer para el binario (SIGINT, kill a los 10 s) y devuelve el error
// de apagado: nil si el proceso salió limpio, o el motivo si hubo que
// matarlo a la fuerza o salió con estado distinto de 0. Idempotente: una
// llamada tras la primera no vuelve a invocar el cierre y devuelve nil.
func (env *Env) StopServer() error {
	if env.stop == nil {
		return nil
	}
	err := env.stop()
	env.stop = nil
	return err
}

func (env *Env) do(ctx context.Context, method, path string, body, out any) (int, error) {
	if env.Client == nil {
		return 0, errors.New("servidor no arrancado")
	}
	var buf bytes.Buffer
	if body != nil {
		_ = json.NewEncoder(&buf).Encode(body)
	}
	req, err := http.NewRequestWithContext(ctx, method, env.BaseURL+path, &buf)
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	if env.CSRF != "" {
		req.Header.Set("X-LucidFence-CSRF", env.CSRF)
	}
	res, err := env.Client.Do(req)
	if err != nil {
		return 0, err
	}
	defer func() { _ = res.Body.Close() }()
	raw, _ := io.ReadAll(res.Body)
	if out != nil && len(raw) > 0 && strings.HasPrefix(res.Header.Get("Content-Type"), "application/json") {
		_ = json.Unmarshal(raw, out)
	}
	if s, ok := out.(*string); ok {
		*s = string(raw)
	}
	return res.StatusCode, nil
}

// GetJSON hace GET y decodifica JSON (o vuelca el cuerpo si out es *string).
func (env *Env) GetJSON(ctx context.Context, path string, out any) (int, error) {
	return env.do(ctx, http.MethodGet, path, nil, out)
}

// PostJSON hace POST con cuerpo JSON y cabecera CSRF si hay sesión.
func (env *Env) PostJSON(ctx context.Context, path string, body, out any) (int, error) {
	return env.do(ctx, http.MethodPost, path, body, out)
}
