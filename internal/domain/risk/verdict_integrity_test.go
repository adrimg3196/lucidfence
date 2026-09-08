package risk

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
)

func TestVerdictIntegrityMembershipOrder(t *testing.T) {
	checks := []string{integrity.CheckAccuracyTooPerfect, integrity.CheckCountryFlip, integrity.CheckImpossibleSpeed, integrity.CheckAccuracyInvalid, integrity.CheckImpossibleSpeed}
	sig := Signals{"location_integrity": {"checks": checks, "speed_kmh": 1234.9, "suspicious": false}}
	got := Evaluate(device.Device{}, sig, time.Time{})
	want := []string{"velocidad imposible entre reportes (1234 km/h): posible spoofing de ubicación", "país declarado cambió sin movimiento acorde: metadatos de ubicación incoherentes", "precisión GPS inválida (accuracy ≤ 0): report no fiable", "precisión imposible para geolocalización por IP: campo falseado"}
	if *got.Score != 61 || !reflect.DeepEqual(got.Reasons, want) {
		t.Fatalf("score=%v reasons=%v", *got.Score, got.Reasons)
	}
}

func TestVerdictIntegrityUnknownMetric(t *testing.T) {
	sig := Signals{"location_integrity": {"checks": []any{nil, 5, integrity.CheckImpossibleSpeed}}}
	got := Evaluate(device.Device{}, sig, time.Time{})
	if *got.Score != 30 || len(got.Reasons) != 1 || got.Reasons[0] != "velocidad imposible entre reportes (0 km/h): posible spoofing de ubicación" {
		t.Fatalf("%+v score=%v", got, *got.Score)
	}
	sig = Signals{"location_integrity": {"suspicious": true}}
	got = Evaluate(device.Device{}, sig, time.Time{})
	if *got.Score != 0 || len(got.Reasons) != 0 {
		t.Fatal(got)
	}
}
