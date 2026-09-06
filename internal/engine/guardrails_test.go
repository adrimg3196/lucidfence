package engine

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

func TestObserveSiempreDryRun(t *testing.T) {
	g := Guardrails{Enforcement: EnforcementObserve}
	for _, a := range action.All {
		if !g.DryRun(a) {
			t.Fatalf("%s en observe debe ser dry-run", a)
		}
	}
	if g.Enforcement != "observe" {
		t.Fatal("literal")
	}
}

func TestEnforcementVacioEquivaleAObserve(t *testing.T) {
	if !(Guardrails{}).DryRun(action.Wipe) {
		t.Fatal("sin configurar = observe")
	}
}
