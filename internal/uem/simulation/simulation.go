package simulation

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// Name es el identificador del conector.
const Name = "simulation"

const accuracyM = 12.0

var madrid = geo.Point{Lat: 40.4168, Lng: -3.7038}

// Adapter simula una flota.
type Adapter struct {
	mu   sync.Mutex
	seed Seed
	tick int
	now  func() time.Time
}

// New crea el conector con una seed y un reloj.
func New(seed Seed, now func() time.Time) *Adapter {
	if now == nil {
		now = time.Now
	}
	return &Adapter{seed: seed, now: now}
}

// NewFromConfig construye el conector desde cfg["seed_path"] (opcional).
func NewFromConfig(cfg map[string]any, _ map[string]string) (uem.Adapter, error) {
	if path, ok := cfg["seed_path"].(string); ok && path != "" {
		seed, err := LoadSeed(path)
		if err != nil {
			return nil, err
		}
		return New(seed, time.Now), nil
	}
	return New(DefaultSeed(), time.Now), nil
}

// Tick devuelve cuántas veces se ha pedido la flota.
func (a *Adapter) Tick() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.tick
}

// Name implementa uem.Adapter.
func (a *Adapter) Name() string { return Name }

// Capabilities implementa uem.Adapter: la simulación lo soporta todo salvo postura.
func (a *Adapter) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true, Posture: false}
}

// Position calcula la posición en un tick: un segmento cada 3 ticks con
// interpolación lineal, para que una flota se mueva visiblemente entre ciclos.
func Position(waypoints []geo.Point, tick int) geo.Point {
	n := len(waypoints)
	if n == 0 {
		return madrid
	}
	seg := (tick / 3) % n
	a, b := waypoints[seg], waypoints[(seg+1)%n]
	frac := float64(tick%3) / 3.0
	return geo.Point{Lat: a.Lat + (b.Lat-a.Lat)*frac, Lng: a.Lng + (b.Lng-a.Lng)*frac}
}

// FetchDevices implementa uem.Adapter.
func (a *Adapter) FetchDevices(_ context.Context) ([]device.Device, error) {
	a.mu.Lock()
	tick := a.tick
	a.tick++
	seed := a.seed
	a.mu.Unlock()
	if len(seed.Devices) == 0 {
		return nil, errNoSeed
	}
	now := a.now().UTC()
	out := make([]device.Device, 0, len(seed.Devices))
	for _, sd := range seed.Devices {
		p := Position(sd.Waypoints, tick)
		acc := accuracyM
		status := sd.Status
		if status == "" {
			status = "active"
		}
		out = append(out, device.Device{
			ID: sd.ID, Name: sd.Name, Platform: sd.Platform, Status: status, Compliant: sd.Compliant,
			Provider: Name, ProviderRefs: map[string]string{Name: sd.ID},
			Location:     device.Location{Point: &p, AccuracyM: &acc, Source: Name, ObservedAt: now},
			Network:      device.Network{IP: sd.IP},
			Inventory:    sd.Inventory,
			FenceState:   device.Unknown,
			RouteState:   device.Unassigned,
			Risk:         device.Verdict{Reasons: []string{}, MatchedPolicies: []string{}},
			LastReportAt: now,
		})
	}
	return out, nil
}

// Execute implementa uem.Adapter: nunca contacta un dispositivo real.
func (a *Adapter) Execute(_ context.Context, dev device.Device, act action.Action, params map[string]any, dryRun bool) action.Result {
	sum := sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%d", dev.ID, act, a.Tick())))
	return action.Result{
		Adapter: Name, OK: true, DeviceID: dev.ID, DeviceName: dev.Name, Action: act, Params: params,
		DryRun: dryRun, Simulated: true, CommandID: "sim-" + hex.EncodeToString(sum[:6]),
		Note: "Acción simulada (ningún dispositivo real contactado)", At: a.now().UTC(),
	}
}

// TestConnection implementa uem.Adapter.
func (a *Adapter) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "simulated"}
}
