package risk

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

func TestShiftUbicacionDesconocidaNoEsIncumplimiento(t *testing.T) {
	ctx := Context{ShiftZones: map[string]string{"d": "hq"}}
	for _, loc := range []*geo.Point{nil, {Lat: 91}} {
		d := device.Device{ID: "d", InsideFence: "hq", Location: device.Location{Point: loc}}
		transition.Evaluate(nil, &d, nil, noon)
		if d.FenceState != device.Unknown {
			t.Fatal("fixture no produce unknown")
		}
		s := Compute(d, ctx)
		metric(t, s, "shift_match", "shift_known", true)
		absent(t, s, "shift_match", "shift_match")
	}
	for _, d := range []device.Device{
		{ID: "d"},
		{ID: "d", FenceState: device.Unknown, InsideFence: "hq"},
		{ID: "d", FenceState: device.Inside},
	} {
		s := Compute(d, ctx)
		metric(t, s, "shift_match", "shift_known", true)
		absent(t, s, "shift_match", "shift_match")
	}
}

func TestShiftFueraObservadoSigueSiendoIncumplimiento(t *testing.T) {
	ctx := Context{ShiftZones: map[string]string{"d": "hq"}}
	d := device.Device{ID: "d", Location: device.Location{Point: &geo.Point{Lat: 40, Lng: -3}}}
	transition.Evaluate(nil, &d, nil, noon)
	if d.FenceState != device.Outside {
		t.Fatal("fixture no produce outside")
	}
	metric(t, Compute(d, ctx), "shift_match", "shift_match", false)
	metric(t, Compute(device.Device{ID: "d", FenceState: device.Inside, InsideFence: "hq"}, ctx), "shift_match", "shift_match", true)
	metric(t, Compute(device.Device{ID: "d", FenceState: device.Inside, InsideFence: "away"}, ctx), "shift_match", "shift_match", false)
}
