package policy_test

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/google/go-cmp/cmp"
)

func ptr[T any](v T) *T { return &v }

func TestCadaCampoDelCatalogoResuelve(t *testing.T) {
	d := device.Device{Platform: "android", FenceState: device.Outside, RouteState: device.OffRoute,
		Compliant: ptr(false), InsideFence: "sede", RouteDeviationM: ptr(501.0), DwellSeconds: 900,
		Inventory: device.Inventory{BatteryLevel: ptr(42), StorageFreeGB: ptr(12.5), EncryptionEnabled: ptr(true), Department: "ventas", Ownership: "company"},
		Posture:   device.Posture{Rooted: ptr(false), Country: "ES"}}
	s := policy.NewSubject(d, device.Verdict{Score: ptr(55.0), Severity: "high"}, nil)
	wants := map[string]any{"risk_score": 55.0, "severity": "high", "fence_state": "outside", "route_state": "off_route", "compliant": false, "platform": "android", "inside_fence": "sede", "route_deviation_m": 501.0, "dwell_seconds": 900, "inventory.battery_level": 42, "inventory.storage_free_gb": 12.5, "inventory.encryption_enabled": true, "inventory.department": "ventas", "inventory.ownership": "company", "posture.rooted": false, "posture.country": "ES"}
	if len(policy.Fields) != len(wants) {
		t.Fatal("catálogo incompleto")
	}
	seen := map[string]bool{}
	for _, field := range policy.Fields {
		want, exists := wants[field]
		got, ok := policy.Resolve(s, field)
		if !exists || seen[field] || !ok || !cmp.Equal(got, want) {
			t.Errorf("%s=%v,%v; want %v", field, got, ok, want)
		}
		seen[field] = true
	}
}

func TestLoDesconocidoNuncaCasa(t *testing.T) {
	s := policy.NewSubject(device.Device{}, risk.Failed(nil, time.Time{}), nil)
	for _, field := range append(append([]string{}, policy.Fields...), "missing", "inventory.missing", "posture.missing", "signal:x", "signal:.x", "signal:x.", "signal:x.y") {
		if field == "dwell_seconds" {
			continue
		}
		if field == "severity" {
			continue
		} // "unknown" es la etiqueta explícita de Failed.
		for _, op := range []policy.Op{policy.OpEq, policy.OpNe, policy.OpIn, policy.OpGte} {
			if (policy.Condition{Field: field, Op: op, Value: 0}).Match(s) {
				t.Errorf("%s %s unknown casa", field, op)
			}
		}
	}
	if !(policy.Condition{Field: "dwell_seconds", Op: policy.OpEq, Value: 0}).Match(s) {
		t.Fatal("cero observado")
	}
}

func TestCondicionesSobreSenales(t *testing.T) {
	d := device.Device{Posture: device.Posture{Rooted: ptr(false)}}
	signals := risk.Compute(d, risk.DefaultContext(time.Time{}))
	d.Signals = signals.Raw()
	raw, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	var restored device.Device
	if err := json.Unmarshal(raw, &restored); err != nil {
		t.Fatal(err)
	}
	hydrated := risk.Signals{}
	for name, sig := range restored.Signals {
		hydrated[name] = risk.Signal(sig)
	}
	for _, sig := range []risk.Signals{signals, hydrated} {
		s := policy.NewSubject(d, device.Verdict{}, sig)
		if !(policy.Condition{Field: "signal:device_health.rooted", Op: policy.OpEq, Value: false}).Match(s) {
			t.Fatal("false desaparece")
		}
		if (policy.Condition{Field: "signal:shift_match.shift_match", Op: policy.OpNe, Value: true}).Match(s) {
			t.Fatal("sin turno no acredita desajuste")
		}
	}
}
