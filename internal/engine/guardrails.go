package engine

import (
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// Códigos de decisión. Los "blocked_*" viajan en action.Result.ErrorType y
// quedan en actions.jsonl; los "suppressed_*" solo alimentan los contadores
// del ciclo (una acción suprimida no se registra).
const (
	BlockedWipeNotAllowed     = "wipe_not_allowed"
	BlockedWipeNotInAllowlist = "wipe_not_in_allowlist"
	SuppressedCooldown        = "cooldown"
	SuppressedDuplicate       = "duplicate"
)

// CooldownStore es la memoria persistida de acciones destructivas
// (store.OrgStore la satisface). Se declara aquí, en el consumidor, para que
// el motor no dependa del tipo concreto y los tests puedan sustituirla.
type CooldownStore interface {
	LastActionAt(deviceID string, a action.Action) (time.Time, bool)
	RecordActionAt(deviceID string, a action.Action, at time.Time) error
}

// Guardrails es el ÚNICO sitio que decide si una orden sale en vivo. Los tres
// ficheros guardrails* del paquete están protegidos por CODEOWNERS (spec
// §9.2): este decide, guardrails_cooldown.go recuerda y guardrails_apply.go
// aplica. Ningún otro fichero fija el dry_run del resultado auditado ni abre
// la doble llave de wipe.
type Guardrails struct {
	Enforcement settings.Enforcement
	Cooldowns   CooldownStore
	Now         func() time.Time
}

// Decision es el veredicto para una acción concreta sobre un dispositivo
// concreto. Allow false con Blocked false es una supresión (no se ejecuta ni
// se registra); Allow false con Blocked true es un bloqueo (no se ejecuta,
// pero se registra para auditoría).
type Decision struct {
	Allow   bool
	DryRun  bool
	Blocked bool
	Code    string
	Reason  string
}

// Mode normaliza el modo: cualquier valor que no sea "enforce" es "observe".
func (g Guardrails) Mode() string {
	if g.Enforcement.Mode == settings.ModeEnforce {
		return settings.ModeEnforce
	}
	return settings.ModeObserve
}

// normalizedEnforcement sanea el modo del bloque de enforcement que el motor
// guarda y publica, con el mismo criterio de Mode(): cualquier valor que no
// sea "enforce" es "observe". Devuelve además si hubo que sanearlo, para que
// el motor pueda avisar de un settings.json con un modo que no existe. Solo
// toca el modo: el resto del bloque se publica tal cual llegó, y no hace
// falta convertir una live_actions nula porque live() ya la trata como la
// lista vacía (ninguna acción en vivo), igual que settings.Normalized().
func normalizedEnforcement(enf settings.Enforcement) (settings.Enforcement, bool) {
	mode := Guardrails{Enforcement: enf}.Mode()
	saneado := mode != enf.Mode
	enf.Mode = mode
	return enf, saneado
}

// now devuelve el reloj del motor en UTC (time.Now si no se inyectó otro).
func (g Guardrails) now() time.Time {
	if g.Now == nil {
		return time.Now().UTC()
	}
	return g.Now().UTC()
}

// live indica si la acción puede salir en vivo según enforcement.live_actions.
// La allowlist es cerrada en los dos sentidos: lo que no está listado nunca
// sale en vivo, y una lista ausente (nula) vale exactamente lo mismo que la
// lista vacía, NINGUNA. 1.x leía el nil como "todas"; 2.0 falla cerrado (spec
// §3 principio 3), que es además lo que declara el dominio
// (settings.Enforcement) y lo que se guarda en settings.json.
func (g Guardrails) live(a action.Action) bool {
	for _, la := range g.Enforcement.LiveActions {
		if la == a {
			return true
		}
	}
	return false
}

// Decide aplica el orden de la spec §5.4 a partir del segundo paso: cooldown,
// observe/enforce, allowlist de acciones en vivo y doble llave de wipe. El
// primer paso, el dedupe por ciclo, lo hace alreadyFired, que es quien tiene
// el estado del ciclo.
func (g Guardrails) Decide(d device.Device, a action.Action) Decision {
	if dec, cooled := g.cooldown(d, a); cooled {
		return dec
	}
	dryRun := g.Mode() != settings.ModeEnforce || !g.live(a)
	if !dryRun && a == action.Wipe {
		if dec, blocked := g.wipeKey(d); blocked {
			return dec
		}
	}
	return Decision{Allow: true, DryRun: dryRun}
}

// wipeKey es la doble llave: wipe en vivo exige allow_wipe y, si hay
// wipe_allowlist, que el dispositivo esté en ella. Un falso positivo de GPS
// jamás debe poder borrar un dispositivo por defecto.
func (g Guardrails) wipeKey(d device.Device) (Decision, bool) {
	if !g.Enforcement.AllowWipe {
		return Decision{Blocked: true, Code: BlockedWipeNotAllowed,
			Reason: "wipe bloqueado por guardarraíl: requiere enforcement.allow_wipe en los ajustes de la organización"}, true
	}
	if len(g.Enforcement.WipeAllowlist) == 0 {
		return Decision{}, false
	}
	for _, id := range g.Enforcement.WipeAllowlist {
		if id == d.ID {
			return Decision{}, false
		}
	}
	return Decision{Blocked: true, Code: BlockedWipeNotInAllowlist,
		Reason: fmt.Sprintf("wipe bloqueado: %q no está en enforcement.wipe_allowlist", d.ID)}, true
}
