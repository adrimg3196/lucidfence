package risk

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestVerdictShiftExplicitEvidence(t *testing.T) {
	var missing *bool
	cases := []struct {
		name         string
		known, match any
		want         float64
	}{
		{"explicit mismatch", true, false, 20},
		{"match", true, true, 0},
		{"absent", true, nil, 0},
		{"typed nil", true, missing, 0},
		{"unexpected", true, "false", 0},
		{"unknown shift", false, false, 0},
		{"unknown known", nil, false, 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			sig := Signals{"shift_match": {"shift_known": tc.known, "shift_match": tc.match}}
			got := Evaluate(device.Device{}, sig, time.Time{})
			if got.Score == nil || *got.Score != tc.want {
				t.Fatalf("score=%v want %v", got.Score, tc.want)
			}
			if tc.want > 0 && (len(got.Reasons) != 1 || got.Reasons[0] != "dispositivo fuera de su turno asignado") {
				t.Fatalf("reasons=%v", got.Reasons)
			}
		})
	}
}

func TestVerdictOffHoursBeforeShift(t *testing.T) {
	sig := Signals{"time_of_day": {"off_hours": true}, "shift_match": {"shift_known": true, "shift_match": false}}
	got := Evaluate(device.Device{}, sig, time.Time{})
	if *got.Score != 30 || len(got.Reasons) != 2 {
		t.Fatalf("got=%+v score=%v", got, *got.Score)
	}
	if got.Reasons[0] != "fuera de horario laboral" || got.Reasons[1] != "dispositivo fuera de su turno asignado" {
		t.Fatal(got.Reasons)
	}
}
