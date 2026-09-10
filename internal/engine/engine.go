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
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/notify"
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
	// Notifier entrega los eventos del ciclo. serve lo construye con los
	// ajustes de la organización, el resolutor de secretos y el OrgStore
	// como Sink; si es nil, New construye uno equivalente (newNotifier).
	Notifier *notify.Notifier
	// Secrets resuelve webhook_secret y ntfy_token cuando New tiene que
	// construir el Notifier. El motor nunca lee su valor: lo consulta el
	// Notifier en el momento del envío.
	Secrets notify.Secrets
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
	RiskEvaluated     int                       `json:"risk_evaluated"`
	RiskFailed        int                       `json:"risk_failed"`
	BySeverity        map[string]int            `json:"by_severity"`
	Transitions       int                       `json:"transitions"`
	ActionsPlanned    int                       `json:"actions_planned"`
	ActionsExecuted   int                       `json:"actions_executed"`
	ActionsSuppressed int                       `json:"actions_suppressed"`
	ActionsBlocked    int                       `json:"actions_blocked"`
	IncidentsOpened   int                       `json:"incidents_opened"`
	IncidentsClosed   int                       `json:"incidents_closed"`
	AlertsFired       int                       `json:"alerts_fired"`
	HandoffsPending   int                       `json:"handoffs_pending"`
	Deliveries        int                       `json:"deliveries"`
	DeliveriesFailed  int                       `json:"deliveries_failed"`
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
	Incidents       int                       `json:"incidents_open"`
	Notify          notify.Status             `json:"notify"`
}

// Engine es el motor de una organización.
type Engine struct {
	org      *store.OrgStore
	adapters map[string]uem.Adapter
	order    []string
	opts     Options
	guard    Guardrails
	riskCfg  settings.Risk

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
	// dwelled recuerda, por dispositivo y geocerca, el instante de inicio de
	// la estancia cuyo on_enter por permanencia ya se emitió. Salir de la
	// geocerca borra la entrada (ver planDwell). Se rehidrata del store al
	// arrancar y se guarda al final del ciclo en que cambió: "un solo disparo
	// por estancia" también tiene que valer después de un reinicio.
	dwelled    map[string]string
	dwellDirty bool
	// handoffs es la bandeja del ciclo en curso (la que evaluatePlaybooks
	// consulta para no duplicar) y opened las peticiones que este ciclo ha
	// abierto: de ahí salen la persistencia y los avisos handoff.pending.
	handoffs []playbook.Handoff
	opened   []playbook.Handoff
	// manualMu serializa todo lo que toca handoffs.json fuera del recorrido
	// de la flota: las dos decisiones, la acción manual y la escritura de la
	// bandeja al final del ciclo. Así una aprobación concurrente no se pierde
	// y dos wipes manuales simultáneos no se cuelan los dos por el cooldown.
	manualMu sync.Mutex
	fired    map[string]bool
	// alerted recuerda, por regla y dispositivo, cuándo salió el último
	// alert.fired. Una condición que sigue encendida no vuelve a avisar hasta
	// que pase alertCooldown; una que se apaga pierde su marca y su episodio
	// siguiente avisa en el acto (ver evaluateAlerts). Es memoria del proceso,
	// como en 1.x: lo que se repite tras un reinicio es un aviso, no una orden
	// a un dispositivo (M2-R41).
	alerted map[string]time.Time
	// notifier lo construye New y no se sustituye nunca: applySettings lo
	// recarga con Reload, que es seguro para uso concurrente.
	notifier *notify.Notifier
	// incidents es el número de incidentes sin cerrar tras el último ciclo;
	// lo publica Status() y lo escribe syncIncidents bajo stateMu.
	incidents int
	wg        sync.WaitGroup

	// evalHook, si no es nil, se llama al principio de evaluateDevice. Solo
	// lo fijan los tests, para provocar de forma determinista un pánico por
	// dispositivo y comprobar que el ciclo no se cae (no hay ruta natural de
	// producción a un pánico ahí).
	evalHook func(*device.Device)
}

// New crea el motor. El enforcement y el contexto de riesgo nacen en los
// ajustes de fábrica (observe, jornada 20-7) y cada ciclo los recarga del
// store con applySettings; la memoria de cooldown es el propio OrgStore.
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
		riskCfg:   settings.Default().Risk,
		providers: map[string]ProviderHealth{}, violations: map[string]int{},
		dwelled: map[string]string{}, fired: map[string]bool{},
		alerted: map[string]time.Time{}}
	if org != nil {
		e.guard.Cooldowns = org
		e.dwelled = org.DwellMarks()
	}
	e.notifier = newNotifier(org, opts)
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

// applySettings refresca, una vez por ciclo, lo que el motor consulta fuera
// del ciclo: el enforcement de los guardarraíles y el contexto de riesgo. Los
// ajustes vienen de la lectura que hizo loadInput, así que settings.json se
// lee una sola vez por ciclo y un cambio hecho por la API surte efecto en el
// ciclo siguiente sin reiniciar el proceso. El modo se sanea antes de
// guardarlo (M2-R32): lo que el motor publica no puede decir "Enforce"
// mientras gatea como observe.
func (e *Engine) applySettings(set settings.Settings) {
	enf, saneado := normalizedEnforcement(set.Enforcement)
	if saneado {
		e.opts.Logger.Warn("enforcement.mode desconocido: el motor lo trata como observe",
			"mode", set.Enforcement.Mode)
	}
	e.stateMu.Lock()
	e.guard.Enforcement = enf
	e.riskCfg = set.Risk
	e.stateMu.Unlock()
	// Reload cambia configuración, no contadores: delivered/failed siguen
	// siendo el histórico del proceso que publica health (T11).
	if n := e.Notifier(); n != nil {
		n.Reload(set)
	}
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
		Running: e.running, Cycles: e.cycles, LastCycle: e.last, LastError: e.lastErr, NextCycleAt: e.nextAt,
		Providers: e.providers, Incidents: e.incidents, Notify: notifyStatusOf(e.notifier)}
}

// setOpenIncidents guarda el número de incidentes sin cerrar del último
// ciclo. Lo llama syncIncidents, que corre bajo el lock del ciclo, no bajo
// stateMu.
func (e *Engine) setOpenIncidents(n int) {
	e.stateMu.Lock()
	e.incidents = n
	e.stateMu.Unlock()
}
