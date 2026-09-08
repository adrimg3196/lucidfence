package policy_test

import (
	"encoding/json"
	"sync"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestTodasLasFamiliasValueHacenRoundTrip(t *testing.T) {
	for _, v := range []any{false, 0, 1.5, "texto", []any{1, false}, map[string]any{"nested": []any{0, "a"}}} {
		c := policy.Condition{Field: "signal:test.value", Op: policy.OpEq, Value: v}
		raw, err := json.Marshal(c)
		if err != nil {
			t.Fatal(err)
		}
		var restored policy.Condition
		if err := json.Unmarshal(raw, &restored); err != nil {
			t.Fatal(err)
		}
		again, err := json.Marshal(restored)
		if err != nil {
			t.Fatal(err)
		}
		if string(raw) != string(again) {
			t.Fatal("familia/claves alteradas")
		}
		s := policy.Subject{Signals: risk.Signals{"test": {"value": v}}}
		if c.Match(s) != restored.Match(s) {
			t.Fatalf("resultado cambia %T", v)
		}
	}
}

func TestMatchingConcurrenteNoMutaEntradas(t *testing.T) {
	p := validPolicy()
	p.Actions[0].Params = map[string]any{"nested": map[string]any{"list": []any{"original"}}}
	before, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	for range 16 {
		wg.Go(func() {
			for range 10 {
				matches := policy.MatchAll([]policy.Policy{p}, policy.Subject{})
				if len(matches) != 1 {
					t.Error("matching inconsistente")
					return
				}
				matches[0].Actions[0].Params["nested"].(map[string]any)["list"].([]any)[0] = "mutado"
				templates := policy.Templates()
				templates[0].Actions[0].Params["msg"] = "local"
			}
		})
	}
	wg.Wait()
	after, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("entrada compartida mutada")
	}
}
