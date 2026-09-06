// Package engine ejecuta el ciclo de evaluación (spec §5.4): pide la flota a
// cada conector, evalúa geocercas y rutas, detecta transiciones, decide
// acciones bajo guardarraíles y persiste. Un solo ciclo a la vez.
package engine

import (
	"context"
	"errors"
	"log/slog"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// ErrCycleInProgress se devuelve si RunOnce se solapa con otro ciclo.
var ErrCycleInProgress = errors.New("ciclo en curso")

// Options configura el motor.
type Options struct {
	Mode     string
	Interval time.Duration
	Now      func() time.Time
	Logger   *slog.Logger
}

// ProviderHealth es la salud de un conector.
type ProviderHealth struct {
	OK        bool       `json:"ok"`
	Error     string     `json:"error,omitempty"`
	Devices   int        `json:"devices"`
	LatencyMS int64      `json:"latency_ms"`
	LastOK    *time.Time `json:"last_ok,omitempty"`
}

// CycleStats resume un ciclo.
type CycleStats struct {
	At                time.Time                 `json:"at"`
	DurationMS        int64                     `json:"duration_ms"`
	Mode              string                    `json:"mode"`
	DevicesTotal      int                       `json:"devices_total"`
	Inside            int                       `json:"inside"`
	Outside           int                       `json:"outside"`
	Unknown           int                       `json:"unknown"`
	Transitions       int                       `json:"transitions"`
	ActionsPlanned    int                       `json:"actions_planned"`
	ActionsExecuted   int                       `json:"actions_executed"`
	EvaluationErrors  int                       `json:"evaluation_errors"`
	PersistenceErrors int                       `json:"persistence_errors"`
	Providers         map[string]ProviderHealth `json:"providers"`
}

// Status es lo que expone /api/v1/engine/status.
type Status struct {
	Mode            string                    `json:"mode"`
	Enforcement     string                    `json:"enforcement"`
	IntervalSeconds int                       `json:"interval_seconds"`
	Running         bool                      `json:"running"`
	Cycles          int                       `json:"cycles"`
	LastCycle       *CycleStats               `json:"last_cycle,omitempty"`
	LastError       string                    `json:"last_error,omitempty"`
	NextCycleAt     *time.Time                `json:"next_cycle_at,omitempty"`
	Providers       map[string]ProviderHealth `json:"providers"`
}

// Engine es el motor de una organización.
type Engine struct {
	org      *store.OrgStore
	adapters map[string]uem.Adapter
	order    []string
	opts     Options
	guard    Guardrails

	cycleMu    sync.Mutex
	stateMu    sync.RWMutex
	running    bool
	cancel     context.CancelFunc
	cycles     int
	last       *CycleStats
	lastErr    string
	nextAt     *time.Time
	providers  map[string]ProviderHealth
	violations map[string]int
	fired      map[string]bool
	wg         sync.WaitGroup

	// evalHook, si no es nil, se llama al principio de evaluateDevice. Solo
	// lo fijan los tests, para provocar de forma determinista un pánico por
	// dispositivo y comprobar que el ciclo no se cae (no hay ruta natural de
	// producción a un pánico ahí).
	evalHook func(*device.Device)
}

// New crea el motor. El enforcement nace en observe y M1 no ofrece forma de cambiarlo.
func New(org *store.OrgStore, adapters []uem.Adapter, opts Options) *Engine {
	if opts.Now == nil {
		opts.Now = time.Now
	}
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	if opts.Interval <= 0 {
		opts.Interval = 15 * time.Minute
	}
	e := &Engine{org: org, adapters: map[string]uem.Adapter{}, opts: opts, guard: Guardrails{Enforcement: EnforcementObserve},
		providers: map[string]ProviderHealth{}, violations: map[string]int{}, fired: map[string]bool{}}
	for _, a := range adapters {
		name := a.Name()
		if _, dup := e.adapters[name]; dup {
			opts.Logger.Warn("conector duplicado", "name", name)
			continue
		}
		e.adapters[name] = a
		e.order = append(e.order, name)
	}
	return e
}

// Guardrails expone la configuración de enforcement vigente.
func (e *Engine) Guardrails() Guardrails { return e.guard }

// RunOnce ejecuta un ciclo si no hay otro en curso. Si runCycle falla (p. ej.
// el store no puede leer o guardar), el ciclo no cuenta como completado: no
// se incrementa Cycles ni se sustituye LastCycle, y el error queda expuesto
// en Status().LastError hasta que un ciclo correcto lo vacíe.
func (e *Engine) RunOnce(ctx context.Context) (CycleStats, error) {
	if !e.cycleMu.TryLock() {
		return CycleStats{}, ErrCycleInProgress
	}
	defer e.cycleMu.Unlock()
	e.fired = map[string]bool{}
	st, err := e.runCycle(ctx)
	e.stateMu.Lock()
	e.providers = st.Providers
	if err != nil {
		e.lastErr = err.Error()
	} else {
		e.cycles++
		e.last = &st
		e.lastErr = ""
	}
	e.stateMu.Unlock()
	return st, err
}

// Start lanza el bucle periódico: un ciclo inmediato y luego cada Interval.
// Reentrante: si ya hay un bucle en marcha, la llamada no hace nada. Deriva
// su propio contexto cancelable para que Stop no dependa de que el llamante
// cancele el contexto externo.
func (e *Engine) Start(ctx context.Context) {
	e.stateMu.Lock()
	if e.running {
		e.stateMu.Unlock()
		return
	}
	ctx, cancel := context.WithCancel(ctx)
	e.running, e.cancel = true, cancel
	e.stateMu.Unlock()
	e.wg.Add(1)
	go func() {
		defer e.wg.Done()
		defer func() {
			e.stateMu.Lock()
			e.running, e.nextAt, e.cancel = false, nil, nil
			e.stateMu.Unlock()
		}()
		t := time.NewTicker(e.opts.Interval)
		defer t.Stop()
		for {
			if _, err := e.RunOnce(ctx); err != nil && !errors.Is(err, ErrCycleInProgress) {
				e.opts.Logger.Error("ciclo", "error", err)
			}
			next := e.opts.Now().Add(e.opts.Interval)
			e.stateMu.Lock()
			e.nextAt = &next
			e.stateMu.Unlock()
			select {
			case <-ctx.Done():
				return
			case <-t.C:
			}
		}
	}()
}

// Stop cancela el bucle lanzado por Start (con su propio contexto derivado,
// sin depender de que el llamante cancele el externo) y espera a que
// termine. Es idempotente: llamarlo sin un bucle en marcha, o varias veces,
// no bloquea ni hace panic.
func (e *Engine) Stop() {
	e.stateMu.RLock()
	cancel := e.cancel
	e.stateMu.RUnlock()
	if cancel != nil {
		cancel()
	}
	e.wg.Wait()
}

// Status devuelve el estado actual.
func (e *Engine) Status() Status {
	e.stateMu.RLock()
	defer e.stateMu.RUnlock()
	return Status{Mode: e.opts.Mode, Enforcement: e.guard.Enforcement, IntervalSeconds: int(e.opts.Interval / time.Second),
		Running: e.running, Cycles: e.cycles, LastCycle: e.last, LastError: e.lastErr, NextCycleAt: e.nextAt, Providers: e.providers}
}
