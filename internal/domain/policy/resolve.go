package policy

import (
	"strings"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// Fields es el catálogo explícito. No se debe modificar.
var Fields = []string{"risk_score", "severity", "fence_state", "route_state", "compliant", "platform", "inside_fence", "route_deviation_m", "dwell_seconds", "inventory.battery_level", "inventory.storage_free_gb", "inventory.encryption_enabled", "inventory.department", "inventory.ownership", "posture.rooted", "posture.country"}

// Subject aporta evidencia ya calculada; nunca la recalcula.
type Subject struct {
	Device  device.Device
	Verdict device.Verdict
	Signals risk.Signals
}

// NewSubject construye el sujeto sin alterar sus entradas.
func NewSubject(d device.Device, v device.Verdict, s risk.Signals) Subject {
	return Subject{Device: d, Verdict: v, Signals: s}
}

// Condition compara un campo con un literal JSON explícito.
type Condition struct {
	Field string `json:"field"`
	Op    Op     `json:"op"`
	Value any    `json:"value"`
}

// Resolve distingue desconocido de cero/false observados.
func Resolve(s Subject, field string) (any, bool) {
	if rest, ok := strings.CutPrefix(field, "signal:"); ok {
		name, key, valid := strings.Cut(rest, ".")
		if !valid || name == "" || key == "" {
			return nil, false
		}
		return s.Signals.Value(name, key)
	}
	switch field {
	case "risk_score":
		return pointerValue(s.Verdict.Score)
	case "severity":
		return textValue(s.Verdict.Severity)
	case "fence_state":
		return textValue(string(s.Device.FenceState))
	case "route_state":
		return textValue(string(s.Device.RouteState))
	case "compliant":
		return pointerValue(s.Device.Compliant)
	case "platform":
		return textValue(s.Device.Platform)
	case "inside_fence":
		return textValue(s.Device.InsideFence)
	case "route_deviation_m":
		return pointerValue(s.Device.RouteDeviationM)
	case "dwell_seconds":
		return s.Device.DwellSeconds, true
	}
	return resolveDetails(s.Device, field)
}

func resolveDetails(d device.Device, field string) (any, bool) {
	switch field {
	case "inventory.battery_level":
		return pointerValue(d.Inventory.BatteryLevel)
	case "inventory.storage_free_gb":
		return pointerValue(d.Inventory.StorageFreeGB)
	case "inventory.encryption_enabled":
		return pointerValue(d.Inventory.EncryptionEnabled)
	case "inventory.department":
		return textValue(d.Inventory.Department)
	case "inventory.ownership":
		return textValue(d.Inventory.Ownership)
	case "posture.rooted":
		return pointerValue(d.Posture.Rooted)
	case "posture.country":
		return textValue(d.Posture.Country)
	}
	return nil, false
}

func pointerValue[T bool | int | float64](p *T) (any, bool) {
	if p == nil {
		return nil, false
	}
	return *p, true
}

func textValue(s string) (any, bool) {
	if s == "" {
		return nil, false
	}
	return s, true
}

// Match no transforma la ausencia en desigualdad observada.
func (c Condition) Match(s Subject) bool {
	if c.Validate() != nil {
		return false
	}
	actual, ok := Resolve(s, c.Field)
	return ok && compare(actual, c.Op, c.Value)
}
