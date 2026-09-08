package risk

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestSinSenalesSoloCuentaLaGeocerca(t *testing.T) {
	at := noon.In(time.FixedZone("local", 7200))
	for _, tc := range []struct {
		state   device.FenceState
		score   float64
		reasons []string
	}{
		{device.Inside, 0, []string{}},
		{device.Outside, 35, []string{"fuera de geocerca permitida"}},
		{device.Unknown, 20, []string{"ubicación desconocida (señal perdida)"}},
	} {
		t.Run(string(tc.state), func(t *testing.T) {
			v := Evaluate(device.Device{FenceState: tc.state, Compliant: ptr(false)}, nil, at)
			if v.Score == nil || *v.Score != tc.score || !reflect.DeepEqual(v.Reasons, tc.reasons) {
				t.Fatalf("veredicto = %+v", v)
			}
			if v.EvaluatedAt == nil || *v.EvaluatedAt != noon || v.MatchedPolicies == nil {
				t.Fatalf("fecha/listas = %+v", v)
			}
			wantProv := "none"
			if len(tc.reasons) > 0 {
				wantProv = "tool"
			}
			if v.Provenance != wantProv || v.Verified != (len(tc.reasons) > 0) {
				t.Fatalf("evidencia = %+v", v)
			}
		})
	}
}

func TestSeverityFronteras(t *testing.T) {
	for _, tc := range []struct {
		score float64
		want  string
	}{
		{0, "low"}, {29.9, "low"}, {30, "medium"}, {54.9, "medium"},
		{55, "high"}, {79.9, "high"}, {80, "critical"}, {100, "critical"},
	} {
		if got := Severity(tc.score); got != tc.want {
			t.Errorf("Severity(%v)=%s", tc.score, got)
		}
	}
}
