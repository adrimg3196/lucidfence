package risk

import (
	"fmt"
	"math"
	"slices"
	"strconv"

	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
)

func integrityScore(sig Signal) (float64, []string) {
	checks := stringList(sig["checks"])
	speed := math.Trunc(metricNumber(sig["speed_kmh"]))
	if speed == 0 {
		speed = 0
	} // El entero textual cero no tiene signo.
	score := 0.0
	reasons := []string{}
	rules := []struct {
		check  string
		weight float64
		reason string
	}{
		{integrity.CheckImpossibleSpeed, 30, fmt.Sprintf("velocidad imposible entre reportes (%.0f km/h): posible spoofing de ubicación", speed)},
		{integrity.CheckCountryFlip, 15, "país declarado cambió sin movimiento acorde: metadatos de ubicación incoherentes"},
		{integrity.CheckAccuracyInvalid, 8, "precisión GPS inválida (accuracy ≤ 0): report no fiable"},
		{integrity.CheckAccuracyTooPerfect, 8, "precisión imposible para geolocalización por IP: campo falseado"},
	}
	for _, rule := range rules {
		if slices.Contains(checks, rule.check) {
			score += rule.weight
			reasons = append(reasons, rule.reason)
		}
	}
	return score, reasons
}

// Métrica ausente o no finita es neutral. El texto 0 km/h es una convención
// de explicación compatible, no una velocidad observada.
func metricNumber(v any) float64 {
	var n float64
	switch v := v.(type) {
	case int:
		n = float64(v)
	case float64:
		n = v
	}
	if math.IsNaN(n) || math.IsInf(n, 0) {
		return 0
	}
	return n
}

func zoneRouteScore(score float64, reasons []string, sig Signals) (float64, []string) {
	zone := metricNumber(sig["zone_risk"]["zone_risk"])
	if zone > 0 {
		// La conversión explícita fija el redondeo del producto antes de sumar;
		// impide fusionarlo con la suma en arquitecturas con FMA.
		score += float64(zone * 20)
		reasons = append(reasons, "zona de riesgo elevado ("+strconv.FormatFloat(zone, 'f', -1, 64)+")")
	}
	state, _ := sig["route_state"]["route_state"].(string)
	switch state {
	case "off_route":
		deviation := math.Max(0, metricNumber(sig["route_state"]["route_deviation_m"]))
		score += 25 + math.Min(25, math.Trunc(deviation/100))
		reasons = append(reasons, fmt.Sprintf("desviado de su ruta asignada (%.0f m)", math.Trunc(deviation)))
	case "on_route":
		score = math.Max(0, score-5)
	}
	return score, reasons
}

func stringList(v any) []string {
	switch v := v.(type) {
	case []string:
		return v
	case []any:
		out := []string{}
		for _, value := range v {
			if s, ok := value.(string); ok {
				out = append(out, s)
			}
		}
		return out
	default:
		return nil
	}
}
