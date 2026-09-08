package policy

// Match informa candidatos sin efectos ni ejecución.
type Match struct {
	PolicyID string   `json:"policy_id"`
	Name     string   `json:"name"`
	Severity string   `json:"severity"`
	Actions  []Action `json:"actions"`
}

// Matches exige AND completo; una política vacía o apagada no casa.
func (p Policy) Matches(s Subject) bool {
	if !p.Enabled || len(p.When) == 0 {
		return false
	}
	for _, c := range p.When {
		if !c.Match(s) {
			return false
		}
	}
	return true
}

// MatchAll mantiene el orden de entrada y devuelve acciones independientes.
func MatchAll(ps []Policy, s Subject) []Match {
	var out []Match
	for _, p := range ps {
		if p.Validate() != nil || !p.Matches(s) {
			continue
		}
		actions, ok := cloneActions(p.Actions)
		if !ok {
			continue
		} // Parámetros imposibles no producen candidatos parciales.
		out = append(out, Match{PolicyID: p.ID, Name: p.Name, Severity: p.Severity, Actions: actions})
	}
	return out
}

func cloneActions(actions []Action) ([]Action, bool) {
	if actions == nil {
		return nil, true
	}
	out := make([]Action, len(actions))
	for i, a := range actions {
		v, err := jsonCopy(a.Params)
		if err != nil {
			return nil, false
		}
		params, _ := v.(map[string]any)
		out[i] = Action{Action: a.Action, Params: params}
	}
	return out, true
}
