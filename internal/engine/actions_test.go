package engine

import (
	"context"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
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

func TestPlanTransition(t *testing.T) {
	fs := testFences()
	cur := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	enter := &transition.Transition{From: "none:outside", To: "demo-hq:inside"}
	got := PlanTransition(cur, enter, fs)
	if len(got) != 1 || got[0].Action.Action != action.Message || got[0].FenceID != "demo-hq" || got[0].Trigger != "on_enter" {
		t.Fatalf("on_enter: %+v", got)
	}
	cur = device.Device{ID: "d", FenceState: device.Outside}
	exit := &transition.Transition{From: "demo-hq:inside", To: "none:outside"}
	got = PlanTransition(cur, exit, fs)
	if len(got) != 1 || got[0].Action.Action != action.Notify || got[0].Trigger != "on_exit" {
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
	if got := e.planStanding(out, fs); len(got) != 1 || got[0].Action.Action != action.Lock || got[0].Trigger != "on_violation" {
		t.Fatalf("ciclo 2: dispara, got %+v", got)
	}
	in := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	e.planStanding(in, fs)
	if _, exists := e.violations["d|demo-hq"]; exists {
		t.Fatal("dentro debe borrar la clave del mapa, no ponerla a cero")
	}
}

func TestDedupePorCiclo(t *testing.T) {
	e := &Engine{fired: map[string]bool{}}
	p := Planned{Device: device.Device{ID: "d"}, Action: fence.Action{Action: action.Message}, FenceID: "f", Trigger: "on_enter"}
	if e.alreadyFired(p) || !e.alreadyFired(p) {
		t.Fatal("la segunda vez debe estar deduplicada")
	}
}

// adapterQueDesobedece devuelve siempre DryRun: false, imitando un conector
// mal escrito que ignora el parámetro dryRun de Execute.
type adapterQueDesobedece struct{ uem.Adapter }

func (adapterQueDesobedece) Execute(context.Context, device.Device, action.Action, map[string]any, bool) action.Result {
	return action.Result{OK: true, DryRun: false}
}

func TestExecuteImponeDryRunDelGuardarrail(t *testing.T) {
	e := &Engine{
		adapters: map[string]uem.Adapter{"fake": adapterQueDesobedece{}},
		guard:    Guardrails{Enforcement: EnforcementObserve},
		opts:     Options{Now: time.Now},
	}
	p := Planned{Device: device.Device{ID: "d", Provider: "fake"}, Action: fence.Action{Action: action.Message}, FenceID: "f", Trigger: "on_enter"}
	res := e.execute(context.Background(), p)
	if !res.DryRun {
		t.Fatalf("el guardarraíl es la única fuente de dry_run: got %+v", res)
	}
}
