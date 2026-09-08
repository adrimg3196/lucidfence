package device

import (
	"encoding/json"
	"testing"
	"time"
)

func TestDwellYSignalsContratoJSON(t *testing.T) {
	const fixture = `{"id":"prueba","fence_state_since":"2026-09-08T08:00:00Z","dwell_seconds":90,"signals":{"posture":{"rooted":false,"score":0,"unknown":null,"checks":["dato"]}}}`
	var d Device
	if err := json.Unmarshal([]byte(fixture), &d); err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	var got map[string]json.RawMessage
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatal(err)
	}
	if string(got["signals"]) != `{"posture":{"checks":["dato"],"rooted":false,"score":0,"unknown":null}}` {
		t.Fatalf("señales pasivas perdidas: %s", b)
	}
	if d.DwellSeconds != 90 || d.FenceStateSince == nil || !d.FenceStateSince.Equal(time.Date(2026, 9, 8, 8, 0, 0, 0, time.UTC)) {
		t.Fatalf("reloj perdido: %s", b)
	}
}

func TestDwellJSONM1NoInventaOrigenNiSignals(t *testing.T) {
	var d Device
	if err := json.Unmarshal([]byte(`{"id":"M1"}`), &d); err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	var got map[string]json.RawMessage
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatal(err)
	}
	if got["signals"] != nil || got["fence_state_since"] != nil || string(got["dwell_seconds"]) != "0" {
		t.Fatalf("sin evaluar no hay origen ni señales: %s", b)
	}
}
