package policy_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestSubjectJSONObservedRange(t *testing.T) {
	for _, literal := range []string{"9007199254740991.1", "-9007199254740991.1", "9.0071992547409911e15", "-9.0071992547409911e15"} {
		for _, op := range policy.Ops {
			if op == policy.OpContains {
				continue
			}
			t.Run(literal+"/"+string(op), func(t *testing.T) {
				var value any = json.Number("9007199254740991")
				if literal[0] == '-' {
					value = json.Number("-9007199254740991")
				}
				if op == policy.OpNe || op == policy.OpGt || op == policy.OpLt {
					value = 0
				}
				if op == policy.OpIn {
					value = []any{value}
				}
				c := policy.Condition{Field: "signal:probe.v", Op: op, Value: value}
				checkSubjectJSON(t, json.Number(literal), c, false)
			})
		}
	}
}

func TestSubjectJSONControls(t *testing.T) {
	var missing *int
	for _, tc := range []struct {
		name            string
		observed, value any
		op              policy.Op
		want            bool
	}{
		{"positive-edge", json.Number("9007199254740991"), int64(9007199254740991), policy.OpEq, true},
		{"negative-edge", json.Number("-9007199254740991"), int64(-9007199254740991), policy.OpEq, true},
		{"fraction", json.Number("0.125"), 0.125, policy.OpEq, true},
		{"zero", 0, 0, policy.OpEq, true},
		{"false", false, false, policy.OpEq, true},
		{"text", "España", "aña", policy.OpContains, true},
		{"nil", nil, 0, policy.OpNe, false},
		{"typed-nil", missing, 0, policy.OpNe, false},
		{"no-text-coercion", "1", 1, policy.OpNe, false},
		{"no-bool-coercion", true, 1, policy.OpEq, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			checkSubjectJSON(t, tc.observed, policy.Condition{Field: "signal:probe.v", Op: tc.op, Value: tc.value}, tc.want)
		})
	}
}

func checkSubjectJSON(t *testing.T, observed any, c policy.Condition, want bool) {
	t.Helper()
	if err := c.Validate(); err != nil {
		t.Fatal(err)
	}
	s := policy.Subject{Signals: risk.Signals{"probe": {"v": observed}}}
	data, err := json.Marshal(s)
	if err != nil {
		t.Fatal(err)
	}
	subjects := map[string]policy.Subject{"native": s}
	for _, mode := range []string{"unmarshal", "decoder", "use-number", "container"} {
		var decoded policy.Subject
		switch mode {
		case "unmarshal":
			err = json.Unmarshal(data, &decoded)
		case "container":
			var values []policy.Subject
			err = json.Unmarshal(append(append([]byte{'['}, data...), ']'), &values)
			if err == nil {
				decoded = values[0]
			}
		default:
			d := json.NewDecoder(bytes.NewReader(data))
			if mode == "use-number" {
				d.UseNumber()
			}
			err = d.Decode(&decoded)
		}
		if err != nil {
			t.Fatal(err)
		}
		subjects[mode] = decoded
	}
	p := policy.Policy{ID: "observed-range", Name: "Observed range", Enabled: true, Severity: "high", When: []policy.Condition{c}, Actions: []policy.Action{{Action: action.Notify}}}
	if err := p.Validate(); err != nil {
		t.Fatal(err)
	}
	for mode, subject := range subjects {
		if got := c.Match(subject); got != want {
			t.Errorf("%s Match=%v want %v; observed=%#v", mode, got, want, subject.Signals)
		}
		matches := policy.MatchAll([]policy.Policy{p}, subject)
		if got := len(matches) > 0; got != want {
			t.Errorf("%s MatchAll=%s want candidate=%v", mode, fmt.Sprint(matches), want)
		}
	}
}

func TestSubjectJSONDecodeErrorsAndNull(t *testing.T) {
	for _, data := range []string{`{"Signals":{"probe":{"v":1e}}}}`, `{"Signals":[]}`, `{"Device":false}`} {
		var s policy.Subject
		if err := json.Unmarshal([]byte(data), &s); err == nil {
			t.Errorf("accepted %s", data)
		}
	}
	for _, data := range []string{`null`, `{}`, `{"Signals":null}`, `{"Signals":{"probe":{"v":null}}}`} {
		var s policy.Subject
		if err := json.Unmarshal([]byte(data), &s); err != nil {
			t.Fatal(err)
		}
		if (policy.Condition{Field: "signal:probe.v", Op: policy.OpNe, Value: 0}).Match(s) {
			t.Errorf("null acquired evidence: %s", data)
		}
	}
}
