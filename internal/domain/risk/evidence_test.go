package risk

import (
	"encoding/json"
	"math"
	"reflect"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestIntegrityReexpuestaSinInferencia(t *testing.T) {
	for _, checks := range [][]string{nil, {}, {"impossible_speed", "low_accuracy"}} {
		d := device.Device{LocationIntegrity: device.Integrity{Suspicious: true, Checks: checks,
			SpeedKMH: ptr(0.0), DistanceKM: ptr(12.0)}}
		s := sig(d)
		metric(t, s, "location_integrity", "suspicious", true)
		if !reflect.DeepEqual(s["location_integrity"]["checks"], checks) {
			t.Fatalf("checks pierde null/vacío/evidencia: %#v", s)
		}
		metric(t, s, "location_integrity", "speed_kmh", 0.0)
		metric(t, s, "location_integrity", "distance_km", 12.0)
		if len(checks) > 0 {
			s["location_integrity"]["checks"].([]string)[0] = "mutado"
			if checks[0] != "impossible_speed" {
				t.Fatal("checks comparte memoria")
			}
		}
	}
	unknown := sig(device.Device{})
	absent(t, unknown, "location_integrity", "speed_kmh")
	absent(t, unknown, "location_integrity", "distance_km")
	metric(t, unknown, "location_integrity", "suspicious", false)
	data, err := json.Marshal(unknown["location_integrity"])
	if err != nil || string(data) != `{"checks":null,"suspicious":false}` {
		t.Fatalf("sin evaluar no es lista de checks superados: %s, %v", data, err)
	}
}

func TestZonaRutaDefaultsYValores(t *testing.T) {
	ctx := Context{ZoneRisk: map[string]float64{"port": 0.8, "": 0.9}}
	for _, zone := range []string{"", "missing", "port"} {
		want := 0.0
		if zone == "port" {
			want = 0.8
		}
		metric(t, Compute(device.Device{InsideFence: zone}, ctx), "zone_risk", "zone_risk", want)
	}
	for _, state := range []device.RouteState{"", device.Unassigned, device.OnRoute, device.OffRoute} {
		d := device.Device{RouteState: state, RouteID: "r-1", RouteDeviationM: ptr(420.5)}
		s := sig(d)
		metric(t, s, "route_state", "route_state", string(state))
		metric(t, s, "route_state", "route_id", "r-1")
		metric(t, s, "route_state", "route_deviation_m", 420.5)
	}
	metric(t, sig(device.Device{}), "route_state", "route_deviation_m", 0.0)
	metric(t, sig(device.Device{}), "route_state", "route_id", "")
}

func TestMetricasNoFinitasNoRompenJSON(t *testing.T) {
	for _, value := range []float64{math.NaN(), math.Inf(1), math.Inf(-1)} {
		d := device.Device{InsideFence: "hq", RouteDeviationM: &value,
			LocationIntegrity: device.Integrity{SpeedKMH: &value, DistanceKM: &value}}
		s := Compute(d, Context{ZoneRisk: map[string]float64{"hq": value}})
		absent(t, s, "location_integrity", "speed_kmh")
		absent(t, s, "location_integrity", "distance_km")
		metric(t, s, "zone_risk", "zone_risk", 0.0)
		metric(t, s, "route_state", "route_deviation_m", 0.0)
		if _, err := json.Marshal(s); err != nil {
			t.Fatal(err)
		}
	}
}

func TestValueRawRoundTripNullYCeros(t *testing.T) {
	s := Signals{"null": nil, "empty": {}, "values": {"null": nil, "false": false, "zero": 0, "list": []string{"a"}}}
	absent(t, s, "missing", "x")
	absent(t, s, "null", "x")
	absent(t, s, "values", "missing")
	absent(t, s, "values", "null")
	metric(t, s, "values", "false", false)
	metric(t, s, "values", "zero", 0)
	raw := s.Raw()
	if raw["null"] != nil || raw["empty"] == nil {
		t.Fatalf("null/vacío perdido: %#v", raw)
	}
	d := device.Device{Signals: raw}
	data, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	var restored device.Device
	if err := json.Unmarshal(data, &restored); err != nil {
		t.Fatal(err)
	}
	got, err := json.Marshal(restored.Signals)
	want, wantErr := json.Marshal(s)
	if err != nil || wantErr != nil || string(got) != string(want) {
		t.Fatalf("round trip: %s != %s (%v/%v)", got, want, err, wantErr)
	}
	raw["values"]["false"] = true
	raw["values"]["list"].([]string)[0] = "mutado"
	metric(t, s, "values", "false", false)
	metric(t, s, "values", "list", []string{"a"})
	if Signals(nil).Raw() != nil {
		t.Fatal("Raw nil debe conservar null")
	}
}

func TestValueNullTipadoConservaUnknownTrasJSON(t *testing.T) {
	for _, value := range []any{[]string(nil), []any(nil), map[string]any(nil), (*bool)(nil)} {
		s := Signals{"test": {"unknown": value}}
		absent(t, s, "test", "unknown")
		data, err := json.Marshal(s)
		if err != nil {
			t.Fatal(err)
		}
		var decoded Signals
		if err := json.Unmarshal(data, &decoded); err != nil {
			t.Fatal(err)
		}
		absent(t, decoded, "test", "unknown")
	}
	absent(t, sig(device.Device{}), "location_integrity", "checks")
	metric(t, sig(device.Device{LocationIntegrity: device.Integrity{Checks: []string{}}}), "location_integrity", "checks", []string{})
}

func TestComputeNoMutaEntradaNiComparteResultados(t *testing.T) {
	d := device.Device{Posture: device.Posture{HardwareHealth: map[string]string{"uwb": "failed"}},
		LocationIntegrity: device.Integrity{Checks: []string{"low_accuracy"}}, Signals: map[string]map[string]any{"old": {"x": false}}}
	ctx := Context{Now: noon, ShiftZones: map[string]string{"d": "hq"}, ZoneRisk: map[string]float64{"hq": 0.8}}
	before, _ := json.Marshal(d)
	ctxBefore, _ := json.Marshal(ctx)
	first, second := Compute(d, ctx), Compute(d, ctx)
	if !reflect.DeepEqual(first, second) {
		t.Fatal("cálculo no determinista")
	}
	after, _ := json.Marshal(d)
	ctxAfter, _ := json.Marshal(ctx)
	if string(before) != string(after) || string(ctxBefore) != string(ctxAfter) {
		t.Fatal("Compute muta entrada")
	}
	first["location_integrity"]["checks"].([]string)[0] = "mutado"
	first["device_posture"]["hardware_degraded_components"].([]string)[0] = "mutado"
	metric(t, second, "location_integrity", "checks", []string{"low_accuracy"})
	metric(t, second, "device_posture", "hardware_degraded_components", []string{"uwb"})
}
