package engine

import (
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// enfCooldown son los ajustes de los casos: enforce con la ventana de fábrica.
func enfCooldown() settings.Enforcement {
	return settings.Enforcement{Mode: settings.ModeEnforce, AllowWipe: true, ActionCooldownSeconds: 3600}
}

// guardAt clona g con el reloj en at.
func guardAt(g Guardrails, at time.Time) Guardrails {
	g.Now = func() time.Time { return at }
	return g
}

func TestDestructivaSeEnfriaTrasEjecutarse(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(enfCooldown(), cd)
	if dec := g.Decide(devA(), action.Wipe); !dec.Allow {
		t.Fatalf("el primer wipe pasa: %+v", dec)
	}
	if err := g.Record(devA(), action.Wipe, action.Result{OK: true}); err != nil {
		t.Fatal(err)
	}
	dec := g.Decide(devA(), action.Wipe)
	if dec.Allow || dec.Blocked || dec.Code != SuppressedCooldown {
		t.Fatalf("el segundo ciclo inmediato queda suprimido, no bloqueado: %+v", dec)
	}
	if !strings.Contains(dec.Reason, "3600") {
		t.Fatalf("el motivo debe decir cuánto falta: %q", dec.Reason)
	}
}

func TestCooldownExpiraYVuelveAPermitir(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(enfCooldown(), cd)
	if err := g.Record(devA(), action.Wipe, action.Result{OK: true}); err != nil {
		t.Fatal(err)
	}
	if dec := guardAt(g, guardT0.Add(3599*time.Second)).Decide(devA(), action.Wipe); dec.Allow {
		t.Fatalf("dentro de la ventana sigue suprimida: %+v", dec)
	}
	if dec := guardAt(g, guardT0.Add(3601*time.Second)).Decide(devA(), action.Wipe); !dec.Allow {
		t.Fatalf("pasada la ventana vuelve a permitirse: %+v", dec)
	}
}

func TestMarcaEnElFuturoSuprime(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(enfCooldown(), cd)
	if err := guardAt(g, guardT0.Add(time.Hour)).Record(devA(), action.Wipe, action.Result{OK: true}); err != nil {
		t.Fatal(err)
	}
	if dec := g.Decide(devA(), action.Wipe); dec.Allow {
		t.Fatalf("un reloj hacia atrás no debe reabrir la ventana: %+v", dec)
	}
}

// TestCooldownPersistidoSobreviveAlReinicio es el caso dorado "cooldown not
// persisted across restart": un OrgStore nuevo sobre el mismo directorio ve
// la marca que dejó el anterior.
func TestCooldownPersistidoSobreviveAlReinicio(t *testing.T) {
	dir := t.TempDir()
	open := func() *store.OrgStore {
		t.Helper()
		s, err := store.Open(dir)
		if err != nil {
			t.Fatal(err)
		}
		o, err := s.Org("default")
		if err != nil {
			t.Fatal(err)
		}
		return o
	}
	g := guardWith(enfCooldown(), open())
	if err := g.Record(devA(), action.Wipe, action.Result{DryRun: true}); err != nil {
		t.Fatal(err)
	}
	reiniciado := guardWith(enfCooldown(), open())
	if dec := reiniciado.Decide(devA(), action.Wipe); dec.Allow || dec.Code != SuppressedCooldown {
		t.Fatalf("la supresión debe sobrevivir al reinicio: %+v", dec)
	}
}

func TestNoDestructivaNuncaSeEnfria(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(enfCooldown(), cd)
	for _, a := range []action.Action{action.Notify, action.Message, action.Locate, action.SetCompliance, action.Custom} {
		if err := g.Record(devA(), a, action.Result{OK: true}); err != nil {
			t.Fatal(err)
		}
		if dec := g.Decide(devA(), a); !dec.Allow {
			t.Fatalf("%s no se enfría nunca: %+v", a, dec)
		}
	}
	if cd.saves != 0 {
		t.Fatalf("las no destructivas no dejan entrada en cooldowns.json: %d", cd.saves)
	}
}

func TestFalloDelConectorNoArmaElCooldown(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(enfCooldown(), cd)
	fallo := action.Result{OK: false, DryRun: false, Error: "HTTP 503"}
	if err := g.Record(devA(), action.Lock, fallo); err != nil {
		t.Fatal(err)
	}
	if cd.saves != 0 {
		t.Fatal("un intento fallido no puede bloquear los reintentos durante toda la ventana")
	}
	if dec := g.Decide(devA(), action.Lock); !dec.Allow {
		t.Fatalf("se puede reintentar de inmediato: %+v", dec)
	}
}

func TestVentanaCeroDesactivaElGuardarrail(t *testing.T) {
	cd := newFakeCooldowns()
	g := guardWith(settings.Enforcement{Mode: settings.ModeEnforce, AllowWipe: true}, cd)
	if err := g.Record(devA(), action.Wipe, action.Result{OK: true}); err != nil {
		t.Fatal(err)
	}
	if cd.saves != 0 {
		t.Fatal("con la ventana a cero no se graba nada")
	}
	if dec := g.Decide(devA(), action.Wipe); !dec.Allow {
		t.Fatalf("con la ventana a cero no se suprime nada: %+v", dec)
	}
}

func TestSinAlmacenDeCooldownNoHaySupresion(t *testing.T) {
	g := guardWith(enfCooldown(), nil)
	if dec := g.Decide(devA(), action.Wipe); !dec.Allow {
		t.Fatalf("sin memoria no se puede suprimir: %+v", dec)
	}
	if err := g.Record(devA(), action.Wipe, action.Result{OK: true}); err != nil {
		t.Fatalf("Record sin memoria es un no-op, no un error: %v", err)
	}
}
