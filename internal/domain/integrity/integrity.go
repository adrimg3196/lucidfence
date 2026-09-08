// Package integrity evalúa evidencia de ubicación sin I/O ni enforcement.
package integrity

import (
	"math"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

const (
	CoarseIPMinAccuracyM    = 100.0
	SourceCoarseIP          = "coarse_ip"
	CheckAccuracyInvalid    = "accuracy_invalid"
	CheckAccuracyTooPerfect = "accuracy_too_perfect"
	CountryFlipMaxKM        = 50.0
	CheckCountryFlip        = "country_flip_without_movement"
	ImpossibleSpeedKMH      = 1000.0
	MinDistanceKM           = 5.0
	CheckImpossibleSpeed    = "impossible_speed"
)

// Assess compara reports usando exclusivamente el reloj propio LastReportAt.
// No muta entradas. Datos ausentes/no finitos no son evidencia negativa;
// Checks siempre es una lista, ordenada por velocidad, país y precisión.
func Assess(cur device.Device, prev *device.Device, now time.Time) device.Integrity {
	out := movement(cur, prev, now)
	if check := accuracy(cur.Location); check != "" {
		out.Checks = append(out.Checks, check)
	}
	out.Suspicious = len(out.Checks) > 0
	return out
}

func accuracy(location device.Location) string {
	if location.AccuracyM == nil || math.IsNaN(*location.AccuracyM) || math.IsInf(*location.AccuracyM, 0) {
		return ""
	}
	if *location.AccuracyM <= 0 {
		return CheckAccuracyInvalid
	}
	if location.Source == SourceCoarseIP && *location.AccuracyM < CoarseIPMinAccuracyM {
		return CheckAccuracyTooPerfect
	}
	return ""
}

func movement(cur device.Device, prev *device.Device, now time.Time) device.Integrity {
	out := device.Integrity{Checks: []string{}}
	if prev == nil || prev.Location.Point == nil || cur.Location.Point == nil || prev.Location.Point.Valid() != nil || cur.Location.Point.Valid() != nil {
		return out
	}
	km := geo.HaversineM(*prev.Location.Point, *cur.Location.Point) / 1000
	// Redondear solo la presentación: nunca mover un dato a través del umbral.
	distance := math.Round(km*100) / 100
	out.DistanceKM = &distance
	if km >= MinDistanceKM && !prev.LastReportAt.IsZero() && now.After(prev.LastReportAt) {
		kmh := km / now.Sub(prev.LastReportAt).Hours()
		speed := math.Round(kmh*10) / 10
		out.SpeedKMH = &speed
		if kmh > ImpossibleSpeedKMH {
			out.Checks = append(out.Checks, CheckImpossibleSpeed)
		}
	}
	from, to := strings.ToLower(strings.TrimSpace(prev.Posture.Country)), strings.ToLower(strings.TrimSpace(cur.Posture.Country))
	if from != "" && to != "" && from != to && km < CountryFlipMaxKM {
		out.Checks = append(out.Checks, CheckCountryFlip)
	}
	return out
}
