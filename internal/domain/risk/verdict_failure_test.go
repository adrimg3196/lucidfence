package risk

import (
	"encoding/json"
	"errors"
	"math"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestFailedPreservesUnknown(t *testing.T) {
	for _, err := range []error{nil, errors.New("fallo proveedor")} {
		v := Failed(err, noon.In(time.FixedZone("local", 7200)))
		reason := "no se pudo evaluar el riesgo: error desconocido"
		if err != nil {
			reason = "no se pudo evaluar el riesgo: " + err.Error()
		}
		if v.Score != nil || v.Severity != "unknown" || !reflect.DeepEqual(v.Reasons, []string{reason}) || v.MatchedPolicies == nil || v.Verified || v.Provenance != "none" || *v.EvaluatedAt != noon {
			t.Fatal(v)
		}
		b, e := json.Marshal(v)
		if e != nil || !strings.Contains(string(b), `"score":null`) {
			t.Fatalf("%s %v", b, e)
		}
	}
}

func TestMaxScoreUnknownAndOwnership(t *testing.T) {
	if MaxScore(nil) != nil || MaxScore([]device.Verdict{{}, {Score: ptr(math.NaN())}}) != nil {
		t.Fatal("unknown became zero")
	}
	vs := []device.Verdict{{Score: ptr(0.0)}, {Score: ptr(45.0)}, {Score: ptr(math.NaN())}}
	got := MaxScore(vs)
	if got == nil || *got != 45 {
		t.Fatal(got)
	}
	*got = 9
	if *vs[1].Score != 45 {
		t.Fatal("aliased score")
	}
	for _, n := range []float64{math.Inf(-1), math.Inf(1), 0} {
		got := MaxScore([]device.Verdict{{Score: &n}})
		if got == nil || *got != n {
			t.Fatal(got)
		}
	}
	if !reflect.DeepEqual(Severities, []string{"low", "medium", "high", "critical"}) {
		t.Fatal(Severities)
	}
}

func TestEvidenceGate(t *testing.T) {
	for _, tc := range []struct {
		score    float64
		reasons  []string
		prov     string
		verified bool
		want     []string
	}{
		{0, nil, "none", false, []string{}},
		{1, nil, "context", false, []string{"riesgo sin señal explícita (score base)"}},
		{0, []string{"real"}, "tool", true, []string{"real"}},
	} {
		reasons, prov, verified := evidenceGate(tc.score, tc.reasons)
		if prov != tc.prov || verified != tc.verified || !reflect.DeepEqual(reasons, tc.want) {
			t.Fatalf("%v %s %v", reasons, prov, verified)
		}
	}
}
