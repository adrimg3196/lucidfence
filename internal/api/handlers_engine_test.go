package api

import (
	"context"
	"net/http"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// blockingFleet envuelve fakeFleet pero bloquea FetchDevices hasta que el
// test cierra release. RunOnce mantiene el candado del ciclo (cycleMu) todo
// el tiempo que FetchDevices tarda, así que esto permite provocar de forma
// determinista un segundo POST run-once mientras el primero sigue en curso.
type blockingFleet struct {
	*fakeFleet
	started chan struct{}
	release chan struct{}
}

func (f *blockingFleet) FetchDevices(ctx context.Context) ([]device.Device, error) {
	close(f.started)
	<-f.release
	return f.fakeFleet.FetchDevices(ctx)
}

// TestEngineRunOnceConcurrenteDevuelve409 cubre la ronda de corrección
// M1-R17 (ítem opcional): un segundo POST run-once mientras el primero sigue
// dentro del ciclo debe responder 409 cycle_in_progress.
func TestEngineRunOnceConcurrenteDevuelve409(t *testing.T) {
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	fleet := &blockingFleet{
		fakeFleet: &fakeFleet{now: func() time.Time { return now }},
		started:   make(chan struct{}),
		release:   make(chan struct{}),
	}
	e := newTestEnvWithFleet(t, fleet, now)
	e.setup("empty")

	statusCh := make(chan int, 1)
	go func() {
		req, _ := http.NewRequest(http.MethodPost, e.srv.URL+"/api/v1/engine/run-once", nil)
		req.AddCookie(e.cookie)
		req.Header.Set(CSRFHeader, e.csrf)
		res, err := http.DefaultClient.Do(req)
		if err != nil {
			statusCh <- -1
			return
		}
		_ = res.Body.Close()
		statusCh <- res.StatusCode
	}()

	<-fleet.started
	res, out := e.do("POST", "/api/v1/engine/run-once", nil, true)
	close(fleet.release)
	if res.StatusCode != 409 || out["code"] != "cycle_in_progress" {
		t.Fatalf("segundo run-once concurrente: %d %v", res.StatusCode, out)
	}
	if got := <-statusCh; got != 200 {
		t.Fatalf("primer run-once: %d", got)
	}
}

func TestEngineStatusEventosYAcciones(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	res, out := e.do("GET", "/api/v1/engine/status", nil, true)
	if res.StatusCode != 200 || out["enforcement"] != "observe" || out["cycles"].(float64) != 0 {
		t.Fatalf("status: %d %v", res.StatusCode, out)
	}
	if res, _ := e.do("POST", "/api/v1/engine/run-once", nil, true); res.StatusCode != 200 {
		t.Fatal("run-once")
	}
	res, out = e.do("GET", "/api/v1/events?limit=3", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 3 {
		t.Fatalf("events: %v", out)
	}
	res, out = e.do("GET", "/api/v1/actions", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || len(items) == 0 || items[0].(map[string]any)["dry_run"] != true {
		t.Fatalf("actions: %v", out)
	}
}
