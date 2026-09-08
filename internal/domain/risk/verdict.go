package risk

import (
	"math"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// Severity clasifica el score recibido; Evaluate la aplica después de redondear.
func Severity(score float64) string {
	switch {
	case math.IsNaN(score):
		return "unknown"
	case score >= 80:
		return "critical"
	case score >= 55:
		return "high"
	case score >= 30:
		return "medium"
	default:
		return "low"
	}
}

// Evaluate consume evidencia ya calculada, sin I/O, reloj global ni mutación.
// MatchedPolicies queda vacío hasta incorporar políticas, fuera de este cálculo.
func Evaluate(d device.Device, sig Signals, at time.Time) device.Verdict {
	score, reasons := accumulate(d, sig)
	score = roundTenth(math.Max(0, math.Min(100, score)))
	reasons, provenance, verified := evidenceGate(score, reasons)
	at = at.UTC()
	return device.Verdict{Score: &score, Severity: Severity(score), Reasons: reasons,
		MatchedPolicies: []string{}, EvaluatedAt: &at, Provenance: provenance, Verified: verified}
}

func accumulate(d device.Device, sig Signals) (float64, []string) {
	score := 0.0
	reasons := []string{}
	switch d.FenceState {
	case device.Outside:
		score = 35
		reasons = append(reasons, "fuera de geocerca permitida")
	case device.Unknown:
		score = 20
		reasons = append(reasons, "ubicación desconocida (señal perdida)")
	}
	score, reasons = healthScore(score, reasons, sig)
	score, reasons = postureScore(score, reasons, sig)
	integrityPoints, integrityReasons := integrityScore(sig["location_integrity"])
	score += integrityPoints
	reasons = append(reasons, integrityReasons...)
	if off, ok := sig["time_of_day"]["off_hours"].(bool); ok && off {
		score += 10
		reasons = append(reasons, "fuera de horario laboral")
	}
	known, _ := sig["shift_match"]["shift_known"].(bool)
	match, explicit := sig["shift_match"]["shift_match"].(bool)
	if known && explicit && !match {
		score += 20
		reasons = append(reasons, "dispositivo fuera de su turno asignado")
	}
	return zoneRouteScore(score, reasons, sig)
}

func healthScore(score float64, reasons []string, sig Signals) (float64, []string) {
	if dh, ok := sig["device_health"]; ok {
		if c, ok := dh["compliant"].(bool); ok && !c {
			score += 25
			reasons = append(reasons, "dispositivo no conforme")
		}
		if r, ok := dh["rooted"].(bool); ok && r {
			score += 15
			reasons = append(reasons, "dispositivo con root/jailbreak")
		}
		if o, ok := dh["os_outdated"].(bool); ok && o {

			score += 10
			reasons = append(reasons, "SO desactualizado")
		}
	}
	return score, reasons
}

func postureScore(score float64, reasons []string, sig Signals) (float64, []string) {
	osOutdated, _ := sig["device_health"]["os_outdated"].(bool)
	dp := sig["device_posture"]
	rules := []struct {
		key    string
		weight float64
		reason string
	}{
		{"disk_low", 8, "disco casi lleno (<10% libre)"},
		{"battery_critical", 6, "batería crítica (≤15%)"},
		{"os_unpatched", 12, "SO sin parchear de seguridad"},
		{"encryption_off", 15, "almacenamiento sin cifrar"},
		{"lockdown_mode_off", 10, "Lockdown Mode desactivado"},
		{"unsupervised", 10, "dispositivo sin supervisión (enrolamiento personal)"},
		{"hardware_degraded", 10, "salud de hardware degradada (" + strings.Join(stringList(dp["hardware_degraded_components"]), ", ") + ")"},
		{"osquery_config_invalid", 8, "configuración de osquery no válida"},
	}
	for _, rule := range rules {
		v, _ := dp[rule.key].(bool)
		if v && (rule.key != "os_unpatched" || !osOutdated) {
			score += rule.weight
			reasons = append(reasons, rule.reason)
		}
	}
	return score, reasons
}
