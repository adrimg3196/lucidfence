package risk

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
)

func TestSpeedTruncatesNegativeFractionToIntegerZero(t *testing.T) {
	sig := Signals{"location_integrity": {"checks": []string{integrity.CheckImpossibleSpeed}, "speed_kmh": -0.2}}
	got := Evaluate(device.Device{}, sig, time.Time{})
	if got.Reasons[0] != "velocidad imposible entre reportes (0 km/h): posible spoofing de ubicación" {
		t.Fatal(got.Reasons)
	}
}
