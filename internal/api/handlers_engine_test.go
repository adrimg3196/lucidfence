package api

import (
	"context"
	"fmt"
	"net/http"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/store"
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
	enf, _ := out["enforcement"].(map[string]any)
	if res.StatusCode != 200 || enf["mode"] != "observe" || out["cycles"].(float64) != 0 {
		t.Fatalf("status: %d %v", res.StatusCode, out)
	}
	if enf["allow_wipe"] != false || enf["action_cooldown_seconds"].(float64) != 3600 {
		t.Fatalf("el estado publica los guardarraíles completos, no solo el modo: %v", enf)
	}
	if res, _ := e.do("POST", "/api/v1/engine/run-once", nil, true); res.StatusCode != 200 {
		t.Fatal("run-once")
	}
	res, out = e.do("GET", "/api/v1/events?limit=3", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 3 {
		t.Fatalf("events: %v", out)
	}
	if _, hay := out["next_cursor"]; !hay {
		t.Fatalf("next_cursor viaja siempre, aunque sea vacío: %v", out)
	}
	res, out = e.do("GET", "/api/v1/actions", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || len(items) == 0 || items[0].(map[string]any)["dry_run"] != true {
		t.Fatalf("actions: %v", out)
	}
}

// sembrarEventos escribe n transiciones numeradas en events.jsonl. El id del
// dispositivo lleva el índice, así que la prueba puede comprobar que la
// paginación no repite ni pierde ninguna.
func sembrarEventos(t *testing.T, e *testEnv, n int) {
	t.Helper()
	at := time.Date(2026, 9, 6, 9, 0, 0, 0, time.UTC)
	for i := range n {
		ev := transition.Transition{At: at.Add(time.Duration(i) * time.Second),
			DeviceID: fmt.Sprintf("dev-%03d", i), DeviceName: "Dispositivo", From: "none:unknown", To: "hq:inside"}
		if err := e.org.AppendEvent(ev); err != nil {
			t.Fatal(err)
		}
	}
}

func sembrarAcciones(t *testing.T, e *testEnv, n int) {
	t.Helper()
	at := time.Date(2026, 9, 6, 9, 0, 0, 0, time.UTC)
	for i := range n {
		res := action.Result{Adapter: "fake", OK: true, DeviceID: fmt.Sprintf("dev-%03d", i),
			DeviceName: "Dispositivo", Action: action.Message, DryRun: true, Simulated: true,
			At: at.Add(time.Duration(i) * time.Second)}
		if err := e.org.AppendAction(res); err != nil {
			t.Fatal(err)
		}
	}
}

// recorrer pagina la ruta entera de 100 en 100 y devuelve los device_id en el
// orden en que los sirvió la API.
func recorrer(t *testing.T, e *testEnv, path string) []string {
	t.Helper()
	var ids []string
	cursor := ""
	for paginas := 0; ; paginas++ {
		if paginas > 20 {
			t.Fatal("la paginación no termina")
		}
		url := path + "?limit=100"
		if cursor != "" {
			url += "&cursor=" + cursor
		}
		res, out := e.do("GET", url, nil, true)
		if res.StatusCode != 200 {
			t.Fatalf("%s: %d %v", url, res.StatusCode, out)
		}
		for _, it := range out["items"].([]any) {
			ids = append(ids, it.(map[string]any)["device_id"].(string))
		}
		cursor, _ = out["next_cursor"].(string)
		if cursor == "" {
			return ids
		}
	}
}

func unicos(ids []string) int {
	set := map[string]bool{}
	for _, id := range ids {
		set[id] = true
	}
	return len(set)
}

func TestEventosPaginanSinRepetirNiPerder(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	total := store.MaxPageLimit + 10
	sembrarEventos(t, e, total)

	ids := recorrer(t, e, "/api/v1/events")
	if len(ids) != total || unicos(ids) != total {
		t.Fatalf("recorrido completo: %d elementos, %d únicos, quiero %d", len(ids), unicos(ids), total)
	}
	if ids[0] != fmt.Sprintf("dev-%03d", total-1) {
		t.Fatalf("la primera página empieza por lo más reciente: %q", ids[0])
	}

	// limit por encima del máximo se acota, no se rechaza.
	res, out := e.do("GET", "/api/v1/events?limit=9999", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != store.MaxPageLimit {
		t.Fatalf("limit acotado a %d: %d %d elementos", store.MaxPageLimit, res.StatusCode, len(out["items"].([]any)))
	}
	if out["next_cursor"] == "" {
		t.Fatalf("quedan %d eventos por delante: next_cursor no puede venir vacío", total-store.MaxPageLimit)
	}

	res, out = e.do("GET", "/api/v1/events?cursor=no-es-un-cursor", nil, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("cursor manipulado: %d %v", res.StatusCode, out)
	}
	if e.logs.Len() != 0 {
		t.Fatalf("un cursor mal escrito no es un fallo del servidor: %s", e.logs.String())
	}
}

func TestAccionesPaginanSinRepetirNiPerder(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	const total = 250
	sembrarAcciones(t, e, total)

	ids := recorrer(t, e, "/api/v1/actions")
	if len(ids) != total || unicos(ids) != total {
		t.Fatalf("recorrido completo: %d elementos, %d únicos, quiero %d", len(ids), unicos(ids), total)
	}
	if ids[0] != "dev-249" || ids[len(ids)-1] != "dev-000" {
		t.Fatalf("de la más reciente a la más antigua: %q ... %q", ids[0], ids[len(ids)-1])
	}
	res, out := e.do("GET", "/api/v1/actions?cursor=%%%%", nil, true)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("cursor manipulado: %d %v", res.StatusCode, out)
	}
}
