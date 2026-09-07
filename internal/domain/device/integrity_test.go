package device

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestIntegrityUnknownAndZeroMetrics(t *testing.T) {
	for _, raw := range []string{
		`{"suspicious":false,"checks":null}`,
		`{"suspicious":false,"checks":[]}`,
		`{"suspicious":false,"checks":[],"speed_kmh":0,"distance_km":0}`,
	} {
		var v Integrity
		if err := json.Unmarshal([]byte(raw), &v); err != nil {
			t.Fatal(err)
		}
		b, err := json.Marshal(v)
		if err != nil || string(b) != raw {
			t.Fatalf("round trip %s: %s, %v", raw, b, err)
		}
	}
}

func TestIntegrityJSONRoundTrip(t *testing.T) {
	raw := `{"location_integrity":{"suspicious":true,"checks":["impossible_speed"],"speed_kmh":40000,"distance_km":10050.5}}`
	var d Device
	if err := json.Unmarshal([]byte(raw), &d); err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	var got, want map[string]any
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal([]byte(raw), &want); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got["location_integrity"], want["location_integrity"]) {
		t.Fatalf("integrity lost: %s", b)
	}
}
