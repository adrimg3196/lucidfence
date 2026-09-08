package integrity

import (
	"math"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestAccuracyEvidenceIndependentOfPosition(t *testing.T) {
	for _, tc := range []struct {
		name, source string
		accuracy     float64
		check        string
	}{
		{"zero", "gps", 0, "accuracy_invalid"},
		{"negative", "coarse_ip", -1, "accuracy_invalid"},
		{"too perfect", "coarse_ip", 5, "accuracy_too_perfect"},
		{"below", "coarse_ip", 99.999, "accuracy_too_perfect"},
		{"equal", "coarse_ip", 100, ""},
		{"above", "coarse_ip", 500, ""},
		{"GPS", "gps", 5, ""},
		{"unknown source", "", 5, ""},
		{"NaN", "coarse_ip", math.NaN(), ""},
		{"positive infinity", "coarse_ip", math.Inf(1), ""},
		{"negative infinity", "coarse_ip", math.Inf(-1), ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got := Assess(device.Device{Location: device.Location{Source: tc.source, AccuracyM: &tc.accuracy}}, nil, now)
			if got.Suspicious != (tc.check != "") || (tc.check != "" && (len(got.Checks) != 1 || got.Checks[0] != tc.check)) {
				t.Fatalf("accuracy: %+v", got)
			}
		})
	}
}
