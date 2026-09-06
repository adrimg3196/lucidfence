package battery

import (
	"bytes"
	"context"
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
	defer env.StopServer()
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
