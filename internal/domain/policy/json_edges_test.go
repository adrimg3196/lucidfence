package policy_test

import (
	"encoding/json"
	"math"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestFloat32ConservaSemanticaJSON(t *testing.T) {
	c := policy.Condition{Field: "risk_score", Op: policy.OpEq, Value: float32(0.1)}
	raw, err := json.Marshal(c)
	if err != nil {
		t.Fatal(err)
	}
	var restored policy.Condition
	if err := json.Unmarshal(raw, &restored); err != nil {
		t.Fatal(err)
	}
	s := policy.Subject{Verdict: device.Verdict{Score: ptr(0.1)}}
	if !c.Match(s) || !restored.Match(s) {
		t.Fatal("float32/JSON cambia matching")
	}
}

func TestUnknownNoFinitoNativoYJSON(t *testing.T) {
	invalid := []any{nil, (*float64)(nil), math.NaN(), math.Inf(1), math.Inf(-1), []string(nil), map[string]any(nil)}
	for _, value := range invalid {
		signals := risk.Signals{"test": {"value": value}}
		variants := []risk.Signals{signals}
		if raw, err := json.Marshal(signals); err == nil {
			var restored risk.Signals
			if err := json.Unmarshal(raw, &restored); err != nil {
				t.Fatal(err)
			}
			variants = append(variants, restored)
		}
		for _, sig := range variants {
			for _, op := range policy.Ops {
				c := policy.Condition{Field: "signal:test.value", Op: op, Value: 0}
				if c.Match(policy.Subject{Signals: sig}) {
					t.Fatalf("%T %s casa", value, op)
				}
			}
		}
	}
}

func TestParametrosInvalidosNoProducenCandidatos(t *testing.T) {
	p := validPolicy()
	p.Actions[0].Params = map[string]any{"nan": math.NaN()}
	if p.Actions[0].Validate() == nil {
		t.Fatal("params no JSON aceptados")
	}
	if got := policy.MatchAll([]policy.Policy{p}, policy.Subject{}); len(got) != 0 {
		t.Fatal(got)
	}
}
