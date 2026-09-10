package engine

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// ordenRecibida es lo que el conector vio: qué acción y con qué dry-run. Sin
// el segundo campo, "el wipe no llegó" y "el wipe llegó en dry-run" serían
// indistinguibles, y son justo lo que separa la invariante de §6.5.
type ordenRecibida struct {
	Action action.Action
	DryRun bool
}

// tSOAR es el instante en que arrancan estos casos: el mismo reloj lo
// comparten el motor y el conector, para que RequestedAt y DecidedAt sean
// comprobables al segundo.
var tSOAR = time.Date(2026, 9, 6, 12, 0, 0, 0, time.UTC)

// grabadora es un conector de un solo dispositivo que apunta cada orden que
// recibe, como el _RecordingAdapter de legacy/tests/test_enforcement.py. Es la
// única forma de demostrar que una llamada NO ocurrió: un contador a cero solo
// dice que nadie la apuntó. La posición y la conformidad las fija el caso, y
// el reloj es el de T13 (internal/engine/risk_dwell_test.go), que el test
// adelanta entre ciclos.
type grabadora struct {
	clock    *reloj
	punto    geo.Point
	conforme bool

	mu       sync.Mutex
	recibido []ordenRecibida
}

func (g *grabadora) Name() string { return "grabadora" }

func (g *grabadora) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true}
}

// FetchDevices copia el punto y la conformidad: el motor muta lo que recibe y
// el conector no puede quedarse con el estado de un ciclo anterior.
func (g *grabadora) FetchDevices(context.Context) ([]device.Device, error) {
	p, conforme := g.punto, g.conforme
	now := g.clock.now().UTC()
	return []device.Device{{
		ID: "dev-1", Name: "Tablet almacén", Platform: "android", Provider: g.Name(),
		Compliant:    &conforme,
		Location:     device.Location{Point: &p, Source: g.Name(), ObservedAt: now},
		FenceState:   device.Unknown,
		RouteState:   device.Unassigned,
		Risk:         device.Verdict{Reasons: []string{}, MatchedPolicies: []string{}},
		LastReportAt: now,
	}}, nil
}

func (g *grabadora) Execute(_ context.Context, d device.Device, a action.Action,
	params map[string]any, dryRun bool) action.Result {
	g.mu.Lock()
	g.recibido = append(g.recibido, ordenRecibida{a, dryRun})
	g.mu.Unlock()
	return action.Result{Adapter: g.Name(), OK: true, DeviceID: d.ID, DeviceName: d.Name,
		Action: a, Params: params, DryRun: dryRun, Simulated: true, At: g.clock.now().UTC()}
}

func (g *grabadora) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "simulated"}
}

func (g *grabadora) recibidas() []ordenRecibida {
	g.mu.Lock()
	defer g.mu.Unlock()
	return append([]ordenRecibida(nil), g.recibido...)
}

func (g *grabadora) olvidar() {
	g.mu.Lock()
	g.recibido = nil
	g.mu.Unlock()
}

// pbBrecha es el playbook dorado de legacy/tests/test_soar_geofence_breach.py
// (dispositivo fuera de geovalla y no conforme) con las mismas dos acciones
// que el soar-rooted-outside de legacy/lucidfence/core/soar.py: un lock
// destructivo y un aviso al SOC.
func pbBrecha() playbook.Playbook {
	return playbook.Playbook{
		ID: "soar-brecha", Name: "Brecha de perímetro",
		When: []policy.Condition{
			{Field: "compliant", Op: policy.OpEq, Value: false},
			{Field: "fence_state", Op: policy.OpEq, Value: "outside"},
		},
		Actions: []policy.Action{
			{Action: action.Lock, Params: map[string]any{"reason": "noncompliant_outside"}},
			{Action: action.Notify, Params: map[string]any{"channel": "soc"}},
		},
		Enabled: true, Severity: risk.SeverityHigh,
	}
}

// pbWipe es el peor caso imaginable: un playbook que pide un borrado remoto.
func pbWipe() playbook.Playbook {
	p := pbBrecha()
	p.ID, p.Name = "soar-wipe", "Borrado por brecha"
	p.Actions = []policy.Action{{Action: action.Wipe}}
	p.Severity = risk.SeverityCritical
	return p
}

// motorSOAR monta un motor con una geocerca sin acciones (para que lo único
// que pueda ordenar algo sean los playbooks), los playbooks dados y un solo
// dispositivo en el punto y con la conformidad del caso. No llama a SeedDemo:
// así los playbooks de fábrica del paso 6 no se cuelan en estos casos.
func motorSOAR(t *testing.T, p geo.Point, compliant bool, pbs ...playbook.Playbook) (*Engine, *store.OrgStore, *grabadora, *reloj) {
	t.Helper()
	s, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	hq := fence.Fence{ID: "hq", Name: "HQ", Kind: fence.Circle,
		Center: &geo.Point{Lat: dentroHQ.Lat, Lng: dentroHQ.Lng}, RadiusM: 500,
		CreatedAt: tSOAR, UpdatedAt: tSOAR}
	if err := org.SaveFences([]fence.Fence{hq}); err != nil {
		t.Fatal(err)
	}
	if err := org.SavePlaybooks(pbs); err != nil {
		t.Fatal(err)
	}
	rel := &reloj{at: tSOAR}
	fleet := &grabadora{clock: rel, punto: p, conforme: compliant}
	e := New(org, []uem.Adapter{fleet}, Options{Mode: "simulation", Interval: time.Hour, Now: rel.now})
	return e, org, fleet, rel
}

// unCiclo corre un ciclo y devuelve sus estadísticas.
func unCiclo(t *testing.T, e *Engine) CycleStats {
	t.Helper()
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	return st
}

// bandejaDe lee handoffs.json.
func bandejaDe(t *testing.T, org *store.OrgStore) []playbook.Handoff {
	t.Helper()
	hs, err := org.Handoffs()
	if err != nil {
		t.Fatal(err)
	}
	return hs
}

// TestUnWipeDePlaybookNuncaLlegaAlConector es LA invariante de la spec §6.5 y
// el caso dorado de
// legacy/tests/test_multiuem_soar_gaps.py::test_soar_human_gate_emits_handoff_not_execution:
// la acción destructiva no se ejecuta, se convierte en una petición humana.
func TestUnWipeDePlaybookNuncaLlegaAlConector(t *testing.T) {
	e, org, fleet, _ := motorSOAR(t, fueraHQ, false, pbWipe())
	st := unCiclo(t, e)

	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("ninguna acción destructiva de un playbook llega al conector sin handoff aprobado: %v", got)
	}
	if st.ActionsExecuted != 0 || st.ActionsPlanned != 0 || st.HandoffsPending != 1 {
		t.Fatalf("el wipe abre una petición y no ejecuta nada: %+v", st)
	}
	hs := bandejaDe(t, org)
	if len(hs) != 1 {
		t.Fatalf("un solo handoff: %+v", hs)
	}
	assertPeticionDelWipe(t, hs[0])
}

// assertPeticionDelWipe comprueba la petición que abrió el ciclo. Es una
// función con nombre y no un bloque más del test porque gocyclo suma todas
// las ramas de la función que las contiene, igual que los assertXxx de
// engine_test.go.
func assertPeticionDelWipe(t *testing.T, h playbook.Handoff) {
	t.Helper()
	if h.ID != playbook.HandoffID("dev-1", "soar-wipe", action.Wipe) ||
		h.Status != playbook.HandoffPending || h.Action != action.Wipe {
		t.Fatalf("handoff pendiente con el id determinista de T6: %+v", h)
	}
	if h.DeviceID != "dev-1" || h.DeviceName != "Tablet almacén" ||
		h.PlaybookID != "soar-wipe" || h.PlaybookName != "Borrado por brecha" ||
		h.Severity != risk.SeverityCritical {
		t.Fatalf("el handoff dice a quién, por qué playbook y con qué gravedad: %+v", h)
	}
	if h.Reason != "compliant=false, fence_state=outside" {
		t.Fatalf("el motivo son los campos que casaron con su valor: %q", h.Reason)
	}
	if h.Result != nil || h.DecidedAt != nil || h.DecidedBy != "" || !h.RequestedAt.Equal(tSOAR) {
		t.Fatalf("nace sin resultado y sin decisión, sellado con el reloj del ciclo: %+v", h)
	}
}

// TestLoNoDestructivoDeUnPlaybookSiSeEjecuta es la otra mitad del caso
// dorado: "acciones no destructivas (notify) sí proceden".
func TestLoNoDestructivoDeUnPlaybookSiSeEjecuta(t *testing.T) {
	e, org, fleet, _ := motorSOAR(t, fueraHQ, false, pbBrecha())
	st := unCiclo(t, e)

	got := fleet.recibidas()
	if len(got) != 1 || got[0].Action != action.Notify || !got[0].DryRun {
		t.Fatalf("solo el aviso llega al conector, y en observe en dry-run: %v", got)
	}
	if st.ActionsExecuted != 1 || st.HandoffsPending != 1 {
		t.Fatalf("una acción ejecutada y una petición pendiente: %+v", st)
	}
	acts, err := org.RecentActions(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) != 1 || acts[0].Action != action.Notify {
		t.Fatalf("el registro de acciones solo tiene el aviso: %+v", acts)
	}
	if acts[0].PlaybookID != "soar-brecha" || acts[0].Trigger != TriggerPlaybook ||
		acts[0].Severity != risk.SeverityHigh {
		t.Fatalf("la orden queda trazada al playbook que la pidió: %+v", acts[0])
	}
	if hs := bandejaDe(t, org); len(hs) != 1 || hs[0].Action != action.Lock {
		t.Fatalf("el lock del mismo playbook se quedó en la bandeja: %+v", hs)
	}
}

// TestElCicloNoDuplicaUnHandoffPendiente: la condición sigue dándose ciclo
// tras ciclo y la bandeja sigue teniendo una sola petición.
func TestElCicloNoDuplicaUnHandoffPendiente(t *testing.T) {
	e, org, fleet, rel := motorSOAR(t, fueraHQ, false, pbWipe())
	unCiclo(t, e)
	rel.avanzar(time.Hour)
	st := unCiclo(t, e)

	if st.HandoffsPending != 1 {
		t.Fatalf("mientras siga pendiente no se abre un segundo: %+v", st)
	}
	hs := bandejaDe(t, org)
	if len(hs) != 1 || !hs[0].RequestedAt.Equal(tSOAR) {
		t.Fatalf("la petición es la misma, con su instante original: %+v", hs)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("dos ciclos y ninguna llamada al conector: %v", got)
	}
}

// TestDentroYConformeNoAbreNingunHandoff es el falso positivo evitado de
// legacy/tests/test_soar_geofence_breach.py::test_dentro_conforme_no_dispara.
func TestDentroYConformeNoAbreNingunHandoff(t *testing.T) {
	e, org, fleet, _ := motorSOAR(t, dentroHQ, true, pbBrecha(), pbWipe())
	st := unCiclo(t, e)

	if st.HandoffsPending != 0 || st.ActionsExecuted != 0 {
		t.Fatalf("dentro de la geocerca y conforme no dispara nada: %+v", st)
	}
	if hs := bandejaDe(t, org); len(hs) != 0 {
		t.Fatalf("la bandeja sigue vacía: %+v", hs)
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("ninguna orden: %v", got)
	}
}

// TestUnPlaybookDeshabilitadoNoAbreHandoff: apagar el playbook es la forma de
// callar la petición, y funciona en el ciclo, no solo en el dominio.
func TestUnPlaybookDeshabilitadoNoAbreHandoff(t *testing.T) {
	apagado := pbWipe()
	apagado.Enabled = false
	e, org, _, _ := motorSOAR(t, fueraHQ, false, apagado)
	if st := unCiclo(t, e); st.HandoffsPending != 0 {
		t.Fatalf("un playbook apagado no casa: %+v", st)
	}
	if hs := bandejaDe(t, org); len(hs) != 0 {
		t.Fatalf("la bandeja sigue vacía: %+v", hs)
	}
}

// TestUnHandoffRechazadoNoSeReabreEnSeguida protege la bandeja del operador:
// contestar "no" no puede significar que te lo vuelvan a preguntar en quince
// minutos, pero tampoco callar para siempre una condición peligrosa.
func TestUnHandoffRechazadoNoSeReabreEnSeguida(t *testing.T) {
	e, org, fleet, rel := motorSOAR(t, fueraHQ, false, pbWipe())
	unCiclo(t, e)
	if _, err := e.RejectHandoff(context.Background(), playbook.HandoffID("dev-1", "soar-wipe", action.Wipe),
		"ana@lucidfence.test", "falso positivo de GPS"); err != nil {
		t.Fatal(err)
	}

	rel.avanzar(time.Hour)
	st := unCiclo(t, e)
	hs := bandejaDe(t, org)
	if st.HandoffsPending != 0 || len(hs) != 1 || hs[0].Status != playbook.HandoffRejected {
		t.Fatalf("una hora después la decisión sigue en pie: %+v %+v", st, hs)
	}

	rel.avanzar(HandoffReopenAfter)
	st = unCiclo(t, e)
	hs = bandejaDe(t, org)
	if st.HandoffsPending != 1 || len(hs) != 1 || hs[0].Status != playbook.HandoffPending {
		t.Fatalf("pasadas 24 h la condición vuelve a preguntar: %+v %+v", st, hs)
	}
	if !hs[0].RequestedAt.Equal(rel.now()) || hs[0].DecidedAt != nil {
		t.Fatalf("la petición reabierta es nueva, no la rechazada: %+v", hs[0])
	}
	if got := fleet.recibidas(); len(got) != 0 {
		t.Fatalf("tres ciclos y un rechazo: el wipe nunca llegó al conector: %v", got)
	}
}

// TestUnDispositivoRotoNoDisparaPlaybooks: sin veredicto no hay evidencia.
func TestUnDispositivoRotoNoDisparaPlaybooks(t *testing.T) {
	e, org, _, _ := motorSOAR(t, fueraHQ, false, pbWipe())
	e.evalHook = func(*device.Device) { panic("evaluador roto") }
	st := unCiclo(t, e)

	if st.EvaluationErrors != 1 || st.HandoffsPending != 0 {
		t.Fatalf("un dispositivo roto no abre peticiones destructivas: %+v", st)
	}
	if hs := bandejaDe(t, org); len(hs) != 0 {
		t.Fatalf("la bandeja sigue vacía: %+v", hs)
	}
}

// TestSeedDemoSiembraLosPlaybooksDeFabrica: la demo arranca con SOAR y un
// ciclo deja una petición esperando a una persona (dev-004 está fuera y no
// es conforme), que es lo que enseña el e2e de T29.
func TestSeedDemoSiembraLosPlaybooksDeFabrica(t *testing.T) {
	e, org := newEngine(t)
	pbs, err := org.Playbooks()
	if err != nil {
		t.Fatal(err)
	}
	if len(pbs) != 3 || pbs[0].ID != "soar-noncompliant-outside" {
		t.Fatalf("los tres playbooks de fábrica, en el orden del catálogo: %+v", pbs)
	}
	for _, p := range pbs {
		if !p.Enabled || p.CreatedAt.IsZero() || p.UpdatedAt.IsZero() {
			t.Fatalf("el playbook demo nace activado y sellado: %+v", p)
		}
		if err := p.Validate(); err != nil {
			t.Fatalf("el playbook demo debe ser válido: %v", err)
		}
	}
	st := unCiclo(t, e)
	if st.HandoffsPending != 1 {
		t.Fatalf("la demo deja una petición pendiente: %+v", st)
	}
	hs := bandejaDe(t, org)
	if len(hs) != 1 || hs[0].ID != playbook.HandoffID("dev-004", "soar-noncompliant-outside", action.Lock) {
		t.Fatalf("el lock de dev-004, que está fuera y no es conforme: %+v", hs)
	}
}
