package risk

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestHardwareUnexpectedTypeIsUnknown(t *testing.T) {
	for _, components := range []any{nil, 12, "battery", (*string)(nil)} {
		got := Evaluate(device.Device{}, Signals{"device_posture": {"hardware_degraded": true, "hardware_degraded_components": components}}, time.Time{})
		if len(got.Reasons) != 1 || got.Reasons[0] != "salud de hardware degradada ()" {
			t.Fatal(got.Reasons)
		}
	}
}
