package engine

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// stayOf identifica la estancia en curso por el instante en que empezó. Sin
// FenceStateSince no hay estancia que identificar y devuelve la cadena vacía:
// no inventamos permanencia hacia atrás.
func stayOf(cur device.Device) string {
	if cur.FenceStateSince == nil {
		return ""
	}
	return cur.FenceStateSince.UTC().Format(time.RFC3339Nano)
}

// planDwell aplica rules.dwell_seconds: las acciones on_enter de una geocerca
// con permanencia configurada no salen en la transición (PlanTransition ya no
// las emite), sino en el primer ciclo en que el dispositivo lleve dentro al
// menos ese tiempo, y una sola vez por estancia. Así un paso fugaz por la
// geocerca no dispara nada.
//
// La marca se guarda como dispositivo|geocerca -> instante de inicio de la
// estancia ya disparada: comparar el instante distingue una estancia de la
// siguiente, y borrar la entrada al salir mantiene el mapa acotado a una
// entrada por dispositivo y geocerca.
func (e *Engine) planDwell(cur device.Device, fences []fence.Fence) []Planned {
	var out []Planned
	for _, f := range fences {
		if f.Rules.DwellSeconds <= 0 {
			continue
		}
		key := cur.ID + "|" + f.ID
		if cur.FenceState != device.Inside || cur.InsideFence != f.ID {
			delete(e.dwelled, key)
			continue
		}
		acts := f.ActionsFor(fence.OnEnter)
		stay := stayOf(cur)
		if len(acts) == 0 || stay == "" || cur.DwellSeconds < f.Rules.DwellSeconds || e.dwelled[key] == stay {
			continue
		}
		e.dwelled[key] = stay
		for _, a := range acts {
			out = append(out, fromFence(cur, a, f.ID, TriggerDwell, risk.SeverityMedium))
		}
	}
	return out
}

// planStanding dispara on_violation cada N ciclos mientras el dispositivo siga
// fuera; estar dentro resetea el contador de esa geocerca. La severidad es
// alta: una violación que persiste ciclo tras ciclo pesa más que el evento de
// geocerca que la abrió (1.x: _fire_standing_violation con "high").
func (e *Engine) planStanding(cur device.Device, fences []fence.Fence) []Planned {
	var out []Planned
	for _, f := range fences {
		acts := f.ActionsFor(fence.OnViolation)
		key := cur.ID + "|" + f.ID
		if cur.FenceState != device.Outside || len(acts) == 0 {
			delete(e.violations, key)
			continue
		}
		e.violations[key]++
		interval := f.Rules.ViolationIntervalCycles
		if interval < 1 {
			interval = 1
		}
		if e.violations[key]%interval != 0 {
			continue
		}
		for _, a := range acts {
			out = append(out, fromFence(cur, a, f.ID, string(fence.OnViolation), risk.SeverityHigh))
		}
	}
	return out
}
