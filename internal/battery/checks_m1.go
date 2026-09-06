package battery

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"
)

func checksM1() []Check {
	return append([]Check{{Name: "serve arranca y /api/v1/health responde", Run: checkServe}}, checksM1WithoutServer()...)
}

// checksM1WithoutServer son los checks que asumen el servidor ya arrancado.
// run-once va antes que la lectura de /devices: es el ciclo explícito de
// este check el que hace evolucionar la flota demo (el ciclo automático
// arrancado por serve corre antes de que exista la geocerca demo, así que
// por sí solo no basta para que dev-001 termine dentro).
func checksM1WithoutServer() []Check {
	return []Check{
		{Name: "readyz confirma datos escribibles", Run: checkReadyz},
		{Name: "setup crea el owner y abre sesión", Run: checkSetup},
		{Name: "sin sesión /devices devuelve 401 con forma de error", Run: checkUnauthenticated},
		{Name: "run-once evalúa la flota y hay dispositivos inside", Run: checkRunOnce},
		{Name: "flota demo visible vía /devices", Run: checkDevices},
		{Name: "transición none:unknown → demo-hq:inside registrada", Run: checkTransition},
		{Name: "acciones on_enter ejecutadas en dry-run (observe)", Run: checkActionsDryRun},
		{Name: "dashboard real embebido en /", Run: checkDashboard},
		{Name: "mutación con cookie sin CSRF devuelve 403", Run: checkCSRF},
		{Name: "servidor para limpio", Run: checkStop},
	}
}

func checkServe(ctx context.Context, env *Env) error {
	if err := env.StartServer(ctx); err != nil {
		return err
	}
	var h map[string]any
	code, err := env.GetJSON(ctx, "/api/v1/health", &h)
	if err != nil || code != 200 || h["status"] != "ok" || h["setup_required"] != true {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, h)
	}
	return nil
}

func checkReadyz(ctx context.Context, env *Env) error {
	var r map[string]any
	if code, err := env.GetJSON(ctx, "/api/v1/readyz", &r); err != nil || code != 200 || r["ready"] != true {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, r)
	}
	return nil
}

func checkSetup(ctx context.Context, env *Env) error {
	var out map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/auth/setup", map[string]any{"email": "battery@lucidfence.local", "name": "Batería", "password": "bateria-runtime-2026", "mode": "demo"}, &out)
	if err != nil || code != 201 {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, out)
	}
	csrf, _ := out["csrf"].(string)
	if csrf == "" {
		return fmt.Errorf("sin csrf: %v", out)
	}
	env.CSRF = csrf
	return nil
}

func checkUnauthenticated(ctx context.Context, env *Env) error {
	anon := &Env{BaseURL: env.BaseURL, Client: &http.Client{}}
	var out map[string]any
	code, err := anon.GetJSON(ctx, "/api/v1/devices", &out)
	if err != nil || code != 401 || out["code"] != "unauthenticated" || out["error"] == "" {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, out)
	}
	return nil
}

// checkDevices reintenta hasta 5 veces con pausas de 500 ms mientras total
// sea menor que 6: run-once ya deja la flota persistida, pero este check
// puede solaparse con el ciclo automático que serve arranca al vuelo, así
// que una lectura inmediata no siempre ve la flota completa todavía.
func checkDevices(ctx context.Context, env *Env) error {
	var out map[string]any
	var total float64
	for attempt := 1; attempt <= 5; attempt++ {
		code, err := env.GetJSON(ctx, "/api/v1/devices", &out)
		if err != nil || code != 200 {
			return fmt.Errorf("code=%d err=%v", code, err)
		}
		total, _ = out["total"].(float64)
		if total == 6 {
			return nil
		}
		if attempt < 5 {
			time.Sleep(500 * time.Millisecond)
		}
	}
	return fmt.Errorf("total=%v, quiero 6", total)
}

func checkRunOnce(ctx context.Context, env *Env) error {
	var st map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/engine/run-once", nil, &st)
	if err != nil || code != 200 {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, st)
	}
	if st["devices_total"].(float64) != 6 || st["inside"].(float64) < 2 {
		return fmt.Errorf("stats=%v", st)
	}
	var devs map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/devices?state=inside", &devs); err != nil {
		return err
	}
	for _, it := range devs["items"].([]any) {
		if d := it.(map[string]any); d["id"] == "dev-001" && d["inside_fence"] == "demo-hq" {
			return nil
		}
	}
	return fmt.Errorf("dev-001 no está inside en demo-hq: %v", devs)
}

// checkTransition exige que dev-001 tenga registrada alguna transición hacia
// demo-hq:inside, sea cual sea su origen: el ciclo automático que serve
// arranca al vuelo corre antes de que exista la geocerca demo (todavía no
// hay setup), así que la secuencia real es none:unknown → none:outside →
// demo-hq:inside, y esta última la deja el run-once explícito del check
// anterior.
func checkTransition(ctx context.Context, env *Env) error {
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/events?limit=100", &out); err != nil {
		return err
	}
	for _, it := range out["items"].([]any) {
		ev := it.(map[string]any)
		if ev["device_id"] == "dev-001" && ev["to"] == "demo-hq:inside" {
			return nil
		}
	}
	return fmt.Errorf("sin transición de dev-001 a demo-hq:inside: %v", out)
}

func checkActionsDryRun(ctx context.Context, env *Env) error {
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/actions?limit=100", &out); err != nil {
		return err
	}
	items := out["items"].([]any)
	if len(items) == 0 {
		return fmt.Errorf("sin acciones")
	}
	for _, it := range items {
		a := it.(map[string]any)
		if a["dry_run"] != true || a["simulated"] != true {
			return fmt.Errorf("acción fuera de dry-run: %v", a)
		}
	}
	return nil
}

func checkDashboard(ctx context.Context, env *Env) error {
	var html string
	code, err := env.GetJSON(ctx, "/", &html)
	if err != nil || code != 200 {
		return fmt.Errorf("code=%d err=%v", code, err)
	}
	if !strings.Contains(html, `id="root"`) || strings.Contains(html, "frontend no compilado") {
		return fmt.Errorf("el binario no lleva el dashboard compilado (make web)")
	}
	return nil
}

func checkCSRF(ctx context.Context, env *Env) error {
	saved := env.CSRF
	env.CSRF = ""
	defer func() { env.CSRF = saved }()
	var out map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/fences", map[string]any{"id": "x", "name": "X", "kind": "circle", "center": map[string]float64{"lat": 1, "lng": 1}, "radius_m": 10}, &out)
	if err != nil || code != 403 || out["code"] != "csrf" {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, out)
	}
	return nil
}

func checkStop(_ context.Context, env *Env) error {
	env.StopServer()
	return nil
}
