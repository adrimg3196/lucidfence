package policy_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
)

func TestActionJSONPreservesParamsAtIngress(t *testing.T) {
	for _, n := range []uint64{9007199254740993, 18446744073709551615} {
		t.Run(fmt.Sprint(n), func(t *testing.T) {
			original := policy.Action{Action: action.Notify, Params: map[string]any{
				"n": n, "nested": []any{map[string]any{"n": n}}, "bool": false, "text": "1", "null": nil,
			}}
			data, err := json.Marshal(original)
			if err != nil {
				t.Fatal(err)
			}
			var decoded policy.Action
			if err := json.Unmarshal(data, &decoded); err != nil {
				t.Fatal(err)
			}
			if _, ok := decoded.Params["n"].(json.Number); !ok {
				t.Errorf("number lost at ingress: %T", decoded.Params["n"])
			}
			if err := decoded.Validate(); err != nil {
				t.Fatal(err)
			}
			got, err := json.Marshal(decoded)
			if err != nil || !bytes.Equal(data, got) {
				t.Fatalf("Params changed: %s -> %s (%v)", data, got, err)
			}
			p := policy.Policy{Actions: []policy.Action{original}}
			data, err = json.Marshal(p)
			if err != nil {
				t.Fatal(err)
			}
			var restored policy.Policy
			if err := json.Unmarshal(data, &restored); err != nil {
				t.Fatal(err)
			}
			got, err = json.Marshal(restored)
			if err != nil || !bytes.Equal(data, got) {
				t.Fatalf("Policy Params changed: %s -> %s (%v)", data, got, err)
			}
		})
	}
}
