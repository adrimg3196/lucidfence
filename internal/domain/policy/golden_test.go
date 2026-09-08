package policy_test

import (
	"encoding/json"
	"os"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestGoldensCompatibilidadYDivergenciasSeparadas(t *testing.T) {
	for _, file := range []string{"compatibility.json", "divergences.json"} {
		t.Run(file, func(t *testing.T) {
			data, err := os.ReadFile("testdata/" + file)
			if err != nil {
				t.Fatal(err)
			}
			var cases []struct {
				Name   string
				Actual any
				Op     policy.Op
				Value  any
				Match  bool
				Legacy *bool
			}
			if err := json.Unmarshal(data, &cases); err != nil {
				t.Fatal(err)
			}
			if len(cases) == 0 {
				t.Fatal("sin goldens")
			}
			for _, tc := range cases {
				t.Run(tc.Name, func(t *testing.T) {
					s := policy.Subject{Signals: risk.Signals{"golden": {"actual": tc.Actual}}}
					c := policy.Condition{Field: "signal:golden.actual", Op: tc.Op, Value: tc.Value}
					if got := c.Match(s); got != tc.Match {
						t.Fatalf("got %v want %v", got, tc.Match)
					}
					if file == "divergences.json" && (tc.Legacy == nil || *tc.Legacy == tc.Match) {
						t.Fatal("divergencia no etiquetada")
					}
				})
			}
		})
	}
}
