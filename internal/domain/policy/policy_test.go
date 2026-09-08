package policy_test

import (
	"encoding/json"
	"math"
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func validPolicy() policy.Policy {
	return policy.Policy{ID: "test-1", Name: "Prueba", Enabled: true, Severity: "high",
		When:    []policy.Condition{{Field: "dwell_seconds", Op: policy.OpGte, Value: 0}},
		Actions: []policy.Action{{Action: action.Notify}}}
}

func TestValidateCasosDorados(t *testing.T) {
	tests := []struct {
		name, fragment string
		change         func(*policy.Policy)
	}{
		{"id vacío", "id", func(p *policy.Policy) { p.ID = "" }},
		{"id inválido", "id", func(p *policy.Policy) { p.ID = "MAL" }},
		{"id largo", "id", func(p *policy.Policy) { p.ID = strings.Repeat("a", 65) }},
		{"nombre", "nombre", func(p *policy.Policy) { p.Name = " " }},
		{"when", "when", func(p *policy.Policy) { p.When = nil }},
		{"field", "campo", func(p *policy.Policy) { p.When[0].Field = "missing" }},
		{"op", "operador", func(p *policy.Policy) { p.When[0].Op = "" }},
		{"value", "value", func(p *policy.Policy) { p.When[0].Value = nil }},
		{"actions", "actions", func(p *policy.Policy) { p.Actions = nil }},
		{"retire", "retire", func(p *policy.Policy) { p.Actions[0].Action = "retire" }},
		{"severity", "severidad", func(p *policy.Policy) { p.Severity = "unknown" }},
	}
	if err := validPolicy().Validate(); err != nil {
		t.Fatal(err)
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			p := validPolicy()
			tt.change(&p)
			err := p.Validate()
			if err == nil || !strings.Contains(err.Error(), tt.fragment) || !strings.Contains(err.Error(), p.ID) {
				t.Fatalf("error no accionable: %v", err)
			}
		})
	}
	for _, severity := range risk.Severities {
		p := validPolicy()
		p.Severity = severity
		if err := p.Validate(); err != nil {
			t.Fatal(err)
		}
	}
}

func TestValidateDeCondicionYAccionPorSeparado(t *testing.T) {
	invalid := []policy.Condition{
		{Field: "", Op: policy.OpEq, Value: 1}, {Field: "signal:x", Op: policy.OpEq, Value: 1},
		{Field: "signal:.k", Op: policy.OpEq, Value: 1}, {Field: "signal:x.", Op: policy.OpEq, Value: 1},
		{Field: "platform", Op: "bad", Value: 1}, {Field: "platform", Op: policy.OpEq, Value: (*bool)(nil)},
		{Field: "platform", Op: policy.OpIn, Value: "android"}, {Field: "platform", Op: policy.OpContains, Value: true},
		{Field: "dwell_seconds", Op: policy.OpGt, Value: "1"}, {Field: "dwell_seconds", Op: policy.OpEq, Value: math.NaN()},
		{Field: "dwell_seconds", Op: policy.OpEq, Value: uint64(9007199254740993)},
	}
	for _, c := range invalid {
		if c.Validate() == nil {
			t.Errorf("condición inválida aceptada %+v", c)
		}
	}
	for _, v := range []any{false, 0, "android", []any{1, "a", false}, map[string]any{"a": 1}} {
		if err := (policy.Condition{Field: "signal:x.k", Op: policy.OpEq, Value: v}).Validate(); err != nil {
			t.Fatal(err)
		}
	}
	for _, a := range action.All {
		if err := (policy.Action{Action: a}).Validate(); err != nil {
			t.Fatal(err)
		}
	}
	if (policy.Action{Action: "retire"}).Validate() == nil {
		t.Fatal("retire aceptado")
	}
}

func TestParseOpYFindByID(t *testing.T) {
	if len(policy.Ops) != 8 {
		t.Fatal("catálogo operadores")
	}
	for _, op := range policy.Ops {
		got, err := policy.ParseOp(string(op))
		if err != nil || got != op {
			t.Fatal(op, got, err)
		}
	}
	for _, bad := range []string{"", "EQ", "unknown"} {
		if _, err := policy.ParseOp(bad); err == nil {
			t.Fatal(bad)
		}
	}
	p := validPolicy()
	if got, ok := policy.FindByID([]policy.Policy{p}, p.ID); !ok || got.ID != p.ID {
		t.Fatal("no encontrado")
	}
	if _, ok := policy.FindByID([]policy.Policy{p}, "missing"); ok {
		t.Fatal("inventado")
	}
}

func TestValidateAllNombraLaPoliticaYLosIdsDuplicados(t *testing.T) {
	p := validPolicy()
	if policy.ValidateAll([]policy.Policy{p}) != nil {
		t.Fatal("válida rechazada")
	}
	if err := policy.ValidateAll([]policy.Policy{p, p}); err == nil || !strings.Contains(err.Error(), p.ID) || !strings.Contains(err.Error(), "duplicado") {
		t.Fatal(err)
	}
	p.Name = ""
	if err := policy.ValidateAll([]policy.Policy{p}); err == nil || !strings.Contains(err.Error(), p.ID) {
		t.Fatal(err)
	}
}

func TestUnFicheroQueNoEsListaNoCarga(t *testing.T) {
	for _, raw := range []string{`{}`, `1`, `"a"`, `[null]`, `null`} {
		var ps []policy.Policy
		err := json.Unmarshal([]byte(raw), &ps)
		if err == nil {
			err = policy.ValidateAll(ps)
		}
		if err == nil {
			t.Fatalf("no-lista aceptada %s", raw)
		}
	}
	if err := policy.ValidateAll([]policy.Policy{}); err != nil {
		t.Fatal(err)
	}
}
