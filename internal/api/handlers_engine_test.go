package api

import "testing"

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
