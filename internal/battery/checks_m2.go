package battery

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// deliveryTimeout es cuánto espera un check a que una entrega de webhook
// llegue al Receiver local. Variable (no const) para que los tests de
// "entrega inválida" no tengan que esperar los 10 s reales: la bajan antes
// de invocar el check y la restauran al terminar.
var deliveryTimeout = 10 * time.Second

// checksM2 son los ocho checks nuevos del hito M2: cada uno convierte un
// claim de riesgo/acciones en una comprobación contra el binario real. Los
// dos del webhook (firmado y OCSF) viven en checks_m2_webhook.go, junto con
// el Receiver que ambos levantan: aquí se quedan los otros seis, que no
// necesitan un receptor HTTP propio.
func checksM2() []Check {
	return []Check{
		{Name: "riesgo explicable: score, motivos, procedencia y verificación", Run: checkRiskExplained},
		{Name: "observe bloquea el wipe con doble llave", Run: checkObserveBlocksWipe},
		{Name: "webhook firmado entrega con las cuatro cabeceras", Run: checkWebhookSigned},
		{Name: "OCSF 2004 sin coordenadas", Run: checkOCSFNoCoords},
		{Name: "el cooldown suprime el segundo destructivo", Run: checkCooldownSuppressesSecond},
		{Name: "el handoff pendiente se aprueba y ejecuta bajo guardarraíles", Run: checkHandoffApprovedUnderGuardrails},
		{Name: "el what-if devuelve disparos sin ejecutar nada", Run: checkWhatIfNoExecution},
		{Name: "/events y /actions paginan con cursor sin repetir ni perder elementos", Run: checkPagination},
	}
}

// runOnce dispara un ciclo del motor y exige 200: varios checks de este
// fichero necesitan que la flota haya evolucionado antes de leerla.
func runOnce(ctx context.Context, env *Env) error {
	code, err := env.PostJSON(ctx, "/api/v1/engine/run-once", nil, nil)
	if err != nil || code != 200 {
		return fmt.Errorf("run-once: code=%d err=%v", code, err)
	}
	return nil
}

// checkRiskExplained exige que, tras un ciclo, al menos un dispositivo
// tenga un veredicto de riesgo con evidencia explícita: score no nulo,
// motivos no vacíos, procedencia "tool" (evidenceGate solo la concede
// cuando hay motivos) y verified true.
func checkRiskExplained(ctx context.Context, env *Env) error {
	if err := runOnce(ctx, env); err != nil {
		return err
	}
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/devices", &out); err != nil {
		return err
	}
	devs, err := items(out)
	if err != nil {
		return err
	}
	for _, it := range devs {
		d, ok := it.(map[string]any)
		if !ok {
			continue
		}
		risk, ok := mapField(d, "risk")
		if !ok || risk["score"] == nil {
			continue
		}
		reasons, _ := risk["reasons"].([]any)
		if len(reasons) > 0 && stringField(risk, "provenance") == "tool" && boolField(risk, "verified") {
			return nil
		}
	}
	return fmt.Errorf("ningún dispositivo tiene riesgo evaluado con procedencia \"tool\": %v", out)
}

// checkObserveBlocksWipe crea una política que siempre casa (dwell_seconds
// nunca es negativo) y ordena wipe. En observe, sin allow_wipe ni
// allowlist, el guardarraíl debe bloquearla siempre: dry_run true y
// blocked true, nunca una ejecución real.
func checkObserveBlocksWipe(ctx context.Context, env *Env) error {
	policy := map[string]any{
		"id": "battery-wipe-always", "name": "Batería: wipe siempre", "description": "política de prueba de guardarraíles",
		"when":    []map[string]any{{"field": "dwell_seconds", "op": "gte", "value": 0}},
		"actions": []map[string]any{{"action": "wipe"}},
		"enabled": true, "severity": "critical",
	}
	if code, err := env.PostJSON(ctx, "/api/v1/policies", policy, nil); err != nil || (code != 200 && code != 201) {
		return fmt.Errorf("crear política: code=%d err=%v", code, err)
	}
	if err := runOnce(ctx, env); err != nil {
		return err
	}
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/actions?limit=200", &out); err != nil {
		return err
	}
	acts, err := items(out)
	if err != nil {
		return err
	}
	found := false
	for _, it := range acts {
		a, ok := it.(map[string]any)
		if !ok || stringField(a, "action") != "wipe" {
			continue
		}
		found = true
		if !boolField(a, "dry_run") || !boolField(a, "blocked") {
			return fmt.Errorf("wipe sin doble llave debe quedar en dry-run y bloqueado, nunca real: %v", a)
		}
	}
	if !found {
		return fmt.Errorf("la política de wipe no produjo ninguna acción: %v", out)
	}
	return nil
}

// checkCooldownSuppressesSecond ejecuta la misma acción manual destructiva
// dos veces seguidas sobre el mismo dispositivo: la segunda, dentro de la
// ventana de cooldown, debe rechazarse (nunca ejecutarse) con un error que
// la nombre. La acción es reboot: el cooldown solo arma con una acción
// destructiva (lock, wipe, clear_passcode, reboot) y "wipe"/"lock" ya los
// ejercitan, con otras acciones y dispositivos, los checks de wipe y de
// handoff de esta misma batería.
func checkCooldownSuppressesSecond(ctx context.Context, env *Env) error {
	body := map[string]any{"action": "reboot"}
	var first map[string]any
	code1, err := env.PostJSON(ctx, "/api/v1/devices/dev-001/actions", body, &first)
	if err != nil || code1 != 200 {
		return fmt.Errorf("primera ejecución: code=%d err=%v body=%v", code1, err, first)
	}
	var second map[string]any
	code2, err := env.PostJSON(ctx, "/api/v1/devices/dev-001/actions", body, &second)
	if err != nil {
		return err
	}
	if code2 == 200 {
		return fmt.Errorf("la segunda ejecución inmediata debía suprimirse por cooldown: %v", second)
	}
	if !strings.Contains(strings.ToLower(fmt.Sprint(second)), "cooldown") {
		return fmt.Errorf("la respuesta de la segunda ejecución no nombra el cooldown: code=%d body=%v", code2, second)
	}
	return nil
}

// checkHandoffApprovedUnderGuardrails crea un playbook con una acción
// destructiva (lock), lo deja producir un handoff pendiente, lo aprueba y
// comprueba que la ejecución resultante respeta los guardarraíles: sigue en
// dry-run porque el motor está en observe.
func checkHandoffApprovedUnderGuardrails(ctx context.Context, env *Env) error {
	pb := map[string]any{
		"id": "battery-playbook-lock", "name": "Batería: bloqueo siempre", "description": "playbook de prueba de handoffs",
		"when":    []map[string]any{{"field": "dwell_seconds", "op": "gte", "value": 0}},
		"actions": []map[string]any{{"action": "lock"}},
		"enabled": true, "severity": "high",
	}
	if code, err := env.PostJSON(ctx, "/api/v1/playbooks", pb, nil); err != nil || (code != 200 && code != 201) {
		return fmt.Errorf("crear playbook: code=%d err=%v", code, err)
	}
	if err := runOnce(ctx, env); err != nil {
		return err
	}
	id, err := firstPendingHandoff(ctx, env)
	if err != nil {
		return err
	}
	// El cuerpo de /approve solo acepta "note": quién decide lo dice la
	// sesión, no el cliente; un campo desconocido devolvería 400.
	var decided map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/handoffs/"+id+"/approve", map[string]any{"note": "aprobado por la batería runtime"}, &decided)
	if err != nil || code != 200 {
		return fmt.Errorf("aprobar handoff: code=%d err=%v body=%v", code, err, decided)
	}
	if stringField(decided, "status") != "executed" {
		return fmt.Errorf("handoff aprobado debe quedar \"executed\": %v", decided)
	}
	result, ok := mapField(decided, "result")
	if !ok || !boolField(result, "dry_run") {
		return fmt.Errorf("la ejecución del handoff debe seguir en dry-run bajo observe: %v", decided)
	}
	return nil
}

func firstPendingHandoff(ctx context.Context, env *Env) (string, error) {
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/handoffs?status=pending", &out); err != nil {
		return "", err
	}
	hs, err := items(out)
	if err != nil || len(hs) == 0 {
		return "", fmt.Errorf("el playbook destructivo no dejó ningún handoff pendiente: %v", out)
	}
	h, ok := hs[0].(map[string]any)
	if !ok {
		return "", fmt.Errorf("handoff con forma inesperada: %v", hs[0])
	}
	return stringField(h, "id"), nil
}

// checkWhatIfNoExecution replay-ea una política nunca guardada contra el
// histórico ya recorrido por las ejecuciones anteriores de la batería: debe
// devolver disparos (firings) positivos sin dejar ni una acción nueva en
// /api/v1/actions.
func checkWhatIfNoExecution(ctx context.Context, env *Env) error {
	before, err := actionsTotal(ctx, env)
	if err != nil {
		return err
	}
	req := map[string]any{
		"policy": map[string]any{
			"id": "battery-whatif", "name": "Batería: what-if", "description": "política nunca guardada, solo replay",
			"when":    []map[string]any{{"field": "dwell_seconds", "op": "gte", "value": 0}},
			"actions": []map[string]any{{"action": "notify", "params": map[string]any{"channel": "security", "msg": "batería what-if"}}},
			"enabled": true, "severity": "low",
		},
		"limit": 500, "use_current_fences": true,
	}
	var out map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/policies/replay", req, &out)
	if err != nil || code != 200 {
		return fmt.Errorf("replay: code=%d err=%v body=%v", code, err, out)
	}
	firings, ferr := number(out, "firings")
	if ferr != nil || firings <= 0 {
		return fmt.Errorf("el what-if debe disparar sobre el histórico ya recorrido: %v", out)
	}
	after, err := actionsTotal(ctx, env)
	if err != nil {
		return err
	}
	if after != before {
		return fmt.Errorf("el what-if ejecutó acciones de verdad: antes=%d después=%d", before, after)
	}
	return nil
}

func actionsTotal(ctx context.Context, env *Env) (int, error) {
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/actions?limit=500", &out); err != nil {
		return 0, err
	}
	acts, err := items(out)
	if err != nil {
		return 0, err
	}
	return len(acts), nil
}

// checkPagination recorre /api/v1/events y /api/v1/actions página a página
// (limit pequeño) siguiendo next_cursor y compara el resultado contra una
// lectura de un tirón con un límite grande: mismo número de elementos, sin
// repetidos.
func checkPagination(ctx context.Context, env *Env) error {
	if err := checkPagesNoRepeat(ctx, env, "/api/v1/events"); err != nil {
		return fmt.Errorf("/api/v1/events: %w", err)
	}
	if err := checkPagesNoRepeat(ctx, env, "/api/v1/actions"); err != nil {
		return fmt.Errorf("/api/v1/actions: %w", err)
	}
	return nil
}

func checkPagesNoRepeat(ctx context.Context, env *Env, path string) error {
	var single map[string]any
	if _, err := env.GetJSON(ctx, path+"?limit=500", &single); err != nil {
		return err
	}
	oneShot, err := items(single)
	if err != nil {
		return err
	}
	paged, err := paginateAll(ctx, env, path, 3)
	if err != nil {
		return err
	}
	if len(paged) != len(oneShot) {
		return fmt.Errorf("paginado trajo %d elementos, de un tirón trajo %d", len(paged), len(oneShot))
	}
	seen := map[string]bool{}
	for _, it := range paged {
		raw, _ := json.Marshal(it)
		if seen[string(raw)] {
			return fmt.Errorf("elemento repetido entre páginas: %s", raw)
		}
		seen[string(raw)] = true
	}
	return nil
}

func paginateAll(ctx context.Context, env *Env, path string, pageSize int) ([]any, error) {
	var all []any
	cursor := ""
	for page := 0; page < 1000; page++ {
		url := fmt.Sprintf("%s?limit=%d", path, pageSize)
		if cursor != "" {
			url += "&cursor=" + cursor
		}
		var out map[string]any
		if _, err := env.GetJSON(ctx, url, &out); err != nil {
			return nil, err
		}
		pageItems, err := items(out)
		if err != nil {
			return nil, err
		}
		all = append(all, pageItems...)
		next := stringField(out, "next_cursor")
		if next == "" {
			return all, nil
		}
		cursor = next
	}
	return nil, fmt.Errorf("%s: demasiadas páginas, ¿cursor en bucle?", path)
}
