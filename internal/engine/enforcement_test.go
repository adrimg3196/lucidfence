package engine

import (
	"context"
	"os"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// TestElCicloRecargaElEnforcementDelStore comprueba el rollout real: el
// operador cambia settings.json y el ciclo siguiente ya manda en vivo lo
// listado, sin reiniciar el proceso. La fixture demo planifica tres
// "message on_enter" (dev-001, dev-003 y dev-006) y ninguna acción
// destructiva, así que aquí se comprueba el camino en vivo; la degradación
// de lo no listado la cubren TestEnforceConLiveActionsDegradaLoNoListado y
// TestApplyDegradaLoNoListado, y la rama del bucle queda como red por si
// T14 añade acciones de política a la demo.
func TestElCicloRecargaElEnforcementDelStore(t *testing.T) {
	e, org := newEngine(t)
	set, err := org.Settings()
	if err != nil {
		t.Fatal(err)
	}
	set.Enforcement = settings.Enforcement{Mode: settings.ModeEnforce,
		LiveActions: []action.Action{action.Message}, ActionCooldownSeconds: 3600}
	if err := org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if e.Status().Enforcement.Mode != settings.ModeEnforce {
		t.Fatalf("el estado debe publicar el enforcement recargado: %+v", e.Status().Enforcement)
	}
	if st.ActionsExecuted == 0 || st.ActionsBlocked != 0 {
		t.Fatalf("nada que bloquear en la demo: %+v", st)
	}
	acts, err := org.RecentActions(100)
	if err != nil {
		t.Fatal(err)
	}
	var vivos int
	for _, a := range acts {
		if a.Action == action.Message {
			if a.DryRun {
				t.Fatalf("message está en live_actions y debe salir en vivo: %+v", a)
			}
			vivos++
			continue
		}
		if !a.DryRun {
			t.Fatalf("lo que no está en live_actions se degrada a dry-run: %+v", a)
		}
	}
	if vivos == 0 {
		t.Fatal("el ciclo demo debe haber ejecutado al menos un message en vivo")
	}
}

// TestAjustesIlegiblesDejanElMotorEnObserve: settings.json corrupto no puede
// dejar al motor en un enforcement desconocido.
func TestAjustesIlegiblesDejanElMotorEnObserve(t *testing.T) {
	e, org := newEngine(t)
	if err := os.WriteFile(org.Path("settings.json"), []byte("{no es json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	if e.Status().Enforcement.Mode != settings.ModeObserve {
		t.Fatalf("unos ajustes ilegibles caen a observe: %+v", e.Status().Enforcement)
	}
}
