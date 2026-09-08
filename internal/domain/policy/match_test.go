package policy_test

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/google/go-cmp/cmp"
)

func TestMatchesYMatchAll(t *testing.T) {
	s := policy.NewSubject(device.Device{}, device.Verdict{}, nil)
	p := validPolicy()
	if !p.Matches(s) {
		t.Fatal("política válida no casa")
	}
	second := validPolicy()
	second.ID = "second"
	disabled := validPolicy()
	disabled.Enabled = false
	empty := validPolicy()
	empty.When = nil
	and := validPolicy()
	and.When = append(and.When, policy.Condition{Field: "platform", Op: policy.OpEq, Value: "ios"})
	ps := []policy.Policy{second, disabled, empty, and, p}
	matches := policy.MatchAll(ps, s)
	want := []policy.Match{{PolicyID: second.ID, Name: second.Name, Severity: second.Severity, Actions: second.Actions}, {PolicyID: p.ID, Name: p.Name, Severity: p.Severity, Actions: p.Actions}}
	if diff := cmp.Diff(want, matches); diff != "" {
		t.Fatal(diff)
	}
	if got := policy.MatchAll(nil, s); len(got) != 0 {
		t.Fatal(got)
	}
}

func TestMatchAllCopiaParamsProfundos(t *testing.T) {
	p := validPolicy()
	p.Actions[0].Params = map[string]any{"nested": map[string]any{"list": []any{map[string]any{"text": "original"}, []string{"a"}}}, "big": uint64(18446744073709551615)}
	before, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	matches := policy.MatchAll([]policy.Policy{p}, policy.Subject{})
	if len(matches) != 1 {
		t.Fatal(matches)
	}
	params := matches[0].Actions[0].Params
	list := params["nested"].(map[string]any)["list"].([]any)
	list[0].(map[string]any)["text"] = "mutado"
	list[1].([]any)[0] = "b"
	matches[0].Actions[0].Action = "wipe"
	after, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("entrada mutada")
	}
	if got := params["big"].(json.Number).String(); got != "18446744073709551615" {
		t.Fatal("Params pierde precisión", got)
	}
}

func TestJSONConservaFamiliasYMatching(t *testing.T) {
	p := validPolicy()
	p.CreatedAt = time.Date(2026, 1, 2, 3, 4, 5, 6, time.UTC)
	p.UpdatedAt = p.CreatedAt
	p.Source = "custom"
	p.TemplateID = "tpl-original"
	p.Description = "Descripción"
	p.When = append(p.When, policy.Condition{Field: "compliant", Op: policy.OpEq, Value: false}, policy.Condition{Field: "platform", Op: policy.OpIn, Value: []string{"ios", "android"}})
	p.Actions[0].Params = map[string]any{"bool": false, "number": 1.5, "text": "a", "list": []any{0, false, nil}, "object": map[string]any{"k": "v"}}
	raw, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	var got policy.Policy
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatal(err)
	}
	again, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	if string(raw) != string(again) {
		t.Fatalf("JSON cambió\n%s\n%s", raw, again)
	}
	for _, platform := range []string{"ios", "windows"} {
		s := policy.NewSubject(device.Device{Compliant: ptr(false), Platform: platform}, device.Verdict{}, nil)
		if p.Matches(s) != got.Matches(s) || p.Matches(s) != (platform == "ios") {
			t.Fatal("semántica JSON cambió")
		}
	}
}

func TestConsumidorNoRecalculaScoreT03(t *testing.T) {
	at := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
	d := device.Device{FenceState: device.Outside}
	signals := risk.Signals{"zone_risk": {"zone_risk": 0.9975}}
	v := risk.Evaluate(d, signals, at)
	if v.Score == nil || *v.Score != 55 || v.Severity != "high" {
		t.Fatal(v)
	}
	s := policy.NewSubject(d, v, signals)
	if !(policy.Condition{Field: "risk_score", Op: policy.OpEq, Value: 55}).Match(s) {
		t.Fatal("score T03 no consumido")
	}
}
