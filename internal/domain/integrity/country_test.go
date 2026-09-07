package integrity

import (
	"math"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestCountryFlip(t *testing.T) {
	for _, tc := range []struct {
		name, from, to string
		km             float64
		flip           bool
	}{
		{"stationary", "es", "fr", 0, true},
		{"normalized", " ES ", "es", 0, false},
		{"missing previous", " ", "fr", 0, false},
		{"missing current", "es", "", 0, false},
		{"below", "es", "fr", 49.999, true},
		{"equal", "es", "fr", 50, false},
		{"above", "es", "fr", 50.001, false},
		{"travel", "es", "fr", 1050, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			prev := report(geo.Point{}, tc.from)
			prev.LastReportAt = now // country evidence does not require a positive interval
			cur := report(geo.Point{Lat: tc.km * 1000 / geo.EarthRadiusM * 180 / math.Pi}, tc.to)
			got := Assess(cur, &prev, now)
			if got.Suspicious != tc.flip || (tc.flip && (len(got.Checks) != 1 || got.Checks[0] != "country_flip_without_movement")) {
				t.Fatalf("flip: %+v", got)
			}
		})
	}
}
