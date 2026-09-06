package engine

import "github.com/adrimg3196/lucidfence/internal/domain/action"

// Modos de enforcement (spec §3 y §5.4). observe = todo dry-run.
const (
	EnforcementObserve = "observe"
	EnforcementEnforce = "enforce"
)

// Guardrails es el ÚNICO sitio que decide si una acción sale en vivo. Este
// fichero está protegido por CODEOWNERS. M1 solo conoce observe; M2 añade
// live_actions, allow_wipe y wipe_allowlist sin mover la decisión de aquí.
type Guardrails struct {
	Enforcement string
}

// DryRun devuelve true si la acción NO debe llegar al dispositivo real.
func (g Guardrails) DryRun(_ action.Action) bool {
	return g.Enforcement != EnforcementEnforce
}
