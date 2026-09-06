package battery

import (
	"bytes"
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

type bytesBuffer = bytes.Buffer

func buildBinary(t *testing.T) string {
	t.Helper()
	bin := filepath.Join(t.TempDir(), "lucidfence")
	cmd := exec.Command("go", "build", "-o", bin, "../../cmd/lucidfence")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go build: %v\n%s", err, out)
	}
	return bin
}

const dashboardCheckName = "dashboard real embebido en /"

// checksM1ParaTest omite el check de dashboard cuando este checkout no
// lleva el frontend compilado (internal/web/dist/index.html ausente, p. ej.
// en CI antes de "make web"): sin build real el binario sirve el
// placeholder y el check fallaría por algo ajeno a esta batería, no por una
// regresión suya.
func checksM1ParaTest(t *testing.T) []Check {
	t.Helper()
	checks := checksM1WithoutServer()
	if _, err := os.Stat(filepath.Join("..", "web", "dist", "index.html")); err != nil {
		t.Logf("dashboard no compilado (%v); omito %q", err, dashboardCheckName)
		out := make([]Check, 0, len(checks)-1)
		for _, c := range checks {
			if c.Name != dashboardCheckName {
				out = append(out, c)
			}
		}
		return out
	}
	return checks
}

func TestStartServerYChecksM1(t *testing.T) {
	if testing.Short() {
		t.Skip("compila el binario; omitido en -short")
	}
	env := &Env{Bin: buildBinary(t), Tmp: t.TempDir()}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	if err := env.StartServer(ctx); err != nil {
		t.Fatal(err)
	}
	defer func() {
		// checkStop ya para el servidor dentro de checksM1ParaTest; esta
		// segunda llamada debe ser idempotente (apagado limpio real).
		if err := env.StopServer(); err != nil {
			t.Errorf("StopServer tras el test: %v", err)
		}
	}()
	var health map[string]any
	if code, err := env.GetJSON(ctx, "/api/v1/health", &health); err != nil || code != 200 || health["status"] != "ok" {
		t.Fatalf("%d %v %v", code, err, health)
	}
	var buf bytesBuffer
	passed, total := Run(ctx, env, checksM1ParaTest(t), &buf)
	if passed != total {
		t.Fatalf("batería M1: %d/%d\n%s", passed, total, buf.String())
	}
	if _, err := os.Stat(filepath.Join(env.Tmp, "data", "orgs", "default", "devices.json")); err != nil {
		t.Fatal("run-once debe persistir devices.json")
	}
}

// TestStopServerReportaMuerteForzada comprueba, sin binario real, que
// checkStop propaga el error de apagado tal cual lo devuelve env.stop.
func TestStopServerReportaMuerteForzada(t *testing.T) {
	want := errors.New("el servidor no atendió SIGINT en 10 s; se mató a la fuerza")
	env := &Env{stop: func() error { return want }}
	if err := checkStop(context.Background(), env); !errors.Is(err, want) {
		t.Fatalf("checkStop = %v, quiero %v", err, want)
	}
}

// TestStopServerIdempotente comprueba que una segunda llamada a StopServer,
// tras haberse ya invocado stop una vez, no vuelve a llamarlo y devuelve nil.
func TestStopServerIdempotente(t *testing.T) {
	calls := 0
	env := &Env{stop: func() error {
		calls++
		return errors.New("boom")
	}}
	if err := env.StopServer(); err == nil {
		t.Fatal("la primera llamada debe propagar el error de stop")
	}
	if err := env.StopServer(); err != nil {
		t.Fatalf("la segunda llamada debe ser idempotente y devolver nil, got %v", err)
	}
	if calls != 1 {
		t.Fatalf("stop debe invocarse una sola vez, calls=%d", calls)
	}
}
