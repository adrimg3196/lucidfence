package risk

import (
	"reflect"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

type weightCase struct {
	signal, key string
	value       any
	score       float64
	reason      string
}

func healthWeights() []weightCase {
	return []weightCase{
		{"device_health", "compliant", false, 25, "dispositivo no conforme"},
		{"device_health", "rooted", true, 15, "dispositivo con root/jailbreak"},
		{"device_health", "os_outdated", true, 10, "SO desactualizado"},
		{"device_posture", "disk_low", true, 8, "disco casi lleno (<10% libre)"},
		{"device_posture", "battery_critical", true, 6, "batería crítica (≤15%)"},
		{"device_posture", "os_unpatched", true, 12, "SO sin parchear de seguridad"},
		{"device_posture", "encryption_off", true, 15, "almacenamiento sin cifrar"},
		{"device_posture", "lockdown_mode_off", true, 10, "Lockdown Mode desactivado"},
		{"device_posture", "unsupervised", true, 10, "dispositivo sin supervisión (enrolamiento personal)"},
		{"device_posture", "hardware_degraded", true, 10, "salud de hardware degradada (battery, storage)"},
		{"device_posture", "osquery_config_invalid", true, 8, "configuración de osquery no válida"},
	}
}

func TestPesosSaludPostura(t *testing.T) {
	for _, tc := range healthWeights() {
		t.Run(tc.key, func(t *testing.T) {
			s := Signals{tc.signal: {tc.key: tc.value, "hardware_degraded_components": []string{"battery", "storage"}}}
			v := Evaluate(device.Device{}, s, noon)
			if *v.Score != tc.score || !reflect.DeepEqual(v.Reasons, []string{tc.reason}) {
				t.Fatalf("score=%v razones=%v", *v.Score, v.Reasons)
			}
		})
	}
}

func TestSaludPosturaOrdenSinDobleSO(t *testing.T) {
	s := Signals{"device_health": {}, "device_posture": {}}
	want := []string{}
	for _, tc := range healthWeights() {
		s[tc.signal][tc.key] = tc.value
		if tc.key != "os_unpatched" {
			want = append(want, tc.reason)
		}
	}
	s["device_posture"]["hardware_degraded_components"] = []any{"battery", 99, "storage"}
	v := Evaluate(device.Device{}, s, noon)
	if *v.Score != 100 || !reflect.DeepEqual(v.Reasons, want) {
		t.Fatalf("score=%v razones=%v", *v.Score, v.Reasons)
	}
}
