// Package transition evalúa la pertenencia a geocerca de un dispositivo y
// detecta cambios de estado entre ciclos. Semántica 1.x: la primera geocerca
// (en orden de lista) que contiene el punto gana; sin ubicación válida el
// estado es unknown, nunca outside.
package transition

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Transition es un cambio de clave de estado.
type Transition struct {
	At         time.Time `json:"at"`
	DeviceID   string    `json:"device_id"`
	DeviceName string    `json:"device_name"`
	From       string    `json:"from"`
	To         string    `json:"to"`
}

// EvaluateFence devuelve el estado y la geocerca contenedora.
func EvaluateFence(loc *geo.Point, fences []fence.Fence) (device.FenceState, string) {
	if loc == nil || loc.Valid() != nil {
		return device.Unknown, ""
	}
	for _, f := range fences {
		if f.Contains(*loc) {
			return device.Inside, f.ID
		}
	}
	return device.Outside, ""
}

// Key compone la clave "<fence|none>:<estado>".
func Key(insideID string, state device.FenceState) string {
	if insideID == "" {
		insideID = "none"
	}
	return insideID + ":" + string(state)
}

// Evaluate rellena los campos de geocerca de cur a partir de prev y devuelve
// la transición si la clave cambia. prev puede ser nil (primer ciclo).
func Evaluate(prev *device.Device, cur *device.Device, fences []fence.Fence, at time.Time) *Transition {
	state, inside := EvaluateFence(cur.Location.Point, fences)
	cur.FenceState, cur.InsideFence = state, inside
	switch state {
	case device.Unknown:
		if prev != nil {
			cur.LastInsideFence = prev.InsideFence
			if cur.LastInsideFence == "" {
				cur.LastInsideFence = prev.LastInsideFence
			}
		}
	default:
		cur.LastInsideFence = inside
	}
	prevKey := "none:unknown"
	if prev != nil {
		prevKey = Key(prev.InsideFence, prev.FenceState)
	}
	curKey := Key(inside, state)
	if prevKey == curKey {
		return nil
	}
	return &Transition{At: at, DeviceID: cur.ID, DeviceName: cur.Name, From: prevKey, To: curKey}
}
