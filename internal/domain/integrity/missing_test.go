package integrity

import (
	"math"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestMissingEvidence(t *testing.T) {
	valid := report(geo.Point{}, "es")
	for _, p := range []*geo.Point{nil, {Lat: math.NaN()}, {Lng: math.Inf(1)}, {Lat: 91}, {Lng: 181}} {
		invalid := device.Device{Location: device.Location{Point: p}}
		for _, pair := range [][2]*device.Device{{&valid, nil}, {&valid, &invalid}, {&invalid, &valid}} {
			got := Assess(*pair[0], pair[1], now)
			if got.Suspicious || got.DistanceKM != nil || got.SpeedKMH != nil || got.Checks == nil {
				t.Fatalf("missing: %+v", got)
			}
		}
	}
}

func TestMissingOrNonpositiveClock(t *testing.T) {
	prev := report(geo.Point{}, "es")
	cur := report(geo.Point{Lat: 1}, "es")
	for _, at := range []time.Time{{}, now, now.Add(time.Second)} {
		prev.LastReportAt = at
		got := Assess(cur, &prev, now)
		if got.SpeedKMH != nil || got.DistanceKM == nil || got.Suspicious {
			t.Fatalf("clock %v: %+v", at, got)
		}
	}
}
