package risk

import (
	"math"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestVerdictPythonRounding(t *testing.T) {
	cases := []struct {
		zone      float64
		outside   bool
		compliant bool
		want      float64
		severity  string
	}{
		{0.0125, false, false, 0.2, "low"}, {0.0575, false, false, 1.2, "low"},
		{0.9975, true, false, 55, "high"}, {0.9975, true, true, 80, "critical"},
	}
	for _, tc := range cases {
		sig := Signals{"zone_risk": {"zone_risk": tc.zone}}
		d := device.Device{}
		if tc.outside {
			d.FenceState = device.Outside
		}
		if tc.compliant {
			sig["device_health"] = Signal{"compliant": false}
		}
		got := Evaluate(d, sig, time.Time{})
		if *got.Score != tc.want || got.Severity != tc.severity {
			t.Errorf("zone=%v score=%v severity=%s want=%v/%s", tc.zone, *got.Score, got.Severity, tc.want, tc.severity)
		}
	}
}

func TestVerdictSeverityNaN(t *testing.T) {
	if got := Severity(math.NaN()); got != "unknown" {
		t.Fatalf("got %s", got)
	}
}
