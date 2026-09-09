package notify

import (
	"bytes"
	"encoding/json"
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/alert"
)

// alertaDisparada es el disparo que devuelve alert.Evaluate cuando una regla
// supera su umbral: todos los campos rellenos y ninguna colección.
func alertaDisparada() *alert.Firing {
	return &alert.Firing{
		At:     time.Date(2026, 8, 29, 10, 5, 0, 0, time.UTC),
		RuleID: "al-riesgo-alto", RuleName: "Riesgo alto sostenido",
		Kind:     alert.KindRiskAbove,
		DeviceID: "dev-7", DeviceName: "Tablet almacén",
		Severity: "critical", Reason: "riesgo 88 (umbral 80)", Value: 88,
	}
}

func eventoAlerta() Event {
	return Event{
		Kind: EventAlertFired, At: time.Date(2026, 8, 29, 10, 5, 0, 0, time.UTC),
		DeliveryID: "dlv-0011", Firing: alertaDisparada(),
	}
}

// clavesDe devuelve las claves de primer nivel del objeto JSON en el orden en
// que viajan. Se leen con el decodificador y no buscando subcadenas, para no
// confundirlas con las del objeto anidado.
func clavesDe(t *testing.T, raw []byte) []string {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	if _, err := dec.Token(); err != nil {
		t.Fatal(err)
	}
	var claves []string
	for dec.More() {
		tok, err := dec.Token()
		if err != nil {
			t.Fatal(err)
		}
		nombre, ok := tok.(string)
		if !ok {
			t.Fatalf("clave inesperada %v", tok)
		}
		claves = append(claves, nombre)
		var descartar json.RawMessage
		if err := dec.Decode(&descartar); err != nil {
			t.Fatal(err)
		}
	}
	return claves
}

// TestNativePayloadDeUnaAlertaLlevaLaListaBlancaDelDisparo fija el quinto sobre
// nativo, el de alert.fired: los otros cuatro ya los fijan sus tests y este era
// el único formato de salida del producto que ningún test construía.
func TestNativePayloadDeUnaAlertaLlevaLaListaBlancaDelDisparo(t *testing.T) {
	cuerpo, err := NativePayload(eventoAlerta())
	if err != nil {
		t.Fatal(err)
	}
	quieroSobre := []string{"delivery_id", "event", "firing", "product", "severity", "title", "ts"}
	if claves := clavesDe(t, cuerpo); !slices.Equal(claves, quieroSobre) {
		t.Fatalf("claves del sobre %v, esperadas %v", claves, quieroSobre)
	}
	var doc struct {
		Event    string          `json:"event"`
		Severity string          `json:"severity"`
		Title    string          `json:"title"`
		TS       string          `json:"ts"`
		Firing   json.RawMessage `json:"firing"`
	}
	if err := json.Unmarshal(cuerpo, &doc); err != nil {
		t.Fatal(err)
	}
	quieroDisparo := []string{"alert_kind", "at", "device_id", "device_name", "reason", "rule_id", "rule_name", "severity", "value"}
	if claves := clavesDe(t, doc.Firing); !slices.Equal(claves, quieroDisparo) {
		t.Fatalf("claves del disparo %v, esperadas %v", claves, quieroDisparo)
	}
	var f map[string]any
	if err := json.Unmarshal(doc.Firing, &f); err != nil {
		t.Fatal(err)
	}
	quiero := map[string]any{
		"rule_id": "al-riesgo-alto", "rule_name": "Riesgo alto sostenido",
		"alert_kind": "risk_above", "device_id": "dev-7", "device_name": "Tablet almacén",
		"severity": "critical", "reason": "riesgo 88 (umbral 80)",
		"at": "2026-08-29T10:05:00Z", "value": float64(88),
	}
	for k, v := range quiero {
		if f[k] != v {
			t.Fatalf("firing.%s = %v, esperado %v", k, f[k], v)
		}
	}
	if doc.Event != EventAlertFired || doc.Severity != "critical" || doc.TS != "2026-08-29T10:05:00Z" {
		t.Fatalf("sobre inesperado: %s", cuerpo)
	}
	if !strings.Contains(doc.Title, "Riesgo alto sostenido") || !strings.Contains(doc.Title, "Tablet almacén") {
		t.Fatalf("el titular debería nombrar la regla y el dispositivo: %q", doc.Title)
	}
}

// TestNtfyDeUnaAlertaNombraLaRegla cierra el tercer formato de salida del
// quinto evento: el aviso de ntfy de un alert.fired.
func TestNtfyDeUnaAlertaNombraLaRegla(t *testing.T) {
	cuerpo := ntfyBody(eventoAlerta())
	for _, linea := range []string{"Regla: Riesgo alto sostenido", "Dispositivo: Tablet almacén", "Severidad: critical"} {
		if !strings.Contains(cuerpo, linea) {
			t.Fatalf("falta %q en el aviso:\n%s", linea, cuerpo)
		}
	}
}

// TestNativePayloadDeUnaAlertaConValorCeroLoSigueDeclarando: battery_below
// dispara con 0 % y storage_low con 0 GB, así que el valor observado 0 es un
// dato alcanzable y no un campo ausente.
func TestNativePayloadDeUnaAlertaConValorCeroLoSigueDeclarando(t *testing.T) {
	f := alertaDisparada()
	f.Kind, f.RuleID, f.RuleName = alert.KindBatteryBelow, "al-bateria", "Batería crítica"
	f.Reason, f.Value, f.Severity = "batería 0 % (umbral < 15 %)", 0, "high"
	ev := eventoAlerta()
	ev.Firing = f
	cuerpo, err := NativePayload(ev)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(cuerpo), `"value":0`) {
		t.Fatalf("un disparo con valor 0 debe declararlo, no omitirlo: %s", cuerpo)
	}
}
