package policy_test

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/policy"
)

func TestConfiguracionInvalidaNoProduceCandidatos(t *testing.T) {
	for _, change := range []func(*policy.Policy){
		func(p *policy.Policy) { p.Actions[0].Action = "retire" },
		func(p *policy.Policy) { p.Actions = nil },
		func(p *policy.Policy) { p.Severity = "unknown" },
		func(p *policy.Policy) { p.ID = "INVALID" },
	} {
		p := validPolicy()
		change(&p)
		if got := policy.MatchAll([]policy.Policy{p}, policy.Subject{}); len(got) != 0 {
			t.Fatalf("configuración inválida produce candidatos %+v", got)
		}
	}
}

func TestListaInvalidaNoCoincideParcialmente(t *testing.T) {
	c := policy.Condition{Field: "dwell_seconds", Op: policy.OpIn, Value: []any{0, uint64(9007199254740993)}}
	if c.Validate() == nil {
		t.Fatal("lista fuera de rango validada")
	}
	if c.Match(policy.Subject{}) {
		t.Fatal("condición inválida casa parcialmente")
	}
}
