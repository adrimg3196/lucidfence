package engine

import (
	"errors"
	"log/slog"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// motorMudo es un motor sin store ni conectores, con los tres mapas de estado
// del ciclo listos: basta para planificar órdenes y deduplicarlas.
func motorMudo() *Engine {
	return &Engine{
		fired:      map[string]bool{},
		violations: map[string]int{},
		dwelled:    map[string]string{},
		opts:       Options{Now: func() time.Time { return guardT0 }, Logger: slog.New(slog.DiscardHandler)},
	}
}

// dispositivoConRiesgo devuelve un dispositivo dentro de demo-hq con el score
// dado y la señal de ruta publicada, tal como lo deja evaluateRisk (T13).
func dispositivoConRiesgo(score float64) device.Device {
	s := score
	return device.Device{
		ID: "dev-a", Name: "A", Platform: "android", Provider: "sim",
		FenceState: device.Inside, InsideFence: "demo-hq", RouteState: device.OffRoute,
		Signals: map[string]map[string]any{"route_state": {"route_state": "off_route"}},
		Risk: device.Verdict{Score: &s, Severity: risk.Severity(score),
			Reasons: []string{}, MatchedPolicies: []string{}},
	}
}

// politicaRiesgo es la política de los casos: dispara por encima de 50.
func politicaRiesgo(id string, acts ...policy.Action) policy.Policy {
	return policy.Policy{
		ID: id, Name: "Riesgo alto " + id, Enabled: true, Severity: risk.SeverityHigh,
		When:    []policy.Condition{{Field: "risk_score", Op: policy.OpGte, Value: 50.0}},
		Actions: acts,
	}
}

func TestPoliticaQueCasaEmiteSusAcciones(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(70)
	ps := []policy.Policy{politicaRiesgo("p-riesgo",
		policy.Action{Action: action.Notify, Params: map[string]any{"channel": "ciso"}},
		policy.Action{Action: action.Lock})}
	got := e.planPolicies(&cur, subjectFor(cur), ps)
	if len(got) != 2 {
		t.Fatalf("una orden por acción de la política: %+v", got)
	}
	for i, want := range []action.Action{action.Notify, action.Lock} {
		if got[i].Action != want || got[i].PolicyID != "p-riesgo" || got[i].Trigger != TriggerPolicy {
			t.Fatalf("orden %d: %+v", i, got[i])
		}
		if got[i].Severity != risk.SeverityHigh {
			t.Fatalf("la orden hereda la severidad de la política: %+v", got[i])
		}
		if got[i].FenceID != "demo-hq" {
			t.Fatalf("el cubo de dedupe es la geocerca en la que está el dispositivo: %+v", got[i])
		}
	}
	if got[0].Params["channel"] != "ciso" {
		t.Fatalf("los parámetros de la política viajan en la orden: %+v", got[0].Params)
	}
	if len(cur.Risk.MatchedPolicies) != 1 || cur.Risk.MatchedPolicies[0] != "p-riesgo" {
		t.Fatalf("el veredicto debe explicar qué política disparó: %+v", cur.Risk.MatchedPolicies)
	}
}

func TestPoliticaQueNoCasaNoEmiteNada(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(40)
	ps := []policy.Policy{politicaRiesgo("p-riesgo", policy.Action{Action: action.Lock})}
	if got := e.planPolicies(&cur, subjectFor(cur), ps); got != nil {
		t.Fatalf("40 no llega al umbral de 50: %+v", got)
	}
	if cur.Risk.MatchedPolicies == nil || len(cur.Risk.MatchedPolicies) != 0 {
		t.Fatalf("sin coincidencias la lista queda vacía, no nula: %+v", cur.Risk.MatchedPolicies)
	}
}

func TestPoliticaDeshabilitadaNoEmite(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(90)
	p := politicaRiesgo("p-riesgo", policy.Action{Action: action.Wipe})
	p.Enabled = false
	if got := e.planPolicies(&cur, subjectFor(cur), []policy.Policy{p}); got != nil {
		t.Fatalf("una política deshabilitada no dispara aunque case: %+v", got)
	}
	if len(cur.Risk.MatchedPolicies) != 0 {
		t.Fatalf("ni cuenta como coincidencia: %+v", cur.Risk.MatchedPolicies)
	}
}

// TestDosPoliticasMismaAccionSeDeduplican es el caso dorado de
// legacy/tests/test_engine_routes.py::test_repeated_policy_on_same_fence_is_deduped:
// dos políticas que piden la misma acción sobre el mismo dispositivo se
// colapsan en una sola ejecución por ciclo.
func TestDosPoliticasMismaAccionSeDeduplican(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(70)
	ps := []policy.Policy{
		politicaRiesgo("p1", policy.Action{Action: action.Notify, Params: map[string]any{"msg": "m1"}}),
		politicaRiesgo("p2", policy.Action{Action: action.Notify, Params: map[string]any{"msg": "m2"}}),
	}
	planned := e.planPolicies(&cur, subjectFor(cur), ps)
	if len(planned) != 2 {
		t.Fatalf("las dos políticas casan y planifican: %+v", planned)
	}
	var ejecutadas []Planned
	for _, p := range planned {
		if e.alreadyFired(p) {
			continue
		}
		ejecutadas = append(ejecutadas, p)
	}
	if len(ejecutadas) != 1 || ejecutadas[0].PolicyID != "p1" {
		t.Fatalf("solo la primera llega al conector: %+v", ejecutadas)
	}
	if len(cur.Risk.MatchedPolicies) != 2 {
		t.Fatalf("deduplicar la orden no borra el rastro de las dos políticas: %+v", cur.Risk.MatchedPolicies)
	}
}

func TestMatchedPoliciesGuardaElOrdenDelFichero(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(70)
	soloFuera := policy.Policy{ID: "p-fuera", Name: "Solo fuera", Enabled: true, Severity: risk.SeverityLow,
		When:    []policy.Condition{{Field: "fence_state", Op: policy.OpEq, Value: "outside"}},
		Actions: []policy.Action{{Action: action.Locate}}}
	ps := []policy.Policy{
		politicaRiesgo("p1", policy.Action{Action: action.Notify}),
		soloFuera,
		politicaRiesgo("p3", policy.Action{Action: action.Message}),
	}
	got := e.planPolicies(&cur, subjectFor(cur), ps)
	if len(got) != 2 || got[0].PolicyID != "p1" || got[1].PolicyID != "p3" {
		t.Fatalf("solo casan p1 y p3, en ese orden: %+v", got)
	}
	if len(cur.Risk.MatchedPolicies) != 2 ||
		cur.Risk.MatchedPolicies[0] != "p1" || cur.Risk.MatchedPolicies[1] != "p3" {
		t.Fatalf("matched_policies en el orden del fichero: %+v", cur.Risk.MatchedPolicies)
	}
}

// TestPoliticaSobreSenalPublicada comprueba que el sujeto lleva las señales que
// el ciclo publicó en el dispositivo: sin ellas, las plantillas de 1.x que
// miran signal:route_state o signal:device_health no casarían jamás.
func TestPoliticaSobreSenalPublicada(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(10)
	p := policy.Policy{ID: "p-ruta", Name: "Fuera de ruta", Enabled: true, Severity: risk.SeverityHigh,
		When:    []policy.Condition{{Field: "signal:route_state.route_state", Op: policy.OpEq, Value: "off_route"}},
		Actions: []policy.Action{{Action: action.Message}}}
	got := e.planPolicies(&cur, subjectFor(cur), []policy.Policy{p})
	if len(got) != 1 || got[0].PolicyID != "p-ruta" {
		t.Fatalf("la señal publicada debe resolver: %+v", got)
	}
	sinSenales := dispositivoConRiesgo(10)
	sinSenales.Signals = nil
	if got := e.planPolicies(&sinSenales, subjectFor(sinSenales), []policy.Policy{p}); got != nil {
		t.Fatalf("sin señales la condición no resuelve y no casa: %+v", got)
	}
}

// TestEvaluacionFallidaNoDisparaPoliticas: sin veredicto no hay evidencia
// (1.x deja fired_policies vacío cuando el evaluador revienta).
func TestEvaluacionFallidaNoDisparaPoliticas(t *testing.T) {
	e := motorMudo()
	cur := dispositivoConRiesgo(90)
	cur.EvaluationError = "pánico en el evaluador"
	cur.Risk = risk.Failed(errors.New("pánico en el evaluador"), guardT0)
	ps := []policy.Policy{politicaRiesgo("p1", policy.Action{Action: action.Wipe})}
	if got := e.planPolicies(&cur, subjectFor(cur), ps); got != nil {
		t.Fatalf("un dispositivo sin veredicto no dispara políticas: %+v", got)
	}
	if len(cur.Risk.MatchedPolicies) != 0 {
		t.Fatalf("ni deja rastro de coincidencias: %+v", cur.Risk.MatchedPolicies)
	}
}
