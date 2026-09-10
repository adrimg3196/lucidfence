package engine

import (
	"context"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// Histórico dorado portado de legacy/tests/test_policy_replay.py.
var (
	replayT0  = time.Date(2026, 8, 10, 9, 0, 0, 0, time.UTC)
	replayFin = replayT0.Add(14*time.Hour + 30*time.Minute) // 23:30, fuera de horario
	hq        = geo.Point{Lat: 40.42, Lng: -3.70}
	cerca     = geo.Point{Lat: 40.42, Lng: -3.71}
	lejos     = geo.Point{Lat: 40.90, Lng: -3.70}
	masLejos  = geo.Point{Lat: 41.00, Lng: -3.70}
)

type puntoDorado struct {
	device string
	punto  geo.Point
	at     time.Time
	clave  string // la clave de estado que el histórico de eventos registró
}

func trailDorado() []puntoDorado {
	return []puntoDorado{
		{"dev-a", hq, replayT0, "demo-hq:inside"},
		{"dev-a", lejos, replayT0.Add(time.Hour), "none:outside"},
		{"dev-b", cerca, replayT0.Add(65 * time.Minute), "demo-hq:inside"},
		{"dev-a", hq, replayT0.Add(2 * time.Hour), "demo-hq:inside"},
		{"dev-a", masLejos, replayFin, "none:outside"},
	}
}

// replayEngine deja un motor sin conectores sobre un store con la geocerca de
// HQ, dos dispositivos en su estado ACTUAL (dev-a rooteado hoy) y el histórico
// dorado escrito en trail.jsonl y events.jsonl.
func replayEngine(t *testing.T) (*Engine, *store.OrgStore) {
	t.Helper()
	s, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	centro := hq
	if err := org.SaveFences([]fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &centro, RadiusM: 5000}}); err != nil {
		t.Fatal(err)
	}
	rooted := true
	if err := org.SaveDevices([]device.Device{
		{ID: "dev-a", Name: "Furgoneta A", Platform: "android", Provider: "simulation", Posture: device.Posture{Rooted: &rooted}},
		{ID: "dev-b", Name: "Tablet B", Platform: "android", Provider: "simulation"},
	}); err != nil {
		t.Fatal(err)
	}
	escribirHistorico(t, org)
	if _, err := org.Settings(); err != nil { // siembra settings.json de fábrica (off-hours 20-7)
		t.Fatal(err)
	}
	ahora := replayT0.Add(24 * time.Hour)
	return New(org, nil, Options{Mode: "simulation", Now: func() time.Time { return ahora }}), org
}

func escribirHistorico(t *testing.T, org *store.OrgStore) {
	t.Helper()
	previa := map[string]string{}
	for _, p := range trailDorado() {
		if err := org.AppendTrail(p.device, p.punto, p.at); err != nil {
			t.Fatal(err)
		}
		if previa[p.device] == p.clave {
			continue
		}
		desde := previa[p.device]
		if desde == "" {
			desde = "none:unknown"
		}
		ev := transition.Transition{At: p.at, DeviceID: p.device, DeviceName: p.device, From: desde, To: p.clave}
		if err := org.AppendEvent(ev); err != nil {
			t.Fatal(err)
		}
		previa[p.device] = p.clave
	}
}

// politicaSalida es OUTSIDE_LOCK_POLICY de 1.x: bloquear al salir de geocerca.
func politicaSalida() policy.Policy {
	return policy.Policy{
		ID: "pol-lock-outside", Name: "Bloquear al salir de geocerca", Enabled: true, Severity: risk.SeverityHigh,
		When:    []policy.Condition{{Field: "fence_state", Op: policy.OpEq, Value: "outside"}},
		Actions: []policy.Action{{Action: action.Lock}},
	}
}

func contieneNota(notas []string, frag string) bool {
	for _, n := range notas {
		if strings.Contains(n, frag) {
			return true
		}
	}
	return false
}

func TestReplayCuentaLosDisparosDelHistorico(t *testing.T) {
	e, _ := replayEngine(t)
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida()})
	if err != nil {
		t.Fatal(err)
	}
	if res.PolicyID != "pol-lock-outside" || res.PointsEvaluated != 5 || res.DevicesEvaluated != 2 {
		t.Fatalf("recuento: %+v", res)
	}
	if res.Firings != 2 || res.ByDevice["dev-a"] != 2 || len(res.ByDevice) != 1 {
		t.Fatalf("dev-a sale dos veces y dev-b ninguna: %+v", res.ByDevice)
	}
	if res.ByAction["lock"] != 2 || len(res.ByAction) != 1 {
		t.Fatalf("reparto por acción: %+v", res.ByAction)
	}
	if res.From == nil || !res.From.Equal(replayT0) || res.To == nil || !res.To.Equal(replayFin) {
		t.Fatalf("ventana temporal: %v %v", res.From, res.To)
	}
	if len(res.Samples) != 2 {
		t.Fatalf("dos disparos, dos muestras: %+v", res.Samples)
	}
	comprobarMuestrasDeSalida(t, res.Samples)
}

// comprobarMuestrasDeSalida vive fuera del test para mantener la complejidad
// ciclomática de cada función por debajo del límite del proyecto (gocyclo ≤ 15),
// como ya hacen los round-trip de internal/store.
func comprobarMuestrasDeSalida(t *testing.T, samples []ReplaySample) {
	t.Helper()
	for _, s := range samples {
		if s.DeviceID != "dev-a" || s.DeviceName != "Furgoneta A" || s.FenceState != "outside" {
			t.Fatalf("muestra mal etiquetada: %+v", s)
		}
		if s.Score == nil || len(s.Reasons) == 0 || s.Severity == "" {
			t.Fatalf("cada disparo de ejemplo lleva su explicación: %+v", s)
		}
	}
}

func TestReplayDeUnaPoliticaEspacialSeDeclaraExacto(t *testing.T) {
	e, _ := replayEngine(t)
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida()})
	if err != nil {
		t.Fatal(err)
	}
	if res.Approximation {
		t.Fatalf("fence_state se reconstruye del histórico: %+v", res.Notes)
	}
	if !contieneNota(res.Notes, "Simulación exacta") || !contieneNota(res.Notes, "solo lectura") {
		t.Fatalf("notas: %+v", res.Notes)
	}
	if !contieneNota(res.Notes, "histórico de eventos") {
		t.Fatalf("la nota debe decir de dónde sale el estado de geocerca: %+v", res.Notes)
	}
}

func TestReplayConCondicionDePosturaSeDeclaraAproximado(t *testing.T) {
	e, _ := replayEngine(t)
	p := politicaSalida()
	p.When = append(p.When, policy.Condition{Field: "posture.rooted", Op: policy.OpEq, Value: true})
	res, err := e.Replay(ReplayRequest{Policy: p})
	if err != nil {
		t.Fatal(err)
	}
	if !res.Approximation || !contieneNota(res.Notes, "posture.rooted") {
		t.Fatalf("una condición no espacial obliga a declarar la aproximación: %+v", res.Notes)
	}
	if !contieneNota(res.Notes, "estado actual del dispositivo") {
		t.Fatalf("la nota explica de dónde sale el valor: %+v", res.Notes)
	}
	if res.Firings != 2 {
		t.Fatalf("dev-a está rooteado hoy: dispara en sus dos salidas, got %d", res.Firings)
	}
}

func TestReplayUsaLaHoraDelPuntoNoLaDeAhora(t *testing.T) {
	e, _ := replayEngine(t)
	p := politicaSalida()
	p.When = append(p.When, policy.Condition{Field: "signal:time_of_day.off_hours", Op: policy.OpEq, Value: true})
	res, err := e.Replay(ReplayRequest{Policy: p})
	if err != nil {
		t.Fatal(err)
	}
	if res.Firings != 1 || len(res.Samples) != 1 {
		t.Fatalf("de las dos salidas solo la de las 23:30 es fuera de horario: %+v", res)
	}
	if !res.Samples[0].At.Equal(replayFin) {
		t.Fatalf("la hora sale del punto, no del reloj de ahora: %v", res.Samples[0].At)
	}
	if res.Approximation {
		t.Fatalf("time_of_day se recalcula con el instante del punto: %+v", res.Notes)
	}
}

func TestReplayEvaluaAunqueLaPoliticaLlegueDeshabilitada(t *testing.T) {
	e, _ := replayEngine(t)
	p := politicaSalida()
	p.Enabled = false
	res, err := e.Replay(ReplayRequest{Policy: p})
	if err != nil || res.Firings != 2 {
		t.Fatalf("el what-if es sobre la candidata, que todavía no está activa: %v %+v", err, res)
	}
}

func TestReplayRechazaUnaPoliticaInvalidaSinEvaluarNada(t *testing.T) {
	e, _ := replayEngine(t)
	res, err := e.Replay(ReplayRequest{Policy: policy.Policy{Name: "sin id"}})
	if err == nil {
		t.Fatal("una política inválida no se simula")
	}
	if res.PointsEvaluated != 0 || res.Notes != nil || res.Samples != nil {
		t.Fatalf("un error no devuelve medio resultado: %+v", res)
	}
}

func TestReplaySobreUnHistoricoVacioNoPresentaElCeroComoResultado(t *testing.T) {
	s, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	e := New(org, nil, Options{Now: func() time.Time { return replayT0 }})
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida()})
	if err != nil {
		t.Fatal(err)
	}
	if res.PointsEvaluated != 0 || res.Firings != 0 || res.From != nil || res.To != nil {
		t.Fatalf("histórico vacío: %+v", res)
	}
	if res.ByDevice == nil || res.ByAction == nil || res.Samples == nil {
		t.Fatalf("los mapas y la lista van vacíos, nunca nulos: %+v", res)
	}
	if !contieneNota(res.Notes, "El histórico está vacío") {
		t.Fatalf("un cero sin explicación es un falso verde: %+v", res.Notes)
	}
}

func TestReplayRecalculaConLasGeocercasActuales(t *testing.T) {
	e, org := replayEngine(t)
	fs, err := org.Fences()
	if err != nil {
		t.Fatal(err)
	}
	// Geocerca hipotética gigante que cubre todos los puntos del histórico.
	centro := geo.Point{Lat: 40.6, Lng: -3.70}
	if err := org.SaveFences(append(fs, fence.Fence{ID: "todo-madrid", Name: "Todo Madrid",
		Kind: fence.Circle, Center: &centro, RadiusM: 200_000})); err != nil {
		t.Fatal(err)
	}
	historico, err := e.Replay(ReplayRequest{Policy: politicaSalida()})
	if err != nil {
		t.Fatal(err)
	}
	whatIf, err := e.Replay(ReplayRequest{Policy: politicaSalida(), UseCurrentFences: true})
	if err != nil {
		t.Fatal(err)
	}
	if historico.Firings != 2 {
		t.Fatalf("el histórico no cambia porque hoy se dibuje una geocerca: %d", historico.Firings)
	}
	if whatIf.Firings != 0 {
		t.Fatalf("con la geocerca nueva ningún punto queda fuera: %d", whatIf.Firings)
	}
	if !contieneNota(whatIf.Notes, "geocercas actuales") || contieneNota(whatIf.Notes, "histórico de eventos") {
		t.Fatalf("la nota declara la fuente del estado de geocerca: %+v", whatIf.Notes)
	}
}

func TestReplayNoEscribeNada(t *testing.T) {
	e, org := replayEngine(t)
	at := replayT0.Add(time.Hour)
	if err := org.AppendAction(action.Result{Adapter: "simulation", DeviceID: "dev-a", Action: action.Lock, DryRun: true, At: at}); err != nil {
		t.Fatal(err)
	}
	if err := org.RecordActionAt("dev-a", action.Lock, at); err != nil {
		t.Fatal(err)
	}
	ficheros := []string{"devices.json", "actions.jsonl", "cooldowns.json"}
	antes := instantanea(t, org, ficheros)
	if _, err := e.Replay(ReplayRequest{Policy: politicaSalida(), UseCurrentFences: true}); err != nil {
		t.Fatal(err)
	}
	despues := instantanea(t, org, ficheros)
	for _, name := range ficheros {
		if antes[name] != despues[name] {
			t.Fatalf("la simulación tocó %s: es un plan, no un apply", name)
		}
	}
}

// instantanea captura mtime y contenido de cada fichero: el mtime detecta la
// reescritura idéntica y el contenido, el cambio dentro del mismo segundo.
func instantanea(t *testing.T, org *store.OrgStore, ficheros []string) map[string]string {
	t.Helper()
	out := map[string]string{}
	for _, name := range ficheros {
		st, err := os.Stat(org.Path(name))
		if err != nil {
			t.Fatalf("%s debe existir antes de la simulación: %v", name, err)
		}
		body, err := os.ReadFile(org.Path(name))
		if err != nil {
			t.Fatal(err)
		}
		out[name] = st.ModTime().UTC().Format(time.RFC3339Nano) + "|" + string(body)
	}
	return out
}

func TestReplayEsSeguroMientrasCorreUnCiclo(t *testing.T) {
	e, _ := replayEngine(t)
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		_, _ = e.RunOnce(context.Background())
	}()
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida()})
	wg.Wait()
	if err != nil {
		t.Fatal(err)
	}
	if res.PolicyID != "pol-lock-outside" {
		t.Fatalf("la simulación no lee estado mutable del motor: %+v", res)
	}
}
