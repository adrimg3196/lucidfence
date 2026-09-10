package battery

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

// jsonRoutes monta un servidor de mentira con solo las respuestas que cada
// check necesita, buenas o equivocadas ("MÉTODO /ruta" ignora la query). Lo
// usan también los checks del webhook, en checks_m2_webhook_test.go.
func jsonRoutes(t *testing.T, routes map[string]func(http.ResponseWriter, *http.Request)) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	for pattern, h := range routes {
		mux.HandleFunc(pattern, h)
	}
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}

func jsonOK(status int, body any) func(http.ResponseWriter, *http.Request) {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(body)
	}
}

func envFor(srv *httptest.Server) *Env {
	return &Env{BaseURL: srv.URL, Client: srv.Client()}
}

func TestCheckRiskExplainedGoodAndBad(t *testing.T) {
	good := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/engine/run-once": jsonOK(200, map[string]any{}),
		"GET /api/v1/devices": jsonOK(200, map[string]any{"items": []any{
			map[string]any{"id": "dev-001", "risk": map[string]any{"score": nil, "reasons": []any{}, "provenance": "none", "verified": false}},
			map[string]any{"id": "dev-002", "risk": map[string]any{"score": 42.0, "reasons": []any{"fuera de geocerca permitida"}, "provenance": "tool", "verified": true}},
		}}),
	})
	if err := checkRiskExplained(context.Background(), envFor(good)); err != nil {
		t.Fatalf("un dispositivo con riesgo explicado debía pasar: %v", err)
	}

	bad := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/engine/run-once": jsonOK(200, map[string]any{}),
		"GET /api/v1/devices": jsonOK(200, map[string]any{"items": []any{
			map[string]any{"id": "dev-001", "risk": map[string]any{"score": nil, "reasons": []any{}, "provenance": "none", "verified": false}},
		}}),
	})
	if err := checkRiskExplained(context.Background(), envFor(bad)); err == nil {
		t.Fatal("sin ningún dispositivo evaluado no debía dar el check por bueno")
	}
}

// wipeActionsServer sirve un /actions con una sola acción wipe, la que el
// caso de prueba quiera: es el único dato que mira checkObserveBlocksWipe.
func wipeActionsServer(t *testing.T, wipe map[string]any) *httptest.Server {
	t.Helper()
	return jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/policies":        jsonOK(201, map[string]any{}),
		"POST /api/v1/engine/run-once": jsonOK(200, map[string]any{}),
		"GET /api/v1/actions":          jsonOK(200, map[string]any{"items": []any{wipe}}),
	})
}

func TestCheckObserveBlocksWipeGoodAndBad(t *testing.T) {
	// Las dos formas que el motor sí puede emitir. En observe (el modo por
	// omisión de la batería) Guardrails.Decide ya devuelve dry_run antes de
	// mirar la doble llave, así que blocked ni siquiera se pone —y el tag es
	// omitempty, o sea que no viaja—; en enforce sin allow_wipe el resultado
	// sale bloqueado y stamp le fija dry_run a false. Nunca los dos a la vez.
	good := map[string]map[string]any{
		"observe deja el wipe en dry-run": {"action": "wipe", "dry_run": true, "ok": true},
		"enforce sin llave lo bloquea":    {"action": "wipe", "dry_run": false, "blocked": true, "ok": false},
	}
	for name, wipe := range good {
		if err := checkObserveBlocksWipe(context.Background(), envFor(wipeActionsServer(t, wipe))); err != nil {
			t.Fatalf("%s debía pasar: %v", name, err)
		}
	}

	// Lo único inaceptable: un wipe de verdad, ni en dry-run ni bloqueado.
	live := map[string]any{"action": "wipe", "dry_run": false, "blocked": false, "ok": true}
	if err := checkObserveBlocksWipe(context.Background(), envFor(wipeActionsServer(t, live))); err == nil {
		t.Fatal("un wipe ejecutado de verdad no debía dar el check por bueno")
	}
}

// checkCooldownSuppressesSecond manda "reboot" (la cooldown solo arma con
// una acción destructiva): el servidor de mentira solo mira método y ruta,
// así que no necesita saber qué acción concreta viaja en el cuerpo.
func TestCheckCooldownSuppressesSecondGoodAndBad(t *testing.T) {
	calls := 0
	good := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/devices/dev-001/actions": func(w http.ResponseWriter, r *http.Request) {
			calls++
			if calls == 1 {
				jsonOK(200, map[string]any{"ok": true})(w, r)
				return
			}
			jsonOK(409, map[string]any{"error": "acción suprimida", "code": "action_suppressed", "detail": "cooldown activo"})(w, r)
		},
	})
	if err := checkCooldownSuppressesSecond(context.Background(), envFor(good)); err != nil {
		t.Fatalf("segunda ejecución suprimida por cooldown debía pasar: %v", err)
	}

	bad := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/devices/dev-001/actions": jsonOK(200, map[string]any{"ok": true}),
	})
	if err := checkCooldownSuppressesSecond(context.Background(), envFor(bad)); err == nil {
		t.Fatal("una segunda ejecución con código 200 no debía dar el check por bueno")
	}
}

func TestCheckHandoffApprovedUnderGuardrailsGoodAndBad(t *testing.T) {
	pending := jsonOK(200, map[string]any{"items": []any{map[string]any{"id": "ho-1", "status": "pending"}}})
	good := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/playbooks":             jsonOK(201, map[string]any{}),
		"POST /api/v1/engine/run-once":       jsonOK(200, map[string]any{}),
		"GET /api/v1/handoffs":               pending,
		"POST /api/v1/handoffs/{id}/approve": jsonOK(200, map[string]any{"status": "executed", "result": map[string]any{"dry_run": true}}),
	})
	if err := checkHandoffApprovedUnderGuardrails(context.Background(), envFor(good)); err != nil {
		t.Fatalf("handoff aprobado y ejecutado en dry-run debía pasar: %v", err)
	}

	bad := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"POST /api/v1/playbooks":             jsonOK(201, map[string]any{}),
		"POST /api/v1/engine/run-once":       jsonOK(200, map[string]any{}),
		"GET /api/v1/handoffs":               pending,
		"POST /api/v1/handoffs/{id}/approve": jsonOK(200, map[string]any{"status": "approved"}),
	})
	if err := checkHandoffApprovedUnderGuardrails(context.Background(), envFor(bad)); err == nil {
		t.Fatal("un handoff que no queda \"executed\" no debía dar el check por bueno")
	}
}

func TestCheckWhatIfNoExecutionGoodAndBad(t *testing.T) {
	good := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"GET /api/v1/actions":          jsonOK(200, map[string]any{"items": []any{map[string]any{"id": "a1"}}}),
		"POST /api/v1/policies/replay": jsonOK(200, map[string]any{"firings": 3}),
	})
	if err := checkWhatIfNoExecution(context.Background(), envFor(good)); err != nil {
		t.Fatalf("what-if sin ejecutar nada debía pasar: %v", err)
	}

	calls := 0
	badExec := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"GET /api/v1/actions": func(w http.ResponseWriter, r *http.Request) {
			calls++
			items := []any{map[string]any{"id": "a1"}}
			if calls > 1 {
				items = append(items, map[string]any{"id": "a2"})
			}
			jsonOK(200, map[string]any{"items": items})(w, r)
		},
		"POST /api/v1/policies/replay": jsonOK(200, map[string]any{"firings": 3}),
	})
	if err := checkWhatIfNoExecution(context.Background(), envFor(badExec)); err == nil {
		t.Fatal("un what-if que deja una acción nueva no debía dar el check por bueno")
	}
	badFirings := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"GET /api/v1/actions":          jsonOK(200, map[string]any{"items": []any{}}),
		"POST /api/v1/policies/replay": jsonOK(200, map[string]any{"firings": 0}),
	})
	if err := checkWhatIfNoExecution(context.Background(), envFor(badFirings)); err == nil {
		t.Fatal("un what-if sin disparos no debía dar el check por bueno")
	}
}

func fiveItems(prefix string) []map[string]any {
	out := make([]map[string]any, 5)
	for i := range out {
		out[i] = map[string]any{"id": fmt.Sprintf("%s-%d", prefix, i)}
	}
	return out
}

// pagedItemsHandler trocea all por limit/cursor (índice absoluto de
// elemento), igual que describe T8 para EventsPage/ActionsPage.
func pagedItemsHandler(all []map[string]any) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		limit := 500
		if l := r.URL.Query().Get("limit"); l != "" {
			_, _ = fmt.Sscanf(l, "%d", &limit)
		}
		start := 0
		if c := r.URL.Query().Get("cursor"); c != "" {
			_, _ = fmt.Sscanf(c, "%d", &start)
		}
		end := min(start+limit, len(all))
		page := all[min(start, len(all)):end]
		items := make([]any, len(page))
		for i, it := range page {
			items[i] = it
		}
		next := ""
		if end < len(all) {
			next = fmt.Sprintf("%d", end)
		}
		jsonOK(200, map[string]any{"items": items, "next_cursor": next})(w, r)
	}
}

func TestCheckPaginationGoodAndBad(t *testing.T) {
	good := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"GET /api/v1/events":  pagedItemsHandler(fiveItems("ev")),
		"GET /api/v1/actions": pagedItemsHandler(fiveItems("ac")),
	})
	if err := checkPagination(context.Background(), envFor(good)); err != nil {
		t.Fatalf("paginación consistente debía pasar: %v", err)
	}

	withRepeat := append(fiveItems("ev"), map[string]any{"id": "ev-0"})
	bad := jsonRoutes(t, map[string]func(http.ResponseWriter, *http.Request){
		"GET /api/v1/events":  pagedItemsHandler(withRepeat),
		"GET /api/v1/actions": pagedItemsHandler(fiveItems("ac")),
	})
	if err := checkPagination(context.Background(), envFor(bad)); err == nil {
		t.Fatal("un elemento repetido en la paginación no debía dar el check por bueno")
	}
}
