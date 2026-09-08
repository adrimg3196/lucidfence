package risk

import (
	"math"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// Los defaults true de salud son compatibilidad, no observación de conformidad.
func TestHealthYPostureBooleanosExplicitos(t *testing.T) {
	for _, value := range []*bool{nil, ptr(false), ptr(true)} {
		d := device.Device{Compliant: value,
			Inventory: device.Inventory{EncryptionEnabled: value, Supervised: value, LockdownMode: value},
			Posture:   device.Posture{Rooted: value, OSOutdated: value, OsqueryConfigValid: value}}
		s := sig(d)
		for _, key := range []string{"compliant", "encryption"} {
			metric(t, s, "device_health", key, value == nil || *value)
		}
		for _, key := range []string{"rooted", "os_outdated"} {
			metric(t, s, "device_health", key, value != nil && *value)
		}
		for _, key := range []string{"encryption_off", "unsupervised", "lockdown_mode_off", "osquery_config_invalid"} {
			metric(t, s, "device_posture", key, value != nil && !*value)
		}
	}
}

func TestBatteryUmbralYDesconocido(t *testing.T) {
	for _, tc := range []struct {
		level *int
		want  bool
	}{
		{nil, false}, {ptr(0), true}, {ptr(14), true}, {ptr(15), true}, {ptr(16), false}, {ptr(100), false},
	} {
		metric(t, sig(device.Device{Inventory: device.Inventory{BatteryLevel: tc.level}}), "device_posture", "battery_critical", tc.want)
	}
}

func TestDiskUmbralYDatosAusentesNoFinitos(t *testing.T) {
	for _, tc := range []struct {
		total, free *float64
		want        bool
	}{
		{nil, nil, false}, {nil, ptr(1.0), false}, {ptr(100.0), nil, false},
		{ptr(0.0), ptr(0.0), false}, {ptr(-1.0), ptr(0.0), false},
		{ptr(100.0), ptr(0.0), true}, {ptr(100.0), ptr(9.999), true},
		{ptr(100.0), ptr(10.0), false}, {ptr(100.0), ptr(10.001), false},
		{ptr(math.NaN()), ptr(1.0), false}, {ptr(100.0), ptr(math.NaN()), false},
		{ptr(math.Inf(1)), ptr(1.0), false}, {ptr(100.0), ptr(math.Inf(-1)), false},
	} {
		d := device.Device{Inventory: device.Inventory{StorageTotalGB: tc.total, StorageFreeGB: tc.free}}
		metric(t, sig(d), "device_posture", "disk_low", tc.want)
	}
}

func TestOSHeuristicaLegacy(t *testing.T) {
	for _, version := range []string{"Android 12", "android 11", "iOS 15.7.2", "Windows 10 Pro", "WIN10"} {
		metric(t, sig(device.Device{Inventory: device.Inventory{OSVersion: version}}), "device_posture", "os_unpatched", true)
	}
	for _, version := range []string{"", "Android 15", "iOS 18.2", "Windows 11", "macOS 26.1", "Ubuntu 24.04"} {
		metric(t, sig(device.Device{Inventory: device.Inventory{OSVersion: version}}), "device_posture", "os_unpatched", false)
	}
}

func TestHardwareVocabularioYOrden(t *testing.T) {
	for _, health := range []map[string]string{
		nil, {}, {"nfc": "weird-status"}, {"uwb": "42"}, {"camera": "[1 2]"},
		{"baseband": "true", "camera": "ok", "bio": "Healthy", "nfc": "NORMAL"}, {"": "failed"},
	} {
		s := sig(device.Device{Posture: device.Posture{HardwareHealth: health}})
		metric(t, s, "device_posture", "hardware_degraded", false)
		metric(t, s, "device_posture", "hardware_degraded_components", []string{})
	}
	for _, word := range []string{"false", "degraded", "Failed", "ERROR", " degraded "} {
		d := device.Device{Posture: device.Posture{HardwareHealth: map[string]string{"uwb": word, "baseband": "false", "camera": "ok"}}}
		for range 20 {
			s := sig(d)
			metric(t, s, "device_posture", "hardware_degraded", true)
			metric(t, s, "device_posture", "hardware_degraded_components", []string{"baseband", "uwb"})
		}
	}
}
