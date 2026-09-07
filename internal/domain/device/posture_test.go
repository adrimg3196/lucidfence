package device

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

func TestPosturaConocidaConservaJSON(t *testing.T) {
	for _, state := range []bool{false, true} {
		want := map[string]any{
			"rooted": state, "os_outdated": state, "osquery_config_valid": state,
			"hardware_health": map[string]any{"battery": "degraded", "disk": "ok"},
			"country":         "es", "site": "hq-madrid",
		}
		raw, err := json.Marshal(map[string]any{"id": "dev-1", "posture": want})
		if err != nil {
			t.Fatal(err)
		}
		var d Device
		if err := json.Unmarshal(raw, &d); err != nil {
			t.Fatal(err)
		}
		encoded, err := json.Marshal(d)
		if err != nil {
			t.Fatal(err)
		}
		var back map[string]any
		if err := json.Unmarshal(encoded, &back); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(back["posture"], want) {
			t.Fatalf("postura (incluido false) perdida: got=%v want=%v", back["posture"], want)
		}
	}
}

func TestPosturaDesconocidaYCompatibilidadM1(t *testing.T) {
	for _, raw := range []string{
		`{"id":"legacy"}`, `{"id":"legacy","posture":{}}`, `{"id":"legacy","posture":null}`,
		`{"id":"legacy","posture":{"rooted":null,"os_outdated":null,"osquery_config_valid":null,"hardware_health":null}}`,
	} {
		var d Device
		if err := json.Unmarshal([]byte(raw), &d); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(d.Posture, Posture{}) {
			t.Fatalf("lo desconocido no es false ni un mapa inventado: %+v", d.Posture)
		}
		encoded, err := json.Marshal(d)
		if err != nil {
			t.Fatal(err)
		}
		for _, want := range []string{`"id":"legacy"`, `"posture":{}`, `"compliant":null`, `"score":null`} {
			if !strings.Contains(string(encoded), want) {
				t.Fatalf("JSON %s sin %s", encoded, want)
			}
		}
	}
}

func TestPosturaParcialNoCompletaLoDesconocido(t *testing.T) {
	var d Device
	if err := json.Unmarshal([]byte(`{"posture":{"rooted":false,"hardware_health":{"disk":"ok"}}}`), &d); err != nil {
		t.Fatal(err)
	}
	if d.Posture.Rooted == nil || *d.Posture.Rooted || d.Posture.OSOutdated != nil || d.Posture.OsqueryConfigValid != nil {
		t.Fatalf("false conocido y campos desconocidos deben distinguirse: %+v", d.Posture)
	}
	if _, ok := d.Posture.HardwareHealth["battery"]; ok {
		t.Fatal("una métrica ausente no se debe inventar")
	}
	encoded, err := json.Marshal(d.Posture)
	if err != nil {
		t.Fatal(err)
	}
	if string(encoded) != `{"rooted":false,"hardware_health":{"disk":"ok"}}` {
		t.Fatalf("postura parcial alterada: %s", encoded)
	}
}
