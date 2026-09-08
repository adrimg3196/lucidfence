// Package risk produce siete señales explicables y puras del dispositivo.
// Los defaults neutros de compatibilidad no acreditan conformidad observada.
// No calcula veredictos ni conecta las señales al ciclo del motor.
package risk

import (
	"math"
	"reflect"
	"slices"
	"sort"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// Signal contiene métricas; una clave ausente o nil significa desconocido.
type Signal map[string]any

// Signals indexa las métricas por nombre de señal.
type Signals map[string]Signal

// Context aporta el reloj y los datasets del despliegue sin hacer I/O.
type Context struct {
	Now           time.Time
	ShiftZones    map[string]string
	ZoneRisk      map[string]float64
	OffHoursStart int
	OffHoursEnd   int
}

// Names declara el orden de evaluación. Los consumidores no deben modificarlo.
var Names = []string{
	"time_of_day", "shift_match", "device_health", "device_posture",
	"location_integrity", "zone_risk", "route_state",
}

// DefaultContext fija la jornada nocturna 20:00-07:00 sin consultar el reloj.
func DefaultContext(now time.Time) Context {
	return Context{Now: now, OffHoursStart: 20, OffHoursEnd: 7}
}

var providers = map[string]func(device.Device, Context) Signal{
	"time_of_day":        sigTimeOfDay,
	"shift_match":        sigShiftMatch,
	"device_health":      sigDeviceHealth,
	"device_posture":     sigDevicePosture,
	"location_integrity": sigLocationIntegrity,
	"zone_risk":          sigZoneRisk,
	"route_state":        sigRouteState,
}

// Compute evalúa en orden estable y aísla el fallo de cada proveedor.
func Compute(d device.Device, ctx Context) Signals {
	out := make(Signals, len(Names))
	for _, name := range Names {
		out[name] = safe(providers[name], d, ctx)
	}
	return out
}

func safe(fn func(device.Device, Context) Signal, d device.Device, ctx Context) (sig Signal) {
	defer func() {
		if recover() != nil || sig == nil {
			sig = Signal{}
		}
	}()
	if fn == nil {
		return Signal{}
	}
	return fn(d, ctx)
}

// Value distingue ausencia de false y cero explícitos.
func (s Signals) Value(name, key string) (any, bool) {
	v, ok := s[name][key]
	if !ok || v == nil {
		return nil, false
	}
	// Un nil tipado también serializa como null: no cambia de significado
	// entre Compute y la lectura de Device desde JSON.
	rv := reflect.ValueOf(v)
	switch rv.Kind() {
	case reflect.Chan, reflect.Func, reflect.Interface, reflect.Map, reflect.Pointer, reflect.Slice:
		if rv.IsNil() {
			return nil, false
		}
	}
	return v, true
}

// Raw copia los mapas y las listas producidas por Compute al contrato Device.
// Conserva mapas/listas nil y null explícitos; no normaliza ausencia a vacío.
// Otros valores any se conservan tal cual (no clona objetos arbitrarios).
func (s Signals) Raw() map[string]map[string]any {
	if s == nil {
		return nil
	}
	out := make(map[string]map[string]any, len(s))
	for name, sig := range s {
		if sig == nil {
			out[name] = nil
			continue
		}
		m := make(map[string]any, len(sig))
		for key, value := range sig {
			if list, ok := value.([]string); ok {
				value = slices.Clone(list)
			}
			m[key] = value
		}
		out[name] = m
	}
	return out
}

func sigTimeOfDay(_ device.Device, ctx Context) Signal {
	if ctx.Now.IsZero() {
		return Signal{"off_hours": false}
	}
	hour := ctx.Now.Hour()
	return Signal{"hour": hour, "off_hours": offHours(hour, ctx.OffHoursStart, ctx.OffHoursEnd)}
}

func offHours(hour, start, end int) bool {
	if start < 0 || start > 23 || end < 0 || end > 23 {
		start, end = 20, 7
	}
	if start > end {
		return hour >= start || hour < end
	}
	return hour >= start && hour < end
}

func sigShiftMatch(d device.Device, ctx Context) Signal {
	expected := strings.TrimSpace(ctx.ShiftZones[d.ID])
	if expected == "" {
		return Signal{"shift_known": false}
	}
	// Turno conocido no implica ubicación conocida. Solo outside observado
	// permite afirmar incumplimiento sin una geocerca identificada.
	if d.FenceState == device.Unknown || (d.InsideFence == "" && d.FenceState != device.Outside) {
		return Signal{"shift_known": true}
	}
	return Signal{"shift_known": true, "shift_match": d.InsideFence == expected}
}

// nil en salud adopta el default neutro legacy, no acredita una lectura sana.
func sigDeviceHealth(d device.Device, _ Context) Signal {
	return Signal{
		"compliant":   boolOr(d.Compliant, true),
		"rooted":      boolOr(d.Posture.Rooted, false),
		"encryption":  boolOr(d.Inventory.EncryptionEnabled, true),
		"os_outdated": boolOr(d.Posture.OSOutdated, false),
	}
}

func sigDevicePosture(d device.Device, _ Context) Signal {
	degraded := degradedComponents(d.Posture.HardwareHealth)
	return Signal{
		"disk_low":                     diskLow(d.Inventory),
		"battery_critical":             d.Inventory.BatteryLevel != nil && *d.Inventory.BatteryLevel <= 15,
		"os_unpatched":                 osUnpatched(d.Inventory.OSVersion),
		"encryption_off":               isFalse(d.Inventory.EncryptionEnabled),
		"lockdown_mode_off":            isFalse(d.Inventory.LockdownMode),
		"unsupervised":                 isFalse(d.Inventory.Supervised),
		"hardware_degraded":            len(degraded) > 0,
		"hardware_degraded_components": degraded,
		"osquery_config_invalid":       isFalse(d.Posture.OsqueryConfigValid),
	}
}

// Reexpone evidencia sin recalcularla; checks nil sigue siendo sin evaluar.
func sigLocationIntegrity(d device.Device, _ Context) Signal {
	li := d.LocationIntegrity
	sig := Signal{"suspicious": li.Suspicious, "checks": slices.Clone(li.Checks)}
	if li.SpeedKMH != nil && finite(*li.SpeedKMH) {
		sig["speed_kmh"] = *li.SpeedKMH
	}
	if li.DistanceKM != nil && finite(*li.DistanceKM) {
		sig["distance_km"] = *li.DistanceKM
	}
	return sig
}

func sigZoneRisk(d device.Device, ctx Context) Signal {
	value := 0.0
	if d.InsideFence != "" {
		if v, ok := ctx.ZoneRisk[d.InsideFence]; ok && finite(v) {
			value = v
		}
	}
	return Signal{"zone_risk": value}
}

// Desvío nil conserva el default legacy; no acredita ruta observada.
func sigRouteState(d device.Device, _ Context) Signal {
	deviation := 0.0
	if d.RouteDeviationM != nil && finite(*d.RouteDeviationM) {
		deviation = *d.RouteDeviationM
	}
	return Signal{"route_state": string(d.RouteState), "route_id": d.RouteID, "route_deviation_m": deviation}
}

func boolOr(v *bool, def bool) bool {
	if v == nil {
		return def
	}
	return *v
}

func isFalse(v *bool) bool { return v != nil && !*v }

func degradedComponents(health map[string]string) []string {
	out := []string{}
	for component, value := range health {
		if component == "" {
			continue
		}
		switch strings.ToLower(strings.TrimSpace(value)) {
		case "false", "degraded", "failed", "error":
			out = append(out, component)
		}
	}
	sort.Strings(out)
	return out
}

func finite(v float64) bool { return !math.IsNaN(v) && !math.IsInf(v, 0) }

func diskLow(inv device.Inventory) bool {
	if inv.StorageFreeGB == nil || inv.StorageTotalGB == nil {
		return false
	}
	free, total := *inv.StorageFreeGB, *inv.StorageTotalGB
	return total > 0 && finite(free) && finite(total) && free/total < 0.10
}

// Heurística de tokens de 1.x, no un catálogo de soporte ni un análisis CVE.
func osUnpatched(version string) bool {
	v := strings.ToLower(version)
	for _, token := range []string{"android 12", "android 11", "ios 15", "windows 10", "win10"} {
		if strings.Contains(v, token) {
			return true
		}
	}
	return false
}
