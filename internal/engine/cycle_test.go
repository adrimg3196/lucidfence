package engine

import (
	"context"
	"errors"
	"os"
	"runtime"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
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

// fleetAdapter devuelve siempre la misma flota (nada se mueve entre ciclos) y
// falla en los ciclos indicados: permite comprobar qué pasa con los
// dispositivos de un conector que se cae y se recupera.
type fleetAdapter struct {
	name    string
	devices []device.Device
	calls   int
	failOn  map[int]bool
}

func (f *fleetAdapter) Name() string { return f.name }

func (f *fleetAdapter) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true}
}

func (f *fleetAdapter) FetchDevices(context.Context) ([]device.Device, error) {
	f.calls++
	if f.failOn[f.calls] {
		return nil, errors.New("HTTP 503")
	}
	out := make([]device.Device, 0, len(f.devices))
	for _, d := range f.devices {
		p := *d.Location.Point
		d.Location.Point = &p
		out = append(out, d)
	}
	return out, nil
}

func (f *fleetAdapter) Execute(_ context.Context, dev device.Device, a action.Action, params map[string]any, dryRun bool) action.Result {
	return action.Result{Adapter: f.name, OK: true, DeviceID: dev.ID, DeviceName: dev.Name, Action: a,
		Params: params, DryRun: dryRun, Simulated: true}
}

func (f *fleetAdapter) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "simulated"}
}

// fleetDevice construye un dispositivo del conector name situado en p.
func fleetDevice(name, id string, p geo.Point) device.Device {
	return device.Device{ID: id, Name: id, Platform: "android", Provider: name,
		Location:   device.Location{Point: &p, Source: name},
		FenceState: device.Unknown, RouteState: device.Unassigned}
}

// TestConectorCaidoConservaSusDispositivos cubre C2: si un conector falla en
// un ciclo, sus dispositivos previos se conservan tal cual en devices.json
// (sin evaluarlos ni ejecutar acciones para ellos ese ciclo) y su salud
// refleja el error; al recuperarse no debe haber transiciones espurias ni
// acciones repetidas. Cada aserción es una función con nombre, como en
// TestRunOnceEvaluaFlotaDemo (gocyclo suma las clausuras anidadas).
func TestConectorCaidoConservaSusDispositivos(t *testing.T) {
	hq := geo.Point{Lat: 40.421, Lng: -3.708}
	alpha := &fleetAdapter{name: "alpha", devices: []device.Device{fleetDevice("alpha", "dev-alpha", hq)}}
	beta := &fleetAdapter{name: "beta", devices: []device.Device{fleetDevice("beta", "dev-beta", hq)}, failOn: map[int]bool{2: true}}
	e, org := newEngine(t, alpha, beta)

	t.Run("ciclo inicial", func(t *testing.T) { assertCicloInicial(t, runCicloOK(t, e)) })
	t.Run("conector caído", func(t *testing.T) { assertConectorCaido(t, runCicloOK(t, e), org) })
	t.Run("recuperación", func(t *testing.T) { assertRecuperacion(t, runCicloOK(t, e), org) })
}

func runCicloOK(t *testing.T, e *Engine) CycleStats {
	t.Helper()
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	return st
}

func assertCicloInicial(t *testing.T, st CycleStats) {
	t.Helper()
	if st.DevicesTotal != 2 || st.Transitions != 2 || st.ActionsExecuted != 2 {
		t.Fatalf("ambos conectores responden y entran en demo-hq: %+v", st)
	}
}

func assertConectorCaido(t *testing.T, st CycleStats, org *store.OrgStore) {
	t.Helper()
	if st.Providers["beta"].OK || st.Providers["beta"].Error != "HTTP 503" {
		t.Fatalf("la salud del conector caído debe reflejar el error: %+v", st.Providers)
	}
	if st.DevicesTotal != 1 || st.Transitions != 0 || st.ActionsPlanned != 0 {
		t.Fatalf("solo se evalúa lo que respondió: %+v", st)
	}
	ds, err := org.Devices()
	if err != nil {
		t.Fatal(err)
	}
	if len(ds) != 2 {
		t.Fatalf("devices.json debe conservar los dispositivos del conector caído: %+v", ds)
	}
	if kept := device.Index(ds)["dev-beta"]; kept.FenceState != device.Inside || kept.InsideFence != "demo-hq" {
		t.Fatalf("el dispositivo conservado mantiene su estado previo: %+v", kept)
	}
}

func assertRecuperacion(t *testing.T, st CycleStats, org *store.OrgStore) {
	t.Helper()
	if st.DevicesTotal != 2 || st.Transitions != 0 || st.ActionsExecuted != 0 {
		t.Fatalf("la recuperación no debe generar transiciones ni acciones espurias: %+v", st)
	}
	acts, err := org.RecentActions(100)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) != 2 {
		t.Fatalf("las acciones de entrada no deben repetirse: %d", len(acts))
	}
}
