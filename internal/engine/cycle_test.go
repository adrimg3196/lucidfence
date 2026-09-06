package engine

import (
	"context"
	"os"
	"runtime"
	"testing"
)

// TestAccionesSeRegistranAunqueFalleSaveDevices deja el directorio de la
// organización en solo lectura tras precrear los .jsonl: SaveDevices no puede
// crear su temporal y falla, mientras los appends siguen funcionando. Las
// acciones ya ejecutadas contra el conector deben quedar en actions.jsonl y
// contarse en actions_executed; el fallo suma a persistence_errors (M1-R11) y
// sigue expuesto en Status().LastError.
func TestAccionesSeRegistranAunqueFalleSaveDevices(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("los permisos POSIX de solo lectura no aplican en Windows")
	}
	if os.Geteuid() == 0 {
		t.Skip("root ignora los permisos de solo lectura del directorio")
	}
	e, org := newEngine(t)
	for _, name := range []string{"events.jsonl", "actions.jsonl", "trail.jsonl", "stats.jsonl"} {
		if err := os.WriteFile(org.Path(name), nil, 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Chmod(org.Dir(), 0o500); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = os.Chmod(org.Dir(), 0o700) }() // para que TempDir pueda limpiar
	st, err := e.RunOnce(context.Background())
	if err == nil {
		t.Fatal("SaveDevices debe fallar con el directorio en solo lectura")
	}
	if st.ActionsPlanned == 0 || st.ActionsExecuted != st.ActionsPlanned {
		t.Fatalf("las acciones ejecutadas deben contarse: %+v", st)
	}
	acts, err := org.RecentActions(100)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) != st.ActionsPlanned {
		t.Fatalf("actions.jsonl debe registrar las %d acciones ejecutadas, tiene %d", st.ActionsPlanned, len(acts))
	}
	if st.PersistenceErrors < 1 {
		t.Fatalf("el fallo de SaveDevices debe contar en persistence_errors: %+v", st)
	}
	if e.Status().LastError == "" {
		t.Fatal("el fallo de SaveDevices debe seguir visible en Status().LastError")
	}
	if e.Status().Cycles != 0 {
		t.Fatalf("un ciclo con SaveDevices roto no cuenta como completado: %d", e.Status().Cycles)
	}
}
