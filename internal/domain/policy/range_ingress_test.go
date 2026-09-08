package policy_test

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestConditionJSONRetainsRejectedLiteral(t *testing.T) {
	for _, n := range []json.Number{"9007199254740991.1", "-9007199254740991.1", "9007199254740993", "18446744073709551615"} {
		for _, op := range []policy.Op{policy.OpEq, policy.OpNe, policy.OpGte, policy.OpLte, policy.OpIn} {
			t.Run(fmt.Sprintf("%s/%s", n, op), func(t *testing.T) {
				var value any = n
				if op == policy.OpIn {
					value = []any{n}
				}
				original := policy.Condition{Field: "signal:probe.n", Op: op, Value: value}
				if original.Validate() == nil {
					t.Fatal("native literal accepted")
				}
				data, err := json.Marshal(original)
				if err != nil {
					t.Fatal(err)
				}
				var decoded policy.Condition
				if err := json.Unmarshal(data, &decoded); err != nil {
					t.Fatal(err)
				}
				var nested policy.Policy
				if err := json.Unmarshal(append(append([]byte(`{"when":[`), data...), []byte(`]}`)...), &nested); err != nil {
					t.Fatal(err)
				}
				for _, c := range []policy.Condition{original, decoded, nested.When[0]} {
					if c.Validate() == nil {
						t.Errorf("invalid literal became valid: %#v", c.Value)
					}
					got, err := json.Marshal(c.Value)
					want, _ := json.Marshal(value)
					if err != nil || string(got) != string(want) {
						t.Errorf("literal changed: %s -> %s", want, got)
					}
					for _, actual := range []any{0, 9007199254740991.0, -9007199254740991.0, nil} {
						if c.Match(policy.Subject{Signals: risk.Signals{"probe": {"n": actual}}}) {
							t.Errorf("invalid literal matched %v", actual)
						}
					}
				}
			})
		}
	}
}
