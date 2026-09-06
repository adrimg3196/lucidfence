package store

import (
	"encoding/json"
	"errors"
	"path/filepath"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

const schemaVersion = 1

// OrgStore es el almacén de una organización (tenant local).
type OrgStore struct {
	id  string
	dir string
	mu  sync.RWMutex
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
	out := make([]T, 0, len(raws))
	for _, r := range raws {
		var v T
		if err := json.Unmarshal(r, &v); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, nil
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

type trailLine struct {
	DeviceID string    `json:"device_id"`
	At       time.Time `json:"at"`
	Point    geo.Point `json:"point"`
}

// AppendTrail registra una posición.
func (o *OrgStore) AppendTrail(deviceID string, p geo.Point, at time.Time) error {
	return appendLine(o, "trail.jsonl", trailLine{DeviceID: deviceID, At: at, Point: p})
}

// Trail devuelve las últimas posiciones de un dispositivo.
func (o *OrgStore) Trail(deviceID string, limit int) ([]device.TrailPoint, error) {
	all, err := readLines[trailLine](o, "trail.jsonl", 0)
	if err != nil {
		return nil, err
	}
	var out []device.TrailPoint
	for _, l := range all {
		if l.DeviceID == deviceID {
			out = append(out, device.TrailPoint{At: l.At, Point: l.Point})
		}
	}
	if limit > 0 && len(out) > limit {
		out = out[len(out)-limit:]
	}
	if out == nil {
		out = []device.TrailPoint{}
	}
	return out, nil
}

// AppendStats registra las estadísticas de un ciclo.
func (o *OrgStore) AppendStats(v any) error { return appendLine(o, "stats.jsonl", v) }

// RecentStats devuelve las últimas estadísticas sin decodificar.
func (o *OrgStore) RecentStats(limit int) ([]json.RawMessage, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return ReadJSONL(o.Path("stats.jsonl"), limit)
}
