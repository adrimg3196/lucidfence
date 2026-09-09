package battery

import (
	"context"
	"fmt"
	"math"
	"time"
)

// senalesDeRiesgo son los siete nombres que risk.Names declara y que el motor
// persiste en cada dispositivo desde M2. Van como literales porque
// internal/battery solo importa la biblioteca estándar (depguard,
// leaf-utils): la batería comprueba el contrato que el binario sirve, no el
// código con el que se compiló.
var senalesDeRiesgo = []string{
	"time_of_day", "shift_match", "device_health", "device_posture",
	"location_integrity", "zone_risk", "route_state",
}

// checkDwell comprueba el estado persistido expuesto por el binario real.
// No interpreta tiempo en unknown como permanencia física; desde M2 exige
// además que el ciclo publique las siete señales que explican el veredicto.
func checkDwell(ctx context.Context, env *Env) error {
	var out map[string]any
	code, err := env.GetJSON(ctx, "/api/v1/devices/dev-001", &out)
	if err != nil || code != 200 {
		return fmt.Errorf("code=%d err=%v", code, err)
	}
	raw, _ := out["fence_state_since"].(string)
	since, err := time.Parse(time.RFC3339Nano, raw)
	if err != nil || since.IsZero() {
		return fmt.Errorf("origen de permanencia ausente o inválido: %q", raw)
	}
	seconds, err := number(out, "dwell_seconds")
	if err != nil || seconds < 0 || math.Trunc(seconds) != seconds {
		return fmt.Errorf("permanencia inválida: %v, %v", out["dwell_seconds"], err)
	}
	signals, ok := out["signals"].(map[string]any)
	if !ok {
		return fmt.Errorf("el ciclo debe publicar las señales del veredicto: %v", out["signals"])
	}
	if len(signals) != len(senalesDeRiesgo) {
		return fmt.Errorf("señales: %d, quiero %d (%v)", len(signals), len(senalesDeRiesgo), signals)
	}
	for _, name := range senalesDeRiesgo {
		if _, exists := signals[name]; !exists {
			return fmt.Errorf("falta la señal %q: %v", name, signals)
		}
	}
	return nil
}
