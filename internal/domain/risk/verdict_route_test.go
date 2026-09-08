package risk

import (
	"math"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestVerdictZoneAndRoute(t *testing.T) {
	cases := []struct {
		name      string
		zone      any
		route     string
		deviation any
		score     float64
		reason    string
	}{
		{"zone normal", 0.35, "", nil, 7, "zona de riesgo elevado (0.35)"},
		{"zone integer", 1, "", nil, 20, "zona de riesgo elevado (1)"},
		{"zone negative", -1.0, "", nil, 0, ""},
		{"zone nonfinite", math.Inf(1), "", nil, 0, ""},
		{"zone overflow", math.MaxFloat64, "", nil, 100, ""},
		{"route trunc", 0, "off_route", 199.9, 26, "desviado de su ruta asignada (199 m)"},
		{"route capped", 0, "off_route", 10000, 50, "desviado de su ruta asignada (10000 m)"},
		{"route negative", 0, "off_route", -5.0, 25, "desviado de su ruta asignada (0 m)"},
		{"credit floor", 0.1, "on_route", nil, 0, "zona de riesgo elevado (0.1)"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			sig := Signals{"zone_risk": {"zone_risk": tc.zone}, "route_state": {"route_state": tc.route, "route_deviation_m": tc.deviation}}
			got := Evaluate(device.Device{}, sig, time.Time{})
			if *got.Score != tc.score {
				t.Fatalf("score=%v want=%v", *got.Score, tc.score)
			}
			if tc.reason != "" && (len(got.Reasons) != 1 || got.Reasons[0] != tc.reason) {
				t.Fatal(got.Reasons)
			}
			if tc.name == "credit floor" && (!got.Verified || got.Provenance != "tool") {
				t.Fatal(got)
			}
		})
	}
}
