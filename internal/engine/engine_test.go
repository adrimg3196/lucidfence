package engine

import (
	"bytes"
	"context"
	"errors"
	"log/slog"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
)

func newEngine(t *testing.T, adapters ...uem.Adapter) (*Engine, *store.OrgStore) {
	t.Helper()
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	if len(adapters) == 0 {
		adapters = []uem.Adapter{simulation.New(simulation.DefaultSeed(), func() time.Time { return now })}
	}
	return New(org, adapters, Options{Mode: "simulation", Interval: 50 * time.Millisecond, Now: func() time.Time { return now }}), org
}

//nolint:gocyclo // aserciones secuenciales sobre un único ciclo demo, no lógica de producción.
func TestRunOnceEvaluaFlotaDemo(t *testing.T) {
	e, org := newEngine(t)
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.DevicesTotal != 6 || st.Inside < 2 || st.Transitions != 6 || st.Providers["simulation"].Devices != 6 || !st.Providers["simulation"].OK {
		t.Fatalf("stats: %+v", st)
	}
	ds, _ := org.Devices()
	idx := device.Index(ds)
	if idx["dev-001"].FenceState != device.Inside || idx["dev-001"].InsideFence != "demo-hq" {
		t.Fatalf("dev-001 debe estar en demo-hq: %+v", idx["dev-001"])
	}
	if idx["dev-004"].FenceState != device.Outside || idx["dev-005"].InsideFence != "warehouse-poly" {
		t.Fatalf("dev-004 fuera, dev-005 en almacén: %+v %+v", idx["dev-004"], idx["dev-005"])
	}
	if idx["dev-002"].RouteState != device.OnRoute || idx["dev-002"].RouteID != "route-centro" {
		t.Fatalf("dev-002 en ruta: %+v", idx["dev-002"])
	}
	evs, _ := org.RecentEvents(100)
	found := false
	for _, ev := range evs {
		if ev.DeviceID == "dev-001" && ev.From == "none:unknown" && ev.To == "demo-hq:inside" {
			found = true
		}
	}
	if !found {
		t.Fatalf("falta la transición de dev-001: %+v", evs)
	}
	acts, _ := org.RecentActions(100)
	if len(acts) == 0 || st.ActionsExecuted != len(acts) {
		t.Fatalf("acciones: %d vs %d", len(acts), st.ActionsExecuted)
	}
	for _, a := range acts {
		if !a.DryRun || !a.Simulated || a.Trigger == "" {
			t.Fatalf("en observe todo es dry-run: %+v", a)
		}
	}
	tr, _ := org.Trail("dev-001", 10)
	if len(tr) != 1 {
		t.Fatalf("trail: %d", len(tr))
	}
	st2, _ := e.RunOnce(context.Background())
	if st2.Transitions >= 6 {
		t.Fatalf("segundo ciclo no repite las transiciones iniciales: %+v", st2)
	}
	if e.Status().Cycles != 2 || e.Status().Enforcement != "observe" || e.Status().LastCycle == nil {
		t.Fatalf("status: %+v", e.Status())
	}
}

type slowAdapter struct {
	uem.Adapter
	release chan struct{}
	started chan struct{}
	once    sync.Once
}

func (s *slowAdapter) FetchDevices(ctx context.Context) ([]device.Device, error) {
	s.once.Do(func() { close(s.started) })
	<-s.release
	return s.Adapter.FetchDevices(ctx)
}

func TestRunOnceNoSolapaCiclos(t *testing.T) {
	slow := &slowAdapter{Adapter: simulation.New(simulation.DefaultSeed(), time.Now), release: make(chan struct{}), started: make(chan struct{})}
	e, _ := newEngine(t, slow)
	done := make(chan struct{})
	go func() { _, _ = e.RunOnce(context.Background()); close(done) }()
	<-slow.started
	if _, err := e.RunOnce(context.Background()); !errors.Is(err, ErrCycleInProgress) {
		t.Fatalf("esperaba ErrCycleInProgress, got %v", err)
	}
	close(slow.release)
	<-done
}

type failing struct{ uem.Adapter }

func (failing) Name() string { return "broken" }
func (failing) FetchDevices(context.Context) ([]device.Device, error) {
	return nil, errors.New("HTTP 401")
}

type panicking struct{ uem.Adapter }

func (panicking) Name() string                                          { return "panicky" }
func (panicking) FetchDevices(context.Context) ([]device.Device, error) { panic("boom") }

func TestProveedorRotoNoTumbaElCiclo(t *testing.T) {
	sim := simulation.New(simulation.DefaultSeed(), time.Now)
	e, _ := newEngine(t, failing{sim}, panicking{sim}, sim)
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.DevicesTotal != 6 || st.Providers["broken"].OK || st.Providers["broken"].Error != "HTTP 401" || st.Providers["panicky"].OK {
		t.Fatalf("%+v", st.Providers)
	}
}

func TestStartStopEjecutaCiclosPeriodicos(t *testing.T) {
	e, _ := newEngine(t)
	ctx, cancel := context.WithCancel(context.Background())
	e.Start(ctx)
	deadline := time.Now().Add(2 * time.Second)
	for e.Status().Cycles < 2 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if !e.Status().Running || e.Status().NextCycleAt == nil {
		t.Fatalf("status en marcha: %+v", e.Status())
	}
	cancel()
	e.Stop()
	if e.Status().Running || e.Status().Cycles < 2 {
		t.Fatalf("tras Stop: %+v", e.Status())
	}
	_ = action.All
}

// TestErroresDePersistenciaSeCuentan convierte events.jsonl en un directorio
// para que AppendEvent falle con EISDIR en cada transición: el ciclo debe
// seguir, registrar los fallos y no perder las acciones ejecutadas.
func TestErroresDePersistenciaSeCuentan(t *testing.T) {
	e, org := newEngine(t)
	if err := os.Mkdir(org.Path("events.jsonl"), 0o755); err != nil {
		t.Fatal(err)
	}
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.Transitions != 6 {
		t.Fatalf("transitions: %d", st.Transitions)
	}
	if st.PersistenceErrors < 6 {
		t.Fatalf("persistence_errors: %d", st.PersistenceErrors)
	}
	acts, _ := org.RecentActions(100)
	if len(acts) == 0 || st.ActionsExecuted != len(acts) {
		t.Fatalf("las acciones deben seguir ejecutándose y persistiéndose: %d vs %d", st.ActionsExecuted, len(acts))
	}
}

// namedAdapter permite dar el mismo Name() a dos instancias distintas para
// probar la deduplicación de conectores en New.
type namedAdapter struct {
	uem.Adapter
	name string
	tag  string
}

func (n namedAdapter) Name() string { return n.name }

func TestNewIgnoraConectoresDuplicados(t *testing.T) {
	var buf bytes.Buffer
	logger := slog.New(slog.NewTextHandler(&buf, nil))
	sim := simulation.New(simulation.DefaultSeed(), time.Now)
	first := namedAdapter{Adapter: sim, name: "dup", tag: "first"}
	second := namedAdapter{Adapter: sim, name: "dup", tag: "second"}
	e := New(nil, []uem.Adapter{first, second}, Options{Logger: logger})
	if len(e.order) != 1 || e.order[0] != "dup" {
		t.Fatalf("order debe tener una sola entrada por nombre: %v", e.order)
	}
	if got := e.adapters["dup"].(namedAdapter).tag; got != "first" {
		t.Fatalf("el primer conector registrado debe prevalecer, got %q", got)
	}
	if !strings.Contains(buf.String(), "conector duplicado") {
		t.Fatalf("debe avisar del duplicado: %s", buf.String())
	}
}

// TestStartReentranteYStopAutosuficiente cubre M1-R (menores 4): una segunda
// llamada a Start no debe lanzar otro bucle, y Stop debe terminar sin que el
// llamante cancele el contexto externo (Start deriva su propio cancel).
func TestStartReentranteYStopAutosuficiente(t *testing.T) {
	e, _ := newEngine(t)
	e.Start(context.Background())
	e.Start(context.Background()) // reentrante: si lanzara un segundo bucle, Stop se quedaría colgado esperando el primero.
	deadline := time.Now().Add(2 * time.Second)
	for e.Status().Cycles < 1 && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if !e.Status().Running {
		t.Fatal("debería seguir en marcha")
	}
	done := make(chan struct{})
	go func() { e.Stop(); close(done) }()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Stop no debe depender de que el llamante cancele el contexto externo")
	}
	if e.Status().Running {
		t.Fatal("tras Stop no debe seguir corriendo")
	}
	cyclesAfterStop := e.Status().Cycles
	time.Sleep(100 * time.Millisecond)
	if e.Status().Cycles != cyclesAfterStop {
		t.Fatal("el bucle debe haberse detenido de verdad, no solo la bandera running")
	}
	e.Stop() // idempotente: no debe panicar ni bloquear.
}

// TestUltimoErrorDeCicloVisibleEnStatus rompe SaveDevices (devices.json es un
// directorio) para comprobar que un ciclo fallido no incrementa Cycles ni
// sustituye LastCycle, pero deja el error en Status().LastError; un ciclo
// correcto posterior lo vacía.
func TestUltimoErrorDeCicloVisibleEnStatus(t *testing.T) {
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Now()
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(org.Path("devices.json"), 0o755); err != nil {
		t.Fatal(err)
	}
	e := New(org, nil, Options{Now: func() time.Time { return now }})
	if _, err := e.RunOnce(context.Background()); err == nil {
		t.Fatal("SaveDevices debe fallar con devices.json como directorio")
	}
	if e.Status().Cycles != 0 {
		t.Fatalf("un ciclo fallido no debe incrementar Cycles: %d", e.Status().Cycles)
	}
	if e.Status().LastCycle != nil {
		t.Fatalf("un ciclo fallido no debe sustituir LastCycle: %+v", e.Status().LastCycle)
	}
	if e.Status().LastError == "" {
		t.Fatal("LastError debe reflejar el fallo")
	}
	if err := os.Remove(org.Path("devices.json")); err != nil {
		t.Fatal(err)
	}
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	if e.Status().Cycles != 1 {
		t.Fatalf("el primer ciclo correcto debe contar como 1: %d", e.Status().Cycles)
	}
	if e.Status().LastError != "" {
		t.Fatal("un ciclo correcto debe vaciar LastError")
	}
}
