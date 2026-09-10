package store

import (
	"encoding/json"
	"errors"
	"log/slog"
	"path/filepath"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

const schemaVersion = 1

// OrgStore es el almacén de una organización (tenant local). defaultEgress es
// la allowlist con la que se siembra settings.json la primera vez; después de
// esa siembra ya no se consulta. logger es el canal por el que se avisa de lo
// que el almacén decide tragarse (store.WithLogger); nunca es nil.
type OrgStore struct {
	id            string
	dir           string
	mu            sync.RWMutex
	defaultEgress settings.Egress
	logger        *slog.Logger
}

// ID devuelve el id de la organización.
func (o *OrgStore) ID() string { return o.id }

// Dir devuelve el directorio de la organización.
func (o *OrgStore) Dir() string { return o.dir }

// Path devuelve la ruta de un fichero dentro de la organización.
func (o *OrgStore) Path(name string) string { return filepath.Join(o.dir, name) }

type collection[T any] struct {
	SchemaVersion int `json:"schema_version"`
	Items         []T `json:"items"`
}

func readCollection[T any](o *OrgStore, name string) ([]T, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	var c collection[T]
	err := ReadJSON(o.Path(name), &c)
	if errors.Is(err, ErrNotFound) {
		return []T{}, nil
	}
	if err != nil {
		return nil, err
	}
	if c.Items == nil {
		c.Items = []T{}
	}
	return c.Items, nil
}

func writeCollection[T any](o *OrgStore, name string, items []T) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	if items == nil {
		items = []T{}
	}
	return WriteJSON(o.Path(name), collection[T]{SchemaVersion: schemaVersion, Items: items})
}

// Fences lee las geocercas.
func (o *OrgStore) Fences() ([]fence.Fence, error) {
	return readCollection[fence.Fence](o, "fences.json")
}

// SaveFences escribe las geocercas.
func (o *OrgStore) SaveFences(fs []fence.Fence) error { return writeCollection(o, "fences.json", fs) }

// Routes lee las rutas.
func (o *OrgStore) Routes() ([]route.Route, error) {
	return readCollection[route.Route](o, "routes.json")
}

// SaveRoutes escribe las rutas.
func (o *OrgStore) SaveRoutes(rs []route.Route) error { return writeCollection(o, "routes.json", rs) }

// POIs lee los puntos de interés.
func (o *OrgStore) POIs() ([]poi.POI, error) { return readCollection[poi.POI](o, "pois.json") }

// SavePOIs escribe los puntos de interés.
func (o *OrgStore) SavePOIs(ps []poi.POI) error { return writeCollection(o, "pois.json", ps) }

// Devices lee el último estado de los dispositivos.
func (o *OrgStore) Devices() ([]device.Device, error) {
	return readCollection[device.Device](o, "devices.json")
}

// SaveDevices escribe el estado de los dispositivos.
func (o *OrgStore) SaveDevices(ds []device.Device) error {
	return writeCollection(o, "devices.json", ds)
}

func appendLine(o *OrgStore, name string, v any) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	return AppendJSONL(o.Path(name), v)
}

func readLines[T any](o *OrgStore, name string, limit int) ([]T, error) {
	o.mu.RLock()
	raws, err := ReadJSONL(o.Path(name), limit)
	o.mu.RUnlock()
	if err != nil {
		return nil, err
	}
	return decodeLines[T](o, name, raws), nil
}

// decodeLines decodifica lo que se puede y salta lo que no. Un JSONL de solo
// append se corrompe por el final (un kill a mitad de un AppendJSONL, un disco
// lleno que devuelve escritura corta) y esa media línea no puede dejar
// /api/v1/events, /api/v1/actions y el what-if de políticas en 500 para
// siempre, sin más salida que editar el fichero a mano en la máquina del
// tenant. Es el criterio que trailEntries ya trae de load_trail_points de 1.x;
// aquí se aplica también al resto del histórico, y lo descartado se avisa por
// el logger del almacén en vez de tragárselo en silencio.
func decodeLines[T any](o *OrgStore, name string, raws []json.RawMessage) []T {
	out := make([]T, 0, len(raws))
	descartadas := 0
	for _, r := range raws {
		var v T
		if err := json.Unmarshal(r, &v); err != nil {
			descartadas++
			continue
		}
		out = append(out, v)
	}
	if descartadas > 0 {
		o.logger.Warn("líneas ilegibles descartadas: el histórico se sirve sin ellas",
			"file", name, "org", o.id, "lines", descartadas)
	}
	return out
}

// AppendEvent registra una transición.
func (o *OrgStore) AppendEvent(t transition.Transition) error {
	return appendLine(o, "events.jsonl", t)
}

// RecentEvents devuelve las últimas transiciones.
func (o *OrgStore) RecentEvents(limit int) ([]transition.Transition, error) {
	return readLines[transition.Transition](o, "events.jsonl", limit)
}

// AppendAction registra el resultado de una acción.
func (o *OrgStore) AppendAction(r action.Result) error { return appendLine(o, "actions.jsonl", r) }

// RecentActions devuelve los últimos resultados de acciones.
func (o *OrgStore) RecentActions(limit int) ([]action.Result, error) {
	return readLines[action.Result](o, "actions.jsonl", limit)
}

// trailLine es la línea de trail.jsonl tal cual se lee. Point es puntero a
// propósito: así una línea sin coordenadas se distingue de una en el (0,0)
// del golfo de Guinea, que es una posición válida.
type trailLine struct {
	DeviceID string     `json:"device_id"`
	At       time.Time  `json:"at"`
	Point    *geo.Point `json:"point"`
}

// TrailEntry es un punto del histórico global: la posición de un dispositivo
// en un instante. Es lo que consume el simulador what-if del motor.
type TrailEntry struct {
	DeviceID string    `json:"device_id"`
	At       time.Time `json:"at"`
	Point    geo.Point `json:"point"`
}

// MaxTrailPoints es el techo duro de puntos que devuelve TrailAll. Protege al
// servidor local: un trail de meses no puede convertirse en una simulación que
// se coma la memoria de la máquina del operador.
const MaxTrailPoints = 20_000

// AppendTrail registra una posición.
func (o *OrgStore) AppendTrail(deviceID string, p geo.Point, at time.Time) error {
	return appendLine(o, "trail.jsonl", TrailEntry{DeviceID: deviceID, At: at, Point: p})
}

// trailEntries lee trail.jsonl entero y descarta lo que no se puede usar: una
// línea corrupta, sin dispositivo, sin instante o con coordenadas imposibles se
// salta en vez de tumbar la lectura (porte de load_trail_points de 1.x). El
// fichero es append-only y el motor sella cada punto con su propio reloj, así
// que el orden del fichero es el orden cronológico.
func (o *OrgStore) trailEntries() ([]TrailEntry, error) {
	o.mu.RLock()
	raws, err := ReadJSONL(o.Path("trail.jsonl"), 0)
	o.mu.RUnlock()
	if err != nil {
		return nil, err
	}
	out := make([]TrailEntry, 0, len(raws))
	for _, raw := range raws {
		var l trailLine
		if err := json.Unmarshal(raw, &l); err != nil {
			continue
		}
		if l.DeviceID == "" || l.At.IsZero() || l.Point == nil || l.Point.Valid() != nil {
			continue
		}
		out = append(out, TrailEntry{DeviceID: l.DeviceID, At: l.At, Point: *l.Point})
	}
	return out, nil
}

// Trail devuelve las últimas posiciones de un dispositivo.
func (o *OrgStore) Trail(deviceID string, limit int) ([]device.TrailPoint, error) {
	all, err := o.trailEntries()
	if err != nil {
		return nil, err
	}
	out := []device.TrailPoint{}
	for _, e := range all {
		if e.DeviceID == deviceID {
			out = append(out, device.TrailPoint{At: e.At, Point: e.Point})
		}
	}
	if limit > 0 && len(out) > limit {
		out = out[len(out)-limit:]
	}
	return out, nil
}

// TrailAll devuelve los últimos limit puntos del histórico de toda la flota, en
// orden cronológico. limit <= 0 o por encima del techo valen MaxTrailPoints.
func (o *OrgStore) TrailAll(limit int) ([]TrailEntry, error) {
	if limit <= 0 || limit > MaxTrailPoints {
		limit = MaxTrailPoints
	}
	all, err := o.trailEntries()
	if err != nil {
		return nil, err
	}
	if len(all) > limit {
		all = all[len(all)-limit:]
	}
	return all, nil
}

// AppendStats registra las estadísticas de un ciclo.
func (o *OrgStore) AppendStats(v any) error { return appendLine(o, "stats.jsonl", v) }

// RecentStats devuelve las últimas estadísticas sin decodificar.
func (o *OrgStore) RecentStats(limit int) ([]json.RawMessage, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return ReadJSONL(o.Path("stats.jsonl"), limit)
}

// AppendDelivery registra el intento de entrega de una notificación. Acepta
// any para que store no importe notify (la dirección permitida es la
// contraria): así *OrgStore satisface notify.Sink por firma.
func (o *OrgStore) AppendDelivery(v any) error { return appendLine(o, "deliveries.jsonl", v) }

// RecentDeliveries devuelve las últimas entregas sin decodificar.
func (o *OrgStore) RecentDeliveries(limit int) ([]json.RawMessage, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return ReadJSONL(o.Path("deliveries.jsonl"), limit)
}
