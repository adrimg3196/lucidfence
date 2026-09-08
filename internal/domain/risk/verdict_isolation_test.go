package risk

import (
	"encoding/json"
	"math"
	"reflect"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
)

func TestShiftRawJSONObservedOutside(t *testing.T) {
	ctx := DefaultContext(noon)
	ctx.ShiftZones = map[string]string{"d": "hq"}
	for _, state := range []device.FenceState{device.Unknown, device.Outside} {
		d := device.Device{ID: "d", FenceState: state}
		sig := Compute(d, ctx)
		want := 20.0
		if state == device.Outside {
			want = 55
		}
		for _, variant := range []Signals{sig, rehydrate(t, sig)} {
			got := Evaluate(d, variant, noon)
			if *got.Score != want {
				t.Fatalf("%s score=%v", state, *got.Score)
			}
		}
	}
	for _, match := range []any{nil, (*bool)(nil), "false", false, true} {
		sig := Signals{"shift_match": {"shift_known": true, "shift_match": match}}
		for _, variant := range []Signals{sig, rehydrate(t, sig)} {
			got := Evaluate(device.Device{}, variant, noon)
			want := 0.0
			if v, ok := match.(bool); ok && !v {
				want = 20
			}
			if *got.Score != want {
				t.Fatalf("match=%v score=%v", match, *got.Score)
			}
		}
	}
}

func rehydrate(t *testing.T, sig Signals) Signals {
	t.Helper()
	b, err := json.Marshal(sig.Raw())
	if err != nil {
		t.Fatal(err)
	}
	var got Signals
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatal(err)
	}
	return got
}

func TestVerdictSignalsRoundtripAndDeterminism(t *testing.T) {
	sig := Signals{"location_integrity": {"checks": []string{integrity.CheckImpossibleSpeed}, "speed_kmh": 1234}, "zone_risk": {"zone_risk": 0.35}, "device_posture": {"hardware_degraded": true, "hardware_degraded_components": []string{"battery", "storage"}}}
	d := device.Device{FenceState: device.Outside, Signals: sig.Raw()}
	before, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	at := noon.In(time.FixedZone("local", -18000))
	want := Evaluate(d, sig, at)
	if got := Evaluate(d, rehydrate(t, sig), at); !reflect.DeepEqual(got, want) {
		t.Fatalf("roundtrip %v != %v", got, want)
	}
	var wg sync.WaitGroup
	for range 20 {
		wg.Go(func() {
			for range 50 {
				got := Evaluate(d, sig, at)
				if !reflect.DeepEqual(got, want) {
					t.Error("not deterministic")
				}
			}
		})
	}
	wg.Wait()
	after, err := json.Marshal(d)
	if err != nil || string(before) != string(after) {
		t.Fatal("device mutated", err)
	}
	if !reflect.DeepEqual(sig.Raw(), d.Signals) {
		t.Fatal("signals mutated")
	}
}

func TestUnexpectedSignalsRemainNeutral(t *testing.T) {
	for _, v := range []any{nil, (*bool)(nil), "true", 42, math.NaN(), math.Inf(1), []string{"true"}} {
		sig := Signals{"device_health": {"compliant": v, "rooted": v, "os_outdated": v}, "device_posture": {"disk_low": v, "battery_critical": v, "encryption_off": v}, "time_of_day": {"off_hours": v}, "shift_match": {"shift_known": v, "shift_match": v}, "location_integrity": {"checks": v, "speed_kmh": v}}
		got := Evaluate(device.Device{}, sig, noon)
		if *got.Score != 0 || len(got.Reasons) != 0 || got.Verified {
			t.Fatal(got)
		}
	}
	if Severity(math.Inf(1)) != "critical" || Severity(math.Inf(-1)) != "low" {
		t.Fatal("infinity thresholds")
	}
}
