package battery

import (
	"context"
	"fmt"
	"math"
	"time"
)

// checkDwell comprueba el estado persistido expuesto por el binario real.
// No interpreta tiempo en unknown como permanencia física ni exige señales M2.
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
	if _, exists := out["signals"]; exists {
		return fmt.Errorf("seed M1 no debe inventar señales: %v", out["signals"])
	}
	return nil
}
