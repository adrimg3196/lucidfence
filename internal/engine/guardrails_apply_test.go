package engine

import (
	"context"
	"log/slog"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

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
		LiveActions: []action.Action{action.Wipe}, ActionCooldownSeconds: 3600}, cd), ad)
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
