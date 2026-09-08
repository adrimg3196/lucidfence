package risk

import (
	"math"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// Severities contiene los niveles evaluados en orden ascendente, sin unknown.
// Los consumidores no deben modificar el registro.
var Severities = []string{"low", "medium", "high", "critical"}

// Failed preserva el fallo total como desconocido, nunca como score cero sano.
func Failed(err error, at time.Time) device.Verdict {
	message := "error desconocido"
	if err != nil {
		message = err.Error()
	}
	at = at.UTC()
	return device.Verdict{Score: nil, Severity: "unknown", Reasons: []string{"no se pudo evaluar el riesgo: " + message}, MatchedPolicies: []string{}, EvaluatedAt: &at, Provenance: "none", Verified: false}
}

// MaxScore ignora únicamente nil y NaN; devuelve una copia independiente.
func MaxScore(vs []device.Verdict) *float64 {
	var result *float64
	for _, v := range vs {
		if v.Score == nil || math.IsNaN(*v.Score) {
			continue
		}
		if result == nil || *v.Score > *result {
			n := *v.Score
			result = &n
		}
	}
	return result
}

func evidenceGate(score float64, reasons []string) ([]string, string, bool) {
	if len(reasons) > 0 {
		return reasons, "tool", true
	}
	if score > 0 {
		return []string{"riesgo sin señal explícita (score base)"}, "context", false
	}
	return []string{}, "none", false
}
