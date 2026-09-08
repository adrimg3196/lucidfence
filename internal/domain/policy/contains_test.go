package policy_test

import (
	"encoding/json"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestContainsTextFamilyRoundTrip(t *testing.T) {
	type text string
	var missing *string
	cases := []struct {
		name     string
		observed any
		needle   any
		want     bool
	}{
		{"fence", device.Outside, "side", true},
		{"route", device.OffRoute, "route", true},
		{"unicode", text("España"), "aña", true},
		{"both_defined", text("España"), text("aña"), true},
		{"builtin", "outside", "side", true},
		{"case", text("España"), "AÑA", false},
		{"absent", text("España"), "xyz", false},
		{"empty_needle", text("España"), "", true},
		{"json_number", json.Number("123"), "2", false},
		{"number", 123, "2", false},
		{"bool", true, "r", false},
		{"nil", nil, "", false},
		{"typed_nil", missing, "", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			c := policy.Condition{Field: "signal:probe.v", Op: policy.OpContains, Value: tc.needle}
			if err := c.Validate(); err != nil {
				t.Fatal(err)
			}
			s := policy.Subject{Signals: risk.Signals{"probe": {"v": tc.observed}}}
			raw, err := json.Marshal(s)
			if err != nil {
				t.Fatal(err)
			}
			var decoded policy.Subject
			if err := json.Unmarshal(raw, &decoded); err != nil {
				t.Fatal(err)
			}
			conditionJSON, err := json.Marshal(c)
			if err != nil {
				t.Fatal(err)
			}
			var decodedCondition policy.Condition
			if err := json.Unmarshal(conditionJSON, &decodedCondition); err != nil {
				t.Fatal(err)
			}
			for name, subject := range map[string]policy.Subject{"native": s, "json": decoded} {
				for _, condition := range []policy.Condition{c, decodedCondition} {
					if got := condition.Match(subject); got != tc.want {
						t.Errorf("%s Match=%v want %v", name, got, tc.want)
					}
				}
			}
			if c.Match(policy.Subject{}) {
				t.Error("unknown signal matched")
			}
		})
	}
}
