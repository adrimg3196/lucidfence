package battery

import (
	"context"
	"fmt"
)

// checkWebhookSigned levanta un Receiver local, lo autoriza en la allowlist
// de egress (127.0.0.1 es privada: hace falta allow_private), configura el
// webhook con un secreto y crea una regla de riesgo que casa con la flota.
// Quien produce la entrega es el ciclo, dentro de run-once: POST
// /alerts/evaluate es la vista previa de T19 y por contrato no notifica ni
// persiste, así que solo sirve como aserción previa de que la regla recién
// creada sí dispara. El receptor debe confirmar una entrega válida (firma
// correcta y las cuatro cabeceras).
func checkWebhookSigned(ctx context.Context, env *Env) error {
	rcv, stop, err := StartReceiver("bateria-secreto-webhook-2026")
	if err != nil {
		return err
	}
	defer func() { _ = stop() }()
	if err := putEgressAndWebhook(ctx, env, rcv, "native"); err != nil {
		return err
	}
	if err := createAndEvaluateAlert(ctx, env, "battery-alert-risk"); err != nil {
		return err
	}
	if err := runOnce(ctx, env); err != nil {
		return err
	}
	if !awaitDelivery(rcv, "alert.fired", deliveryTimeout, nil) {
		return fmt.Errorf("el receptor no vio una entrega \"alert.fired\" firmada en 10s; recibidas=%v", rcv.Deliveries())
	}
	return nil
}

// checkOCSFNoCoords cambia el formato del webhook a ocsf y crea su PROPIA
// regla de alerta, con id distinto de la de checkWebhookSigned, para
// disparar con su propio ciclo. El enfriamiento de alertas es de 30 min por
// regla y dispositivo: reevaluar la misma regla dentro de la ventana no
// emitiría nada, así que una regla nueva deja este check independiente del
// anterior. El cuerpo recibido debe llevar class_uid 2004 y no llevar
// coordenadas en ningún punto del árbol JSON.
func checkOCSFNoCoords(ctx context.Context, env *Env) error {
	rcv, stop, err := StartReceiver("bateria-secreto-ocsf-2026")
	if err != nil {
		return err
	}
	defer func() { _ = stop() }()
	if err := putEgressAndWebhook(ctx, env, rcv, "ocsf"); err != nil {
		return err
	}
	if err := createAndEvaluateAlert(ctx, env, "battery-alert-risk-ocsf"); err != nil {
		return err
	}
	if err := runOnce(ctx, env); err != nil {
		return err
	}
	var bad error
	ok := awaitDelivery(rcv, "alert.fired", deliveryTimeout, func(body map[string]any) bool {
		classUID, _ := body["class_uid"].(float64)
		if classUID != 2004 {
			bad = fmt.Errorf("class_uid=%v, quiero 2004", body["class_uid"])
			return false
		}
		if containsKeyDeep(body, "lat") || containsKeyDeep(body, "lng") {
			bad = fmt.Errorf("el payload OCSF no debe llevar coordenadas: %v", body)
			return false
		}
		return true
	})
	if bad != nil {
		return bad
	}
	if !ok {
		return fmt.Errorf("el receptor no vio una entrega OCSF firmada en 10s")
	}
	return nil
}

func putEgressAndWebhook(ctx context.Context, env *Env, rcv *Receiver, format string) error {
	if code, err := env.PutJSON(ctx, "/api/v1/settings/egress", map[string]any{"hosts": []string{"127.0.0.1"}, "allow_private": true}, nil); err != nil || code != 200 {
		return fmt.Errorf("egress: code=%d err=%v", code, err)
	}
	webhook := map[string]any{
		"url": rcv.URL, "format": format, "enabled": true, "secret": rcv.Secret,
		"events": []string{"incident.opened", "incident.closed", "handoff.pending", "action.executed", "alert.fired"},
	}
	var out map[string]any
	code, err := env.PutJSON(ctx, "/api/v1/settings/webhooks", webhook, &out)
	if err != nil || code != 200 {
		return fmt.Errorf("webhooks: code=%d err=%v body=%v", code, err, out)
	}
	// La respuesta es el documento de ajustes entero (settingsView), no el
	// bloque que se acaba de mandar: el indicador del secreto vive en
	// webhook.secret_set, nunca en la raíz.
	wh, ok := mapField(out, "webhook")
	if !ok || !boolField(wh, "secret_set") {
		return fmt.Errorf("webhooks: el secreto no quedó guardado: body=%v", out)
	}
	return nil
}

// createAndEvaluateAlert crea una regla risk_above con umbral 0: cualquier
// dispositivo con score numérico dispara (un umbral negativo lo rechaza el
// dominio, y checkRiskExplained, que corre antes, ya garantiza que al menos
// un dispositivo tiene score). Evaluarla una vez es la aserción previa de
// que la regla recién creada sí casa con la flota; la entrega real la
// produce el ciclo siguiente.
func createAndEvaluateAlert(ctx context.Context, env *Env, id string) error {
	alert := map[string]any{"id": id, "name": "Batería: riesgo alto", "kind": "risk_above", "threshold": 0, "severity": "medium", "enabled": true}
	if code, err := env.PostJSON(ctx, "/api/v1/alerts", alert, nil); err != nil || (code != 200 && code != 201) {
		return fmt.Errorf("crear alerta %s: code=%d err=%v", id, code, err)
	}
	var out map[string]any
	if code, err := env.PostJSON(ctx, "/api/v1/alerts/evaluate", nil, &out); err != nil || code != 200 {
		return fmt.Errorf("evaluar alertas: code=%d err=%v body=%v", code, err, out)
	}
	count, cerr := number(out, "count")
	if cerr != nil || count <= 0 {
		return fmt.Errorf("la regla %s no casa con ningún dispositivo: %v", id, out)
	}
	return nil
}
