package engine

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// dwellT0 es el instante en que el dispositivo entra en la geocerca.
var dwellT0 = time.Date(2026, 9, 6, 9, 0, 0, 0, time.UTC)

// cercaConDwell es una geocerca con permanencia mínima de 300 s: el mensaje de
// bienvenida solo debe salir cuando el turno de verdad ha empezado.
func cercaConDwell() []fence.Fence {
	return []fence.Fence{{ID: "almacen", Name: "Almacén", Kind: fence.Circle,
		Center: &geo.Point{Lat: 40.405, Lng: -3.711}, RadiusM: 300,
		Rules: fence.Rules{DwellSeconds: 300},
		Actions: []fence.Action{
			{Action: action.Message, When: fence.OnEnter, Enabled: true, Params: map[string]any{"text": "Turno iniciado"}},
			{Action: action.Notify, When: fence.OnExit, Enabled: true},
		}}}
}

// dentroDesde devuelve el dispositivo dentro de la geocerca con la estancia
// arrancada en since y la permanencia acumulada dada, tal como lo deja
// transition.Evaluate (T1).
func dentroDesde(since time.Time, dwell int) device.Device {
	s := since
	return device.Device{ID: "dev-a", Name: "A", Provider: "sim",
		FenceState: device.Inside, InsideFence: "almacen", FenceStateSince: &s, DwellSeconds: dwell}
}

// fueraDesde es el mismo dispositivo ya fuera de la geocerca.
func fueraDesde(since time.Time) device.Device {
	s := since
	return device.Device{ID: "dev-a", Name: "A", Provider: "sim",
		FenceState: device.Outside, LastInsideFence: "almacen", FenceStateSince: &s}
}

func TestDwellNoDisparaEnLaEntrada(t *testing.T) {
	e := motorMudo()
	fs := cercaConDwell()
	cur := dentroDesde(dwellT0, 0)
	tr := &transition.Transition{From: "none:outside", To: "almacen:inside"}
	if got := PlanTransition(cur, tr, fs); got != nil {
		t.Fatalf("con dwell configurado el on_enter ya no sale en la transición: %+v", got)
	}
	if got := e.planDwell(cur, fs); got != nil {
		t.Fatalf("en el ciclo de entrada la permanencia es 0: %+v", got)
	}
}

func TestDwellDisparaUnaSolaVezPasadoElUmbral(t *testing.T) {
	e := motorMudo()
	fs := cercaConDwell()
	if got := e.planDwell(dentroDesde(dwellT0, 299), fs); got != nil {
		t.Fatalf("299 s todavía no llegan a 300: %+v", got)
	}
	got := e.planDwell(dentroDesde(dwellT0, 300), fs)
	if len(got) != 1 || got[0].Action != action.Message || got[0].FenceID != "almacen" {
		t.Fatalf("al alcanzar el umbral sale el on_enter: %+v", got)
	}
	if got[0].Trigger != TriggerDwell || got[0].Severity != risk.SeverityMedium {
		t.Fatalf("la orden se registra como dwell: %+v", got[0])
	}
	if got[0].Params["text"] != "Turno iniciado" {
		t.Fatalf("los parámetros de la acción viajan en la orden: %+v", got[0].Params)
	}
	for _, dwell := range []int{360, 900, 3600} {
		if extra := e.planDwell(dentroDesde(dwellT0, dwell), fs); extra != nil {
			t.Fatalf("la misma estancia no vuelve a disparar (dwell %d): %+v", dwell, extra)
		}
	}
}

func TestSalirYVolverAEntrarReiniciaLaEstancia(t *testing.T) {
	e := motorMudo()
	fs := cercaConDwell()
	if got := e.planDwell(dentroDesde(dwellT0, 300), fs); len(got) != 1 {
		t.Fatalf("primera estancia: %+v", got)
	}
	if got := e.planDwell(fueraDesde(dwellT0.Add(time.Hour)), fs); got != nil {
		t.Fatalf("fuera no hay permanencia que contar: %+v", got)
	}
	if _, existe := e.dwelled["dev-a|almacen"]; existe {
		t.Fatal("salir debe borrar la marca de la estancia, no conservarla")
	}
	vuelta := dwellT0.Add(2 * time.Hour)
	if got := e.planDwell(dentroDesde(vuelta, 300), fs); len(got) != 1 {
		t.Fatalf("una estancia nueva vuelve a permitir el disparo: %+v", got)
	}
}

// TestPasoFugazNoDisparaNada: entrar y salir antes del umbral no deja ninguna
// orden de entrada, y el on_exit sigue saliendo (no depende del dwell).
func TestPasoFugazNoDisparaNada(t *testing.T) {
	e := motorMudo()
	fs := cercaConDwell()
	entra := dentroDesde(dwellT0, 0)
	planned := append(PlanTransition(entra, &transition.Transition{From: "none:outside", To: "almacen:inside"}, fs),
		e.planDwell(entra, fs)...)
	sale := fueraDesde(dwellT0.Add(90 * time.Second))
	planned = append(planned, e.planDwell(sale, fs)...)
	if len(planned) != 0 {
		t.Fatalf("un paso fugaz no dispara el on_enter: %+v", planned)
	}
	salida := PlanTransition(sale, &transition.Transition{From: "almacen:inside", To: "none:outside"}, fs)
	if len(salida) != 1 || salida[0].Action != action.Notify || salida[0].Trigger != string(fence.OnExit) {
		t.Fatalf("el on_exit sí sale: %+v", salida)
	}
}

func TestSinDwellElOnEnterSigueSaliendoEnLaTransicion(t *testing.T) {
	e := motorMudo()
	fs := cercaConDwell()
	fs[0].Rules.DwellSeconds = 0
	cur := dentroDesde(dwellT0, 0)
	got := PlanTransition(cur, &transition.Transition{From: "none:outside", To: "almacen:inside"}, fs)
	if len(got) != 1 || got[0].Action != action.Message || got[0].Trigger != string(fence.OnEnter) {
		t.Fatalf("sin dwell el comportamiento es el de M1: %+v", got)
	}
	if extra := e.planDwell(dentroDesde(dwellT0, 9000), fs); extra != nil {
		t.Fatalf("sin dwell configurado no hay estancia que vigilar: %+v", extra)
	}
}

// TestViolacionSostenidaCada3Ciclos porta el throttle de
// legacy/lucidfence/core/engine.py::_fire_standing_violation.
func TestViolacionSostenidaCada3Ciclos(t *testing.T) {
	fs := testFences()
	fs[0].Rules.ViolationIntervalCycles = 3
	e := motorMudo()
	fuera := device.Device{ID: "d", Name: "D", Provider: "sim", FenceState: device.Outside}
	var disparos []int
	for ciclo := 1; ciclo <= 9; ciclo++ {
		got := e.planStanding(fuera, fs)
		if len(got) == 0 {
			continue
		}
		if len(got) != 1 || got[0].Action != action.Lock || got[0].Trigger != string(fence.OnViolation) {
			t.Fatalf("ciclo %d: %+v", ciclo, got)
		}
		if got[0].Severity != risk.SeverityHigh {
			t.Fatalf("una violación sostenida es de severidad alta: %+v", got[0])
		}
		disparos = append(disparos, ciclo)
	}
	if len(disparos) != 3 || disparos[0] != 3 || disparos[1] != 6 || disparos[2] != 9 {
		t.Fatalf("debe disparar en los ciclos 3, 6 y 9: %v", disparos)
	}
	dentro := device.Device{ID: "d", Name: "D", Provider: "sim", FenceState: device.Inside, InsideFence: "demo-hq"}
	e.planStanding(dentro, fs)
	if _, existe := e.violations["d|demo-hq"]; existe {
		t.Fatal("volver dentro debe borrar la clave del mapa, no ponerla a cero")
	}
	if got := e.planStanding(fuera, fs); len(got) != 0 {
		t.Fatalf("tras el reset el contador arranca de nuevo en 1: %+v", got)
	}
}

// TestOnUnknownNuncaEmiteAccionesDestructivas es el caso dorado de
// legacy/lucidfence/core/engine.py::_fire_actions: perder señal no es
// evidencia y jamás justifica lock, wipe, reboot ni clear_passcode.
func TestOnUnknownNuncaEmiteAccionesDestructivas(t *testing.T) {
	fs := []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle,
		Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
		Actions: []fence.Action{
			{Action: action.Locate, When: fence.OnUnknown, Enabled: true},
			{Action: action.Lock, When: fence.OnUnknown, Enabled: true},
			{Action: action.Wipe, When: fence.OnUnknown, Enabled: true},
			{Action: action.Reboot, When: fence.OnUnknown, Enabled: true},
			{Action: action.ClearPasscode, When: fence.OnUnknown, Enabled: true},
			{Action: action.Notify, When: fence.OnUnknown, Enabled: true},
		}}}
	cur := device.Device{ID: "d", Name: "D", Provider: "sim",
		FenceState: device.Unknown, LastInsideFence: "demo-hq"}
	got := PlanTransition(cur, &transition.Transition{From: "demo-hq:inside", To: "none:unknown"}, fs)
	if len(got) != 2 {
		t.Fatalf("solo salen las dos no destructivas (locate y notify): %+v", got)
	}
	for _, p := range got {
		if p.Action.Destructive() {
			t.Fatalf("perder señal no es evidencia: %+v", p)
		}
	}
}

// TestDwellDeExtremoAExtremoEnElCiclo comprueba el dwell sobre ciclos reales:
// transition.Evaluate lleva el reloj de la estancia y el motor solo emite el
// on_enter cuando supera el umbral, una vez.
func TestDwellDeExtremoAExtremoEnElCiclo(t *testing.T) {
	e, org, clock, _ := motorConReloj(t, geo.Point{Lat: 40.405, Lng: -3.711})
	if err := org.SaveFences(cercaConDwell()); err != nil {
		t.Fatal(err)
	}
	corre := func(quiero int, motivo string) device.Device {
		t.Helper()
		d := cicloViajero(t, e, org)
		if n := accionesConTrigger(t, org, TriggerDwell); n != quiero {
			t.Fatalf("%s: %d órdenes de dwell, quiero %d", motivo, n, quiero)
		}
		return d
	}
	corre(0, "ciclo de entrada, permanencia 0")
	clock.avanzar(10 * time.Minute)
	corre(1, "a los 600 s sale el on_enter")
	clock.avanzar(10 * time.Minute)
	d := corre(1, "la misma estancia no vuelve a disparar")
	if d.DwellSeconds != 1200 || d.InsideFence != "almacen" {
		t.Fatalf("la permanencia debe acumular sobre la misma estancia: %+v", d)
	}
}

// accionesConTrigger cuenta las acciones registradas con un disparador dado.
func accionesConTrigger(t *testing.T, org *store.OrgStore, trigger string) int {
	t.Helper()
	acts, err := org.RecentActions(200)
	if err != nil {
		t.Fatal(err)
	}
	n := 0
	for _, a := range acts {
		if a.Trigger == trigger {
			n++
		}
	}
	return n
}
