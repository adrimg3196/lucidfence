package integrity

import (
	"math"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestMovementThresholdsBeforeRounding(t *testing.T) {
	for _, tc := range []struct {
		name              string
		km, hours         float64
		speed, suspicious bool
	}{
		{"jitter", 0.3, 0.0001, false, false},
		{"below minimum", 4.999, 0.0001, false, false},
		{"minimum", 5, 1, true, false},
		{"urban", 11, 0.25, true, false},
		{"speed equal", 1000, 1, true, false},
		{"speed below", 999.999, 1, true, false},
		{"speed above", 1000.001, 1, true, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			prev := report(geo.Point{}, "es")
			prev.LastReportAt = now.Add(-time.Duration(tc.hours * float64(time.Hour)))
			cur := report(geo.Point{Lat: tc.km * 1000 / geo.EarthRadiusM * 180 / math.Pi}, "es")
			got := Assess(cur, &prev, now)
			if (got.SpeedKMH != nil) != tc.speed || got.Suspicious != tc.suspicious {
				t.Fatalf("threshold: %+v", got)
			}
		})
	}
}
