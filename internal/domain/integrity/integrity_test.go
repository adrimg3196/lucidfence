package integrity

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

var now = time.Date(2026, 9, 7, 12, 0, 0, 0, time.UTC)

func TestCombinedChecksStableAndInputsUnchanged(t *testing.T) {
	prev := report(geo.Point{}, "es")
	prev.LastReportAt = now.Add(-time.Second)
	cur := report(geo.Point{Lat: 0.1}, "fr")
	m := 5.0
	cur.Location.Source, cur.Location.AccuracyM = "coarse_ip", &m
	beforeCur, beforePrev := cur, prev
	got := Assess(cur, &prev, now)
	want := []string{"impossible_speed", "country_flip_without_movement", "accuracy_too_perfect"}
	if !reflect.DeepEqual(got.Checks, want) {
		t.Fatalf("checks: %v", got.Checks)
	}
	if !reflect.DeepEqual(cur, beforeCur) || !reflect.DeepEqual(prev, beforePrev) || m != 5 {
		t.Fatal("inputs mutated")
	}
}

func report(p geo.Point, country string) device.Device {
	return device.Device{Location: device.Location{Point: &p}, Posture: device.Posture{Country: country}, LastReportAt: now.Add(-15 * time.Minute)}
}

func TestTeleportUsesOwnClock(t *testing.T) {
	prev := report(geo.Point{Lat: 40.4168, Lng: -3.7038}, "es")
	cur := report(geo.Point{Lat: -34.6037, Lng: -58.3816}, "ar")
	cur.Location.ObservedAt = now.Add(-24 * time.Hour)
	got := Assess(cur, &prev, now)
	if !got.Suspicious || len(got.Checks) != 1 || got.Checks[0] != "impossible_speed" {
		t.Fatalf("teleport: %+v", got)
	}
	if got.SpeedKMH == nil || *got.SpeedKMH < 36000 || got.DistanceKM == nil || *got.DistanceKM < 9000 {
		t.Fatalf("metrics: %+v", got)
	}
}
