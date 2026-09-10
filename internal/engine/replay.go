// Simulador what-if de políticas: el "terraform plan" del geofencing (spec
// §4.1). Reconstruye cada punto del histórico de trail, lo vuelve a evaluar con
// las señales y el veredicto de riesgo del motor y comprueba si la política
// CANDIDATA habría disparado, para que el operador vea qué habría hecho una
// regla destructiva antes de activarla.
//
// Es de solo lectura: no llama al adapter, no escribe actions.jsonl ni
// cooldowns.json y no toca un solo campo mutable del motor (por eso lee los
// ajustes del disco en vez de e.riskCfg, y por eso puede correr mientras hay un
// ciclo en marcha).
//
// Límite honesto del modelo: la posición y el instante salen del histórico,
// pero las señales no espaciales (conformidad, postura, inventario) salen del
// estado ACTUAL del dispositivo. Para una política puramente espacial la
// simulación es exacta; para el resto es una aproximación, y el resultado lo
// declara en Approximation y lo explica en Notes.
package engine

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/store"
)

const (
	// ReplayMaxPoints es el techo duro de puntos por simulación.
	ReplayMaxPoints = 20_000
	// ReplayMaxSamples es el número de disparos de ejemplo con detalle.
	ReplayMaxSamples = 50
	// ReplayDefaultLimit es la ventana por defecto si la petición no la fija.
	ReplayDefaultLimit = 5_000
)

// ReplayRequest es la petición de simulación. UseCurrentFences recalcula el
// estado de geocerca con las geocercas de hoy (what-if de política y de
// geocercas a la vez) en vez de leerlo del histórico de transiciones.
type ReplayRequest struct {
	Policy           policy.Policy `json:"policy"`
	Limit            int           `json:"limit"`
	UseCurrentFences bool          `json:"use_current_fences"`
}

// ReplaySample es un disparo de ejemplo con su explicación: sin razones, un
// disparo es un número que nadie puede auditar.
type ReplaySample struct {
	At         time.Time `json:"at"`
	DeviceID   string    `json:"device_id"`
	DeviceName string    `json:"device_name"`
	FenceState string    `json:"fence_state"`
	Score      *float64  `json:"score"`
	Severity   string    `json:"severity"`
	Reasons    []string  `json:"reasons"`
}

// ReplayResult es el plan: qué habría hecho la política y con qué límites se
// calculó. Nunca se ejecuta nada.
type ReplayResult struct {
	PolicyID         string         `json:"policy_id"`
	PointsEvaluated  int            `json:"points_evaluated"`
	DevicesEvaluated int            `json:"devices_evaluated"`
	Firings          int            `json:"firings"`
	ByDevice         map[string]int `json:"by_device"`
	ByAction         map[string]int `json:"by_action"`
	Approximation    bool           `json:"approximation"`
	Notes            []string       `json:"notes"`
	From             *time.Time     `json:"from,omitempty"`
	To               *time.Time     `json:"to,omitempty"`
	Samples          []ReplaySample `json:"samples"`
}

// replayer es el estado de una simulación. Vive en la pila de Replay: no se
// comparte entre llamadas ni con el ciclo.
type replayer struct {
	req     ReplayRequest
	riskCfg settings.Risk
	index   map[string]device.Device
	fences  []fence.Fence
	history *history
	stance  map[string]stance
	seen    map[string]bool
	unknown int
	res     ReplayResult
}

// replayLimit acota la ventana pedida: sin límite manda el de por defecto y
// nadie puede pedir más que el techo duro.
func replayLimit(limit int) int {
	if limit <= 0 {
		return ReplayDefaultLimit
	}
	if limit > ReplayMaxPoints {
		return ReplayMaxPoints
	}
	return limit
}

// Replay simula la política candidata contra el histórico. Valida antes de leer
// nada: una política inválida devuelve error y un resultado vacío, nunca medio
// resultado que alguien pueda leer como "no dispararía".
func (e *Engine) Replay(req ReplayRequest) (ReplayResult, error) {
	if err := req.Policy.Validate(); err != nil {
		return ReplayResult{}, err
	}
	// La candidata se simula encendida aunque llegue apagada: el what-if se
	// hace sobre la política que se está escribiendo, que por definición
	// todavía no está activa, y policy.Matches trata una política apagada
	// como que no casa. req es una copia por valor: la del llamante no se
	// toca y no se enciende nada en disco.
	req.Policy.Enabled = true
	limit := replayLimit(req.Limit)
	r, err := e.newReplayer(req)
	if err != nil {
		return ReplayResult{}, err
	}
	points, err := e.org.TrailAll(limit)
	if err != nil {
		return ReplayResult{}, err
	}
	for _, p := range points {
		r.evaluate(p)
	}
	return r.finish(limit), nil
}

// newReplayer lee del disco todo lo que la simulación necesita. Los ajustes
// vienen de settings.json y no del motor, para que un replay lanzado antes del
// primer ciclo use la misma jornada laboral que usará el ciclo.
func (e *Engine) newReplayer(req ReplayRequest) (*replayer, error) {
	set, err := e.org.Settings()
	if err != nil {
		return nil, err
	}
	ds, err := e.org.Devices()
	if err != nil {
		return nil, err
	}
	fs, err := e.org.Fences()
	if err != nil {
		return nil, err
	}
	evs, err := e.org.RecentEvents(0)
	if err != nil {
		return nil, err
	}
	return &replayer{
		req: req, riskCfg: set.Risk, index: device.Index(ds), fences: fs,
		history: newHistory(evs), stance: map[string]stance{}, seen: map[string]bool{},
		res: ReplayResult{
			PolicyID: req.Policy.ID,
			ByDevice: map[string]int{}, ByAction: map[string]int{},
			Samples: []ReplaySample{},
		},
	}, nil
}

// evaluate reconstruye el dispositivo en ese punto del histórico y comprueba si
// la política candidata habría disparado. Se usa Matches y no MatchAll: el
// what-if es sobre una candidata que todavía no está activa.
func (r *replayer) evaluate(entry store.TrailEntry) {
	d, conocido := r.index[entry.DeviceID]
	if !conocido {
		d = device.Device{ID: entry.DeviceID}
		r.unknown++
	}
	r.seen[entry.DeviceID] = true
	punto := entry.Point
	d.Location.Point = &punto
	d.Location.ObservedAt = entry.At
	d.LastReportAt = entry.At
	state, fenceID, since := r.placeAt(entry)
	d.FenceState, d.InsideFence = state, fenceID
	d.FenceStateSince = &since
	d.DwellSeconds = dwellSeconds(since, entry.At)
	sig := risk.Compute(d, riskContextFrom(r.riskCfg, entry.At))
	verdict := risk.Evaluate(d, sig, entry.At)
	at := entry.At
	if r.res.From == nil {
		r.res.From = &at
	}
	r.res.To = &at
	r.res.PointsEvaluated++
	if r.req.Policy.Matches(policy.NewSubject(d, verdict, sig)) {
		r.fire(entry, d, verdict)
	}
}

// fire contabiliza un disparo. Los totales cuentan todos; las muestras se
// cortan en ReplayMaxSamples para que la respuesta quepa en una pantalla.
func (r *replayer) fire(entry store.TrailEntry, d device.Device, v device.Verdict) {
	r.res.Firings++
	r.res.ByDevice[entry.DeviceID]++
	for _, a := range r.req.Policy.Actions {
		r.res.ByAction[string(a.Action)]++
	}
	if len(r.res.Samples) >= ReplayMaxSamples {
		return
	}
	r.res.Samples = append(r.res.Samples, ReplaySample{
		At: entry.At, DeviceID: d.ID, DeviceName: d.Name,
		FenceState: string(d.FenceState), Score: v.Score, Severity: v.Severity, Reasons: v.Reasons,
	})
}

// finish cierra el resultado: los totales que no se pueden llevar punto a punto
// y las notas que declaran los límites de la simulación.
func (r *replayer) finish(limit int) ReplayResult {
	fields := nonSpatial(r.req.Policy)
	r.res.DevicesEvaluated = len(r.seen)
	r.res.Approximation = len(fields) > 0
	r.res.Notes = r.notes(fields, limit)
	return r.res
}
