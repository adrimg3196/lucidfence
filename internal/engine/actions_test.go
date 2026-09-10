package engine

import (
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

func testFences() []fence.Fence {
	return []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
		Actions: []fence.Action{
			{Action: action.Message, When: fence.OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido"}},
			{Action: action.Notify, When: fence.OnExit, Enabled: true},
			{Action: action.Locate, When: fence.OnUnknown, Enabled: true},
			{Action: action.Lock, When: fence.OnViolation, Enabled: true},
			{Action: action.Wipe, When: fence.OnEnter, Enabled: false},
		}}}
}

func TestPlanTransition(t *testing.T) {
	fs := testFences()
	cur := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	enter := &transition.Transition{From: "none:outside", To: "demo-hq:inside"}
	got := PlanTransition(cur, enter, fs)
	if len(got) != 1 || got[0].Action != action.Message || got[0].FenceID != "demo-hq" || got[0].Trigger != "on_enter" {
		t.Fatalf("on_enter: %+v", got)
	}
	if got[0].Params["text"] != "Bienvenido" {
		t.Fatalf("los parámetros de la geocerca viajan en Planned: %+v", got[0].Params)
	}
	cur = device.Device{ID: "d", FenceState: device.Outside}
	exit := &transition.Transition{From: "demo-hq:inside", To: "none:outside"}
	got = PlanTransition(cur, exit, fs)
	if len(got) != 1 || got[0].Action != action.Notify || got[0].Trigger != "on_exit" {
		t.Fatalf("on_exit: %+v", got)
	}
	cur = device.Device{ID: "d", FenceState: device.Unknown, LastInsideFence: "demo-hq"}
	unk := &transition.Transition{From: "demo-hq:inside", To: "none:unknown"}
	got = PlanTransition(cur, unk, fs)
	if len(got) != 2 {
		t.Fatalf("a unknown: on_exit de la geocerca previa + on_unknown: %+v", got)
	}
	if PlanTransition(cur, nil, fs) != nil {
		t.Fatal("sin transición no hay plan")
	}
}

// rutaConAcciones es la ruta de los casos de corredor: un tramo del centro con
// las acciones que se le pasen.
func rutaConAcciones(acts ...fence.Action) []route.Route {
	return []route.Route{{ID: "route-centro", Name: "Ruta Comercial Centro", CorridorM: 300,
		DeviceIDs: []string{"dev-a"},
		Waypoints: []geo.Point{{Lat: 40.4300, Lng: -3.6900}, {Lat: 40.4250, Lng: -3.7000}},
		Actions:   acts}}
}

// enCorredor y fueraDelCorredor son el mismo dispositivo antes y después de
// salirse de su ruta, tal como los deja evaluateDevice.
func enCorredor() device.Device {
	d := 42.0
	return device.Device{ID: "dev-a", Name: "A", Provider: "sim", RouteID: "route-centro",
		RouteState: device.OnRoute, RouteDeviationM: &d}
}

func fueraDelCorredor() device.Device {
	d := 742.5
	return device.Device{ID: "dev-a", Name: "A", Provider: "sim", RouteID: "route-centro",
		RouteState: device.OffRoute, RouteDeviationM: &d}
}

// TestSalidaDeCorredorEmiteLaAccionDeLaRuta es el caso dorado de
// legacy/tests/test_engine_routes.py::test_route_exit_fires_without_fence_change:
// la orden sale por el cambio de estado de ruta, sin ninguna transición de
// geocerca de por medio.
func TestSalidaDeCorredorEmiteLaAccionDeLaRuta(t *testing.T) {
	rs := rutaConAcciones(fence.Action{Action: action.Notify, When: fence.OnExit, Enabled: true,
		Params: map[string]any{"channel": "security"}})
	prev := enCorredor()
	got := planRoute(&prev, fueraDelCorredor(), rs)
	if len(got) != 1 || got[0].Action != action.Notify || got[0].RouteID != "route-centro" {
		t.Fatalf("la salida del corredor emite la acción de la ruta: %+v", got)
	}
	if got[0].Trigger != TriggerRouteExit || got[0].FenceID != "" {
		t.Fatalf("la orden es de ruta, no de geocerca: %+v", got[0])
	}
	if got[0].Params["channel"] != "security" {
		t.Fatalf("los parámetros de la ruta viajan en la orden: %+v", got[0].Params)
	}
}

// TestRutaSinAccionesEmiteElNotifyDeRespaldo porta
// legacy/lucidfence/core/engine.py::_fire_route_exit: la salida del corredor
// nunca es silenciosa.
func TestRutaSinAccionesEmiteElNotifyDeRespaldo(t *testing.T) {
	prev := enCorredor()
	got := planRoute(&prev, fueraDelCorredor(), rutaConAcciones())
	if len(got) != 1 || got[0].Action != action.Notify || got[0].RouteID != "route-centro" {
		t.Fatalf("sin acciones declaradas cae al notify de respaldo: %+v", got)
	}
	msg, _ := got[0].Params["msg"].(string)
	if !strings.Contains(msg, "742.5 m") {
		t.Fatalf("el aviso debe decir cuántos metros: %q", msg)
	}
	apagada := rutaConAcciones(fence.Action{Action: action.Lock, When: fence.OnExit, Enabled: false})
	if got := planRoute(&prev, fueraDelCorredor(), apagada); got != nil {
		t.Fatalf("una acción apagada a propósito no dispara ni cae al respaldo: %+v", got)
	}
}

func TestSalidaDeCorredorSoloEnLaTransicion(t *testing.T) {
	rs := rutaConAcciones(fence.Action{Action: action.Notify, When: fence.OnExit, Enabled: true})
	fuera := fueraDelCorredor()
	if got := planRoute(&fuera, fuera, rs); got != nil {
		t.Fatalf("seguir fuera no reemite en cada ciclo: %+v", got)
	}
	if got := planRoute(nil, fuera, rs); got != nil {
		t.Fatalf("la primera vez que se ve un dispositivo no es una salida: %+v", got)
	}
	prev := enCorredor()
	if got := planRoute(&prev, enCorredor(), rs); got != nil {
		t.Fatalf("seguir en el corredor no emite nada: %+v", got)
	}
	sinAsignar := enCorredor()
	sinAsignar.RouteState, sinAsignar.RouteID, sinAsignar.RouteDeviationM = device.Unassigned, "", nil
	if got := planRoute(&sinAsignar, fuera, rs); len(got) != 1 {
		t.Fatalf("de unassigned a off_route también es salir del corredor: %+v", got)
	}
	if got := planRoute(&prev, fuera, nil); got != nil {
		t.Fatalf("sin ruta asignada no hay corredor del que salir: %+v", got)
	}
	// Volver a entrar y salir otra vez sí vuelve a avisar.
	if got := planRoute(&prev, fueraDelCorredor(), rs); len(got) != 1 {
		t.Fatalf("una salida nueva vuelve a avisar: %+v", got)
	}
}
