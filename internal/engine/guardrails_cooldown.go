package engine

import (
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// window es la ventana de cooldown vigente. Cero desactiva el guardarraíl en
// los dos sentidos (ni consulta ni graba), igual que no tener memoria.
func (g Guardrails) window() time.Duration {
	if g.Cooldowns == nil || g.Enforcement.ActionCooldownSeconds <= 0 {
		return 0
	}
	return time.Duration(g.Enforcement.ActionCooldownSeconds) * time.Second
}

// cooldown suprime una acción destructiva repetida dentro de la ventana. La
// comparación es la de 1.x (`now - last < ventana`), así que una marca en el
// futuro (reloj ajustado hacia atrás) también suprime: es lo conservador para
// una acción irreversible.
func (g Guardrails) cooldown(d device.Device, a action.Action) (Decision, bool) {
	w := g.window()
	if w == 0 || !a.Destructive() {
		return Decision{}, false
	}
	last, marked := g.Cooldowns.LastActionAt(d.ID, a)
	if !marked {
		return Decision{}, false
	}
	elapsed := g.now().Sub(last)
	if elapsed >= w {
		return Decision{}, false
	}
	remaining := int((w - elapsed).Seconds())
	if remaining < 1 {
		remaining = 1
	}
	return Decision{Code: SuppressedCooldown,
		Reason: fmt.Sprintf("%s en cooldown; reintenta en %d s", a, remaining)}, true
}

// Record arma el cooldown de una acción destructiva que fue efectiva: un
// dry-run cuenta (se sabe qué habría pasado) y un ok real también, pero un
// fallo del conector o un bloqueo del guardarraíl no, para que se pueda
// reintentar de inmediato.
func (g Guardrails) Record(d device.Device, a action.Action, res action.Result) error {
	if g.window() == 0 || !a.Destructive() || !effective(res) {
		return nil
	}
	return g.Cooldowns.RecordActionAt(d.ID, a, g.now())
}

// effective traduce el "effective" de 1.x: dry-run u ok. El tercer término de
// 1.x (`delegated`) no existe en action.Result.
func effective(res action.Result) bool { return res.DryRun || res.OK }
