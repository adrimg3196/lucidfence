package engine

import (
	"context"
	"slices"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// reloj es el reloj que comparten el motor y el conector de estos casos: el
// test lo adelanta entre ciclos, como haría el paso del tiempo real.
type reloj struct{ at time.Time }

func (r *reloj) now() time.Time          { return r.at }
func (r *reloj) avanzar(d time.Duration) { r.at = r.at.Add(d) }

// viajero es un conector de un solo dispositivo cuya posición fija el test.
// Sella LastReportAt con el mismo reloj que el motor: esa marca es NUESTRA
// (cuándo recibimos el report), no el last_seen que informa el dispositivo.
type viajero struct {
	clock *reloj
	point geo.Point
}

func (v *viajero) Name() string { return "viajero" }

func (v *viajero) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true}
}

func (v *viajero) FetchDevices(context.Context) ([]device.Device, error) {
	p, acc, si := v.point, 12.0, true
	now := v.clock.now().UTC()
	return []device.Device{{
		ID: "dev-viajero", Name: "Portátil Viajero", Platform: "macos", Provider: v.Name(), Compliant: &si,
		Location:     device.Location{Point: &p, AccuracyM: &acc, Source: v.Name(), ObservedAt: now},
		Inventory:    device.Inventory{EncryptionEnabled: &si},
		FenceState:   device.Unknown,
		RouteState:   device.Unassigned,
		Risk:         device.Verdict{Reasons: []string{}, MatchedPolicies: []string{}},
		LastReportAt: now,
	}}, nil
}

func (v *viajero) Execute(_ context.Context, d device.Device, a action.Action, params map[string]any, dryRun bool) action.Result {
	return action.Result{Adapter: v.Name(), OK: true, DeviceID: d.ID, DeviceName: d.Name, Action: a,
		Params: params, DryRun: dryRun, Simulated: true, At: v.clock.now().UTC()}
}

func (v *viajero) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "simulated"}
}

// motorConReloj monta el motor sobre la fixture demo con un reloj movible y el
// conector viajero situado en p.
func motorConReloj(t *testing.T, p geo.Point) (*Engine, *store.OrgStore, *reloj, *viajero) {
	t.Helper()
	s, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	clock := &reloj{at: time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)}
	if err := SeedDemo(org, clock.now()); err != nil {
		t.Fatal(err)
	}
	ad := &viajero{clock: clock, point: p}
	e := New(org, []uem.Adapter{ad}, Options{Mode: "simulation", Interval: time.Minute, Now: clock.now})
	return e, org, clock, ad
}

// cicloViajero corre un ciclo y devuelve el dispositivo tal como quedó en
// devices.json.
func cicloViajero(t *testing.T, e *Engine, org *store.OrgStore) device.Device {
	t.Helper()
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	ds, err := org.Devices()
	if err != nil {
		t.Fatal(err)
	}
	return device.Index(ds)["dev-viajero"]
}

// TestIntegridadDetectaElSaltoImposibleEntreCiclos porta al ciclo completo
// legacy/tests/test_location_integrity.py::test_impossible_speed_detected_on_teleport:
// Madrid y Buenos Aires separados por diez minutos de reloj del motor.
func TestIntegridadDetectaElSaltoImposibleEntreCiclos(t *testing.T) {
	madrid := geo.Point{Lat: 40.4168, Lng: -3.7038}
	buenosAires := geo.Point{Lat: -34.6037, Lng: -58.3816}
	e, org, clock, ad := motorConReloj(t, madrid)

	if limpio := cicloViajero(t, e, org); limpio.LocationIntegrity.Suspicious {
		t.Fatalf("el primer ciclo no tiene contra qué comparar: %+v", limpio.LocationIntegrity)
	}
	clock.avanzar(10 * time.Minute)
	ad.point = buenosAires
	saltado := cicloViajero(t, e, org)

	li := saltado.LocationIntegrity
	if !li.Suspicious || !slices.Contains(li.Checks, integrity.CheckImpossibleSpeed) {
		t.Fatalf("más de 9.000 km en diez minutos son imposibles: %+v", li)
	}
	if li.SpeedKMH == nil || *li.SpeedKMH <= integrity.ImpossibleSpeedKMH {
		t.Fatalf("la velocidad medida debe viajar con la sospecha: %+v", li)
	}
	if li.DistanceKM == nil || *li.DistanceKM <= 9000 {
		t.Fatalf("la distancia medida debe viajar con la sospecha: %+v", li)
	}
	if !tieneRazon(saltado.Risk.Reasons, "velocidad imposible entre reportes") {
		t.Fatalf("el veredicto tiene que explicar el salto: %v", saltado.Risk.Reasons)
	}
	if saltado.Risk.Score == nil || *saltado.Risk.Score != 65 {
		t.Fatalf("35 de fuera de geocerca mas 30 de velocidad imposible: %+v", saltado.Risk)
	}
	if susp, ok := saltado.Signals["location_integrity"]["suspicious"].(bool); !ok || !susp {
		t.Fatalf("la señal de integridad debe persistir: %v", saltado.Signals["location_integrity"])
	}
}

// TestDwellAcumulaEnCiclosSucesivosYSeResetaAlSalir comprueba el reloj de
// permanencia de punta a punta: tres ciclos dentro de la misma geocerca
// acumulan y salir lo pone a cero.
func TestDwellAcumulaEnCiclosSucesivosYSeResetaAlSalir(t *testing.T) {
	e, org, clock, ad := motorConReloj(t, geo.Point{Lat: 40.4210, Lng: -3.7080})
	entrada := clock.now()

	primero := cicloViajero(t, e, org)
	if primero.InsideFence != "demo-hq" || primero.DwellSeconds != 0 {
		t.Fatalf("al entrar el reloj de permanencia arranca de cero: %+v", primero)
	}
	if primero.FenceStateSince == nil || !primero.FenceStateSince.Equal(entrada) {
		t.Fatalf("fence_state_since es el instante de entrada: %+v", primero.FenceStateSince)
	}
	clock.avanzar(90 * time.Second)
	if segundo := cicloViajero(t, e, org); segundo.DwellSeconds != 90 || !segundo.FenceStateSince.Equal(entrada) {
		t.Fatalf("el segundo ciclo acumula 90 s sin mover la entrada: %+v", segundo)
	}
	clock.avanzar(210 * time.Second)
	if tercero := cicloViajero(t, e, org); tercero.DwellSeconds != 300 || !tercero.FenceStateSince.Equal(entrada) {
		t.Fatalf("el tercer ciclo acumula 300 s: %+v", tercero)
	}
	clock.avanzar(300 * time.Second)
	ad.point = geo.Point{Lat: 40.5000, Lng: -3.6000}
	salida := cicloViajero(t, e, org)
	if salida.FenceState != device.Outside || salida.DwellSeconds != 0 {
		t.Fatalf("salir resetea la permanencia: %+v", salida)
	}
	if !salida.FenceStateSince.Equal(clock.now()) {
		t.Fatalf("y arranca el reloj del estado nuevo: %+v", salida.FenceStateSince)
	}
}
