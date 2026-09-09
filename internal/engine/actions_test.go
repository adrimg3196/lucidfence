package engine

import (
	"context"
	"log/slog"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

func testFences() []fence.Fence {
	return []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
		Actions: []fence.Action{
			{Action: action.Message, When: fence.OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido"}},
			{Action: action.Notify, When: fence.OnExit, Enabled: true},
			{Action: action.Locate, When: fence.OnUnknown, Enabled: true},
			{Action: action.Lock, When: fence.OnViolation, Enabled: true},
			{Action: action.Wipe, When: fence.OnEnter, Enabled: false},
		}}}
}

// recordingAdapter captura (acción, dryRun) de cada Execute, como el
// _RecordingAdapter de legacy/tests/test_enforcement.py.
type recordingAdapter struct {
	uem.Adapter
	calls []struct {
		Action action.Action
		DryRun bool
	}
}

func (r *recordingAdapter) Name() string { return "rec" }

func (r *recordingAdapter) Execute(_ context.Context, dev device.Device, a action.Action, _ map[string]any, dryRun bool) action.Result {
	r.calls = append(r.calls, struct {
		Action action.Action
		DryRun bool
	}{a, dryRun})
	return action.Result{Adapter: "rec", OK: true, DeviceID: dev.ID, DeviceName: dev.Name, Action: a, DryRun: dryRun}
}

// engineWith monta un motor mínimo (sin store) con los guardarraíles dados.
func engineWith(g Guardrails, ad *recordingAdapter) *Engine {
	return &Engine{
		adapters: map[string]uem.Adapter{"sim": ad},
		guard:    g,
		fired:    map[string]bool{},
		opts:     Options{Now: func() time.Time { return guardT0 }, Logger: slog.New(slog.DiscardHandler)},
	}
}

func TestPlanTransition(t *testing.T) {
	fs := testFences()
	cur := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	enter := &transition.Transition{From: "none:outside", To: "demo-hq:inside"}
	got := PlanTransition(cur, enter, fs)
	if len(got) != 1 || got[0].Action != action.Message || got[0].FenceID != "demo-hq" || got[0].Trigger != "on_enter" {
		t.Fatalf("on_enter: %+v", got)
	}
	if got[0].Params["text"] != "Bienvenido" {
		t.Fatalf("los parámetros de la geocerca viajan en Planned: %+v", got[0].Params)
	}
	cur = device.Device{ID: "d", FenceState: device.Outside}
	exit := &transition.Transition{From: "demo-hq:inside", To: "none:outside"}
	got = PlanTransition(cur, exit, fs)
	if len(got) != 1 || got[0].Action != action.Notify || got[0].Trigger != "on_exit" {
		t.Fatalf("on_exit: %+v", got)
	}
	cur = device.Device{ID: "d", FenceState: device.Unknown, LastInsideFence: "demo-hq"}
	unk := &transition.Transition{From: "demo-hq:inside", To: "none:unknown"}
	got = PlanTransition(cur, unk, fs)
	if len(got) != 2 {
		t.Fatalf("a unknown: on_exit de la geocerca previa + on_unknown: %+v", got)
	}
	if PlanTransition(cur, nil, fs) != nil {
		t.Fatal("sin transición no hay plan")
	}
}

func TestStandingViolationCadaNCiclos(t *testing.T) {
	fs := testFences()
	fs[0].Rules.ViolationIntervalCycles = 2
	e := &Engine{violations: map[string]int{}}
	out := device.Device{ID: "d", FenceState: device.Outside}
	if got := e.planStanding(out, fs); len(got) != 0 {
		t.Fatalf("ciclo 1 de 2: nada, got %+v", got)
	}
	if got := e.planStanding(out, fs); len(got) != 1 || got[0].Action != action.Lock || got[0].Trigger != "on_violation" {
		t.Fatalf("ciclo 2: dispara, got %+v", got)
	}
	in := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	e.planStanding(in, fs)
	if _, exists := e.violations["d|demo-hq"]; exists {
		t.Fatal("dentro debe borrar la clave del mapa, no ponerla a cero")
	}
}

// TestDedupeColapsaLosDosCaminos: con la clave de 1.x (sin trigger), la misma
// orden sobre la misma geocerca sale una vez por ciclo aunque la pidan dos
// disparadores distintos.
func TestDedupeColapsaLosDosCaminos(t *testing.T) {
	e := &Engine{fired: map[string]bool{}}
	enter := Planned{Device: device.Device{ID: "d"}, Action: action.Lock, FenceID: "f", Trigger: "on_enter"}
	violation := Planned{Device: device.Device{ID: "d"}, Action: action.Lock, FenceID: "f", Trigger: "on_violation"}
	if e.alreadyFired(enter) {
		t.Fatal("la primera vez pasa")
	}
	if !e.alreadyFired(violation) {
		t.Fatal("mismo dispositivo, acción y geocerca por otro camino: debe deduplicarse")
	}
	otra := Planned{Device: device.Device{ID: "d"}, Action: action.Lock, FenceID: "g", Trigger: "on_enter"}
	if e.alreadyFired(otra) {
		t.Fatal("otra geocerca es otra acción")
	}
}

// adapterQueDesobedece imita un conector mal escrito que ignora el parámetro
// dryRun de Execute.
type adapterQueDesobedece struct{ uem.Adapter }

func (adapterQueDesobedece) Execute(context.Context, device.Device, action.Action, map[string]any, bool) action.Result {
	return action.Result{OK: true, DryRun: false}
}

func TestExecuteImponeDryRunDelGuardarrail(t *testing.T) {
	e := &Engine{
		adapters: map[string]uem.Adapter{"fake": adapterQueDesobedece{}},
		guard:    guardWith(settings.Default().Enforcement, nil),
		opts:     Options{Now: time.Now},
	}
	p := Planned{Device: device.Device{ID: "d", Provider: "fake"}, Action: action.Message, FenceID: "f", Trigger: "on_enter"}
	res := e.execute(context.Background(), p, true)
	if !res.DryRun {
		t.Fatalf("el guardarraíl es la única fuente de dry_run: got %+v", res)
	}
}

// TestApplyBloqueaElWipeSinLlave: el conector jamás llega a ver el wipe
// bloqueado, el resultado se registra y no arma el cooldown.
func TestApplyBloqueaElWipeSinLlave(t *testing.T) {
	cd := newFakeCooldowns()
	ad := &recordingAdapter{}
	e := engineWith(guardWith(settings.Enforcement{Mode: settings.ModeEnforce,
		ActionCooldownSeconds: 3600}, cd), ad)
	st := &CycleStats{}
	res, logged := e.apply(context.Background(), Planned{Device: devA(), Action: action.Wipe, FenceID: "f", Trigger: "on_enter"}, st)
	if !logged || !res.Blocked || res.OK || res.ErrorType != BlockedWipeNotAllowed {
		t.Fatalf("un bloqueo se registra con blocked y error_type: %+v", res)
	}
	if len(ad.calls) != 0 {
		t.Fatalf("el conector jamás ve el wipe bloqueado: %+v", ad.calls)
	}
	if st.ActionsBlocked != 1 || st.ActionsExecuted != 0 {
		t.Fatalf("contadores: %+v", st)
	}
	if cd.saves != 0 {
		t.Fatal("un bloqueo no arma el cooldown")
	}
}

// TestApplySuprimePorCooldown: la segunda vez en la ventana no se ejecuta ni
// se registra, solo suma a actions_suppressed.
func TestApplySuprimePorCooldown(t *testing.T) {
	cd := newFakeCooldowns()
	ad := &recordingAdapter{}
	e := engineWith(guardWith(settings.Enforcement{Mode: settings.ModeEnforce, AllowWipe: true,
		LiveActions: []action.Action{action.Wipe}, ActionCooldownSeconds: 3600}, cd), ad)
	st := &CycleStats{}
	p := Planned{Device: devA(), Action: action.Wipe, FenceID: "f", Trigger: "on_violation", Severity: "critical"}
	res, logged := e.apply(context.Background(), p, st)
	if !logged || res.DryRun || res.Severity != "critical" {
		t.Fatalf("el primer wipe sale en vivo y hereda la severidad: %+v", res)
	}
	if _, logged := e.apply(context.Background(), p, st); logged {
		t.Fatal("la segunda vez queda suprimida y no se registra")
	}
	if st.ActionsExecuted != 1 || st.ActionsSuppressed != 1 {
		t.Fatalf("contadores: %+v", st)
	}
	if len(ad.calls) != 1 || ad.calls[0].DryRun {
		t.Fatalf("el conector solo ve la primera, y en vivo: %+v", ad.calls)
	}
}

// TestApplyDegradaLoNoListado es el caso dorado de 1.x
// (test_enforce_live_actions_gates_per_action) a nivel de motor.
func TestApplyDegradaLoNoListado(t *testing.T) {
	ad := &recordingAdapter{}
	e := engineWith(guardWith(settings.Enforcement{Mode: settings.ModeEnforce,
		LiveActions: []action.Action{action.Message}}, newFakeCooldowns()), ad)
	st := &CycleStats{}
	e.apply(context.Background(), Planned{Device: devA(), Action: action.Message, FenceID: "f"}, st)
	e.apply(context.Background(), Planned{Device: devA(), Action: action.Lock, FenceID: "f"}, st)
	if len(ad.calls) != 2 || ad.calls[0].DryRun || !ad.calls[1].DryRun {
		t.Fatalf("message en vivo, lock en dry-run: %+v", ad.calls)
	}
	if st.ActionsBlocked != 0 || st.ActionsExecuted != 2 {
		t.Fatalf("degradar no es bloquear: %+v", st)
	}
}
