package risk

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
)

func TestIntegrityIsolatedWeights(t *testing.T) {
	for _, tc := range []struct {
		check string
		want  float64
	}{
		{integrity.CheckImpossibleSpeed, 30}, {integrity.CheckCountryFlip, 15},
		{integrity.CheckAccuracyInvalid, 8}, {integrity.CheckAccuracyTooPerfect, 8},
	} {
		t.Run(tc.check, func(t *testing.T) {
			got := Evaluate(device.Device{}, Signals{"location_integrity": {"checks": []string{tc.check, tc.check}}}, time.Time{})
			if *got.Score != tc.want || len(got.Reasons) != 1 {
				t.Fatal(got)
			}
		})
	}
}

func TestVerdictSignalNamesMatchRegistry(t *testing.T) {
	want := []string{"time_of_day", "shift_match", "device_health", "device_posture", "location_integrity", "zone_risk", "route_state"}
	if !reflect.DeepEqual(Names, want) {
		t.Fatalf("consumer names need review: %v", Names)
	}
}

func TestVerdictAllBlocksKeepReasonsAfterClamp(t *testing.T) {
	sig := Signals{"device_health": {"compliant": false}, "device_posture": {"disk_low": true}, "location_integrity": {"checks": []string{integrity.CheckAccuracyInvalid}}, "time_of_day": {"off_hours": true}, "shift_match": {"shift_known": true, "shift_match": false}, "zone_risk": {"zone_risk": 1}, "route_state": {"route_state": "off_route"}}
	got := Evaluate(device.Device{FenceState: device.Outside}, sig, noon)
	want := []string{"fuera de geocerca permitida", "dispositivo no conforme", "disco casi lleno (<10% libre)", "precisión GPS inválida (accuracy ≤ 0): report no fiable", "fuera de horario laboral", "dispositivo fuera de su turno asignado", "zona de riesgo elevado (1)", "desviado de su ruta asignada (0 m)"}
	if *got.Score != 100 || !reflect.DeepEqual(got.Reasons, want) {
		t.Fatal(got)
	}
}
