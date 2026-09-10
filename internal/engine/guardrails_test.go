package engine

import (
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// guardT0 es el instante de referencia de todos los casos de guardarraíles.
var guardT0 = time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)

// fakeCooldowns es una memoria de cooldown en RAM con el mismo contrato que
// *store.OrgStore (engine.CooldownStore).
type fakeCooldowns struct {
	marks map[string]time.Time
	saves int
	err   error
}

func newFakeCooldowns() *fakeCooldowns { return &fakeCooldowns{marks: map[string]time.Time{}} }

func (f *fakeCooldowns) LastActionAt(deviceID string, a action.Action) (time.Time, bool) {
	at, ok := f.marks[deviceID+"|"+string(a)]
	return at, ok
}

func (f *fakeCooldowns) RecordActionAt(deviceID string, a action.Action, at time.Time) error {
	if f.err != nil {
		return f.err
	}
	f.saves++
	f.marks[deviceID+"|"+string(a)] = at
	return nil
}

// devA es el dispositivo de los casos; devB sirve para la allowlist de wipe.
func devA() device.Device { return device.Device{ID: "dev-a", Name: "A", Provider: "sim"} }
func devB() device.Device { return device.Device{ID: "dev-b", Name: "B", Provider: "sim"} }

// guardWith construye guardarraíles con el reloj congelado en guardT0.
func guardWith(enf settings.Enforcement, cd CooldownStore) Guardrails {
	return Guardrails{Enforcement: enf, Cooldowns: cd, Now: func() time.Time { return guardT0 }}
}

func TestObserveSiempreDryRunIncluidoWipe(t *testing.T) {
	g := guardWith(settings.Default().Enforcement, newFakeCooldowns())
	if g.Mode() != settings.ModeObserve {
		t.Fatalf("los ajustes de fábrica son observe, no %q", g.Mode())
	}
	for _, a := range action.All {
		dec := g.Decide(devA(), a)
		if !dec.Allow || !dec.DryRun || dec.Blocked {
			t.Fatalf("%s en observe debe ser dry-run y no bloqueada: %+v", a, dec)
		}
	}
}

func TestEnforcementVacioEquivaleAObserve(t *testing.T) {
	dec := (Guardrails{}).Decide(devA(), action.Wipe)
	if !dec.Allow || !dec.DryRun || dec.Blocked {
		t.Fatalf("sin configurar = observe: %+v", dec)
	}
	if (Guardrails{Enforcement: settings.Enforcement{Mode: "raro"}}).Mode() != settings.ModeObserve {
		t.Fatal("cualquier modo desconocido debe normalizarse a observe")
	}
}

// TestNormalizedEnforcementSoloSaneaElModo fija lo que el saneo NO hace: no
// toca las llaves, ni la ventana, ni las listas. No hace falta convertir la
// live_actions nula porque live() ya la trata como la lista vacía: ninguna
// acción en vivo.
func TestNormalizedEnforcementSoloSaneaElModo(t *testing.T) {
	enf, saneado := normalizedEnforcement(settings.Enforcement{Mode: "Enforce",
		AllowWipe: true, ActionCooldownSeconds: 3600})
	if enf.Mode != settings.ModeObserve || !saneado {
		t.Fatalf("un modo desconocido se sanea a observe y se avisa: %+v %v", enf, saneado)
	}
	if !enf.AllowWipe || enf.ActionCooldownSeconds != 3600 {
		t.Fatalf("el saneo no toca el resto del bloque: %+v", enf)
	}
	if enf.LiveActions != nil {
		t.Fatalf("el saneo no inventa una lista donde no la había: %+v", enf.LiveActions)
	}
	if enf, saneado := normalizedEnforcement(settings.Enforcement{Mode: settings.ModeEnforce}); enf.Mode != settings.ModeEnforce || saneado {
		t.Fatalf("enforce se respeta tal cual: %+v %v", enf, saneado)
	}
}

// TestEnforceSinLiveActionsNoEjecutaNadaEnVivo: la allowlist ausente es la
// allowlist vacía. Enforce con AllowWipe y sin live_actions no puede tocar un
// solo dispositivo de verdad; todo sale en dry-run.
func TestEnforceSinLiveActionsNoEjecutaNadaEnVivo(t *testing.T) {
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce, AllowWipe: true}, newFakeCooldowns())
	if g.Mode() != settings.ModeEnforce {
		t.Fatalf("mode: %q", g.Mode())
	}
	for _, a := range action.All {
		if dec := g.Decide(devA(), a); !dec.Allow || !dec.DryRun || dec.Blocked {
			t.Fatalf("live_actions nula no saca nada en vivo: %s -> %+v", a, dec)
		}
	}
}

func TestEnforceConLiveActionsDegradaLoNoListado(t *testing.T) {
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce,
		LiveActions: []action.Action{action.Message}}, newFakeCooldowns())
	if dec := g.Decide(devA(), action.Message); !dec.Allow || dec.DryRun {
		t.Fatalf("message está listada y sale en vivo: %+v", dec)
	}
	dec := g.Decide(devA(), action.Lock)
	if !dec.Allow || !dec.DryRun || dec.Blocked {
		t.Fatalf("lock no listada se degrada a dry-run, no se bloquea: %+v", dec)
	}
}

func TestListaVaciaPeroPresenteDegradaTodo(t *testing.T) {
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce,
		LiveActions: []action.Action{}}, newFakeCooldowns())
	for _, a := range action.All {
		if dec := g.Decide(devA(), a); !dec.Allow || !dec.DryRun {
			t.Fatalf("una lista vacía deja todo en dry-run: %s -> %+v", a, dec)
		}
	}
}

func TestWipeEnEnforceSinLlaveSeBloquea(t *testing.T) {
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce,
		LiveActions: []action.Action{action.Wipe}}, newFakeCooldowns())
	dec := g.Decide(devA(), action.Wipe)
	if dec.Allow || !dec.Blocked || dec.Code != BlockedWipeNotAllowed {
		t.Fatalf("wipe sin allow_wipe debe bloquearse: %+v", dec)
	}
	if !strings.Contains(dec.Reason, "allow_wipe") {
		t.Fatalf("el motivo debe nombrar la llave que falta: %q", dec.Reason)
	}
	if dec := g.Decide(devA(), action.Lock); !dec.Allow || dec.Blocked {
		t.Fatalf("la llave es solo de wipe: %+v", dec)
	}
}

func TestWipeAllowlistAcotaElRadio(t *testing.T) {
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce, AllowWipe: true,
		LiveActions: []action.Action{action.Wipe}, WipeAllowlist: []string{"dev-a"}}, newFakeCooldowns())
	if dec := g.Decide(devA(), action.Wipe); !dec.Allow || dec.DryRun || dec.Blocked {
		t.Fatalf("dev-a está en la allowlist y sale en vivo: %+v", dec)
	}
	dec := g.Decide(devB(), action.Wipe)
	if dec.Allow || !dec.Blocked || dec.Code != BlockedWipeNotInAllowlist {
		t.Fatalf("dev-b fuera de la allowlist debe bloquearse: %+v", dec)
	}
	if !strings.Contains(dec.Reason, "dev-b") {
		t.Fatalf("el motivo debe nombrar el dispositivo: %q", dec.Reason)
	}
}

func TestAllowlistVaciaNoAcotaNada(t *testing.T) {
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce, AllowWipe: true,
		LiveActions: []action.Action{action.Wipe}}, newFakeCooldowns())
	if dec := g.Decide(devB(), action.Wipe); !dec.Allow || dec.Blocked {
		t.Fatalf("sin allowlist la llave abierta basta: %+v", dec)
	}
}

func TestWipeBloqueadoNoArmaElCooldown(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce, ActionCooldownSeconds: 3600}, cd)
	dec := g.Decide(devA(), action.Wipe)
	blocked := action.Result{OK: false, Blocked: true, ErrorType: dec.Code, Action: action.Wipe, DeviceID: "dev-a"}
	if err := g.Record(devA(), action.Wipe, blocked); err != nil {
		t.Fatal(err)
	}
	if cd.saves != 0 {
		t.Fatal("un wipe bloqueado no arma el cooldown: abrir la llave debe permitir reintentar ya")
	}
	if _, marked := cd.LastActionAt("dev-a", action.Wipe); marked {
		t.Fatal("no debe quedar marca de un wipe bloqueado")
	}
}
