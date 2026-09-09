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
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
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
	ActionsSuppressed int                       `json:"actions_suppressed"`
	ActionsBlocked    int                       `json:"actions_blocked"`
	EvaluationErrors  int                       `json:"evaluation_errors"`
	PersistenceErrors int                       `json:"persistence_errors"`
	Providers         map[string]ProviderHealth `json:"providers"`
}

// Status es lo que expone /api/v1/engine/status.
type Status struct {
	Mode            string                    `json:"mode"`
	Enforcement     settings.Enforcement      `json:"enforcement"`
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

// New crea el motor. El enforcement nace en los ajustes de fábrica (observe)
// y cada ciclo lo recarga del store con refreshGuardrails; la memoria de
// cooldown es el propio OrgStore.
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
	e := &Engine{org: org, adapters: map[string]uem.Adapter{}, opts: opts,
		guard:     Guardrails{Enforcement: settings.Default().Enforcement, Now: opts.Now},
		providers: map[string]ProviderHealth{}, violations: map[string]int{}, fired: map[string]bool{}}
	if org != nil {
		e.guard.Cooldowns = org
	}
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

// Guardrails devuelve una copia de los guardarraíles vigentes. Toma el lock
// porque el ciclo los sustituye mientras Status() los publica.
func (e *Engine) Guardrails() Guardrails {
	e.stateMu.RLock()
	defer e.stateMu.RUnlock()
	return e.guard
}

// refreshGuardrails recarga el enforcement de settings.json al principio de
// cada ciclo, para que un cambio hecho por la API surta efecto sin reiniciar.
// Si los ajustes no se pueden leer, o traen un modo que no existe, el motor
// cae a observe: la única postura segura ante un fichero que no se entiende
// es no mandar nada en vivo, y que el estado lo diga.
func (e *Engine) refreshGuardrails() {
	if e.org == nil {
		return
	}
	g := e.Guardrails()
	set, err := e.org.Settings()
	if err != nil {
		e.opts.Logger.Warn("ajustes ilegibles: el motor sigue en observe", "error", err)
		set = settings.Default()
	}
	enf, saneado := normalizedEnforcement(set.Enforcement)
	if saneado {
		e.opts.Logger.Warn("enforcement.mode desconocido: el motor lo trata como observe",
			"mode", set.Enforcement.Mode)
	}
	g.Enforcement = enf
	e.stateMu.Lock()
	e.guard = g
	e.stateMu.Unlock()
}

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
