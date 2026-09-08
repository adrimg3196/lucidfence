package policy_test

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

type definedBool bool
type definedInt int

func TestDefinedScalarEqualitySurvivesJSON(t *testing.T) {
	pairs := []struct{ actual, equal, different any }{
		{device.Outside, device.Outside, device.Inside},
		{definedBool(false), definedBool(false), definedBool(true)},
		{definedInt(1), definedInt(1), definedInt(2)},
	}
	for _, pair := range pairs {
		for _, op := range []policy.Op{policy.OpEq, policy.OpNe, policy.OpIn} {
			t.Run(fmt.Sprintf("%T/%s", pair.actual, op), func(t *testing.T) {
				value := pair.equal
				if op == policy.OpNe {
					value = pair.different
				}
				if op == policy.OpIn {
					value = []any{value}
				}
				c := policy.Condition{Field: "signal:probe.v", Op: op, Value: value}
				s := policy.Subject{Signals: risk.Signals{"probe": {"v": pair.actual}}}
				data, err := json.Marshal(c)
				if err != nil {
					t.Fatal(err)
				}
				var restored policy.Condition
				if err := json.Unmarshal(data, &restored); err != nil {
					t.Fatal(err)
				}
				for _, condition := range []policy.Condition{c, restored} {
					if err := condition.Validate(); err != nil {
						t.Fatal(err)
					}
					if !condition.Match(s) {
						t.Errorf("defined scalar failed: %#v %s %#v", pair.actual, op, condition.Value)
					}
				}
			})
		}
	}
}

func TestDefinedScalarsNeverCrossFamilies(t *testing.T) {
	for _, pair := range [][2]any{{definedBool(true), 1}, {definedBool(false), 0}, {definedInt(1), "1"}, {device.Outside, false}, {json.Number("1"), "1"}, {"1", json.Number("1")}} {
		for _, op := range []policy.Op{policy.OpEq, policy.OpNe, policy.OpIn} {
			value := pair[1]
			if op == policy.OpIn {
				value = []any{value}
			}
			c := policy.Condition{Field: "signal:probe.v", Op: op, Value: value}
			if c.Match(policy.Subject{Signals: risk.Signals{"probe": {"v": pair[0]}}}) {
				t.Errorf("family crossing: %#v %s %#v", pair[0], op, value)
			}
		}
	}
}
