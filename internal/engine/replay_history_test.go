package engine

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/store"
)

func TestReplayLimitAplicaDefectoYTecho(t *testing.T) {
	casos := []struct{ pedido, quiere int }{
		{0, ReplayDefaultLimit},
		{-7, ReplayDefaultLimit},
		{10, 10},
		{ReplayMaxPoints + 1, ReplayMaxPoints},
	}
	for _, c := range casos {
		if got := replayLimit(c.pedido); got != c.quiere {
			t.Fatalf("replayLimit(%d) = %d, quiere %d", c.pedido, got, c.quiere)
		}
	}
	if ReplayMaxPoints > store.MaxTrailPoints {
		t.Fatalf("el techo del motor (%d) no puede superar el del store (%d)", ReplayMaxPoints, store.MaxTrailPoints)
	}
}

func TestReplayConLimiteSoloSimulaLaColaDelHistorico(t *testing.T) {
	e, _ := replayEngine(t)
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida(), Limit: 2})
	if err != nil {
		t.Fatal(err)
	}
	if res.PointsEvaluated != 2 || res.Firings != 1 {
		t.Fatalf("los dos últimos puntos son el regreso a HQ y la salida nocturna: %+v", res)
	}
	if res.From == nil || !res.From.Equal(replayT0.Add(2*time.Hour)) {
		t.Fatalf("la ventana empieza en el penúltimo punto: %v", res.From)
	}
	if !contieneNota(res.Notes, "Ventana limitada a los últimos 2 puntos") {
		t.Fatalf("una ventana recortada se declara: %+v", res.Notes)
	}
}

func TestReplayCortaLasMuestrasYAvisaDeDispositivosFueraDelInventario(t *testing.T) {
	e, org := replayEngine(t)
	bilbao := geo.Point{Lat: 43.26, Lng: -2.93}
	for i := 0; i < 60; i++ {
		if err := org.AppendTrail("dev-fantasma", bilbao, replayFin.Add(time.Duration(i)*time.Minute)); err != nil {
			t.Fatal(err)
		}
	}
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida(), UseCurrentFences: true})
	if err != nil {
		t.Fatal(err)
	}
	if res.PointsEvaluated != 65 || res.DevicesEvaluated != 3 {
		t.Fatalf("recuento: %+v", res)
	}
	if res.Firings != 62 || res.ByDevice["dev-fantasma"] != 60 || res.ByAction["lock"] != 62 {
		t.Fatalf("los totales cuentan todos los disparos, no solo las muestras: %+v", res)
	}
	if len(res.Samples) != ReplayMaxSamples {
		t.Fatalf("las muestras se cortan en %d: %d", ReplayMaxSamples, len(res.Samples))
	}
	if !contieneNota(res.Notes, "60 puntos son de dispositivos que ya no están en el inventario") {
		t.Fatalf("notas: %+v", res.Notes)
	}
}

func TestReplayReconstruyeElDwellDelHistorico(t *testing.T) {
	e, org := replayEngine(t)
	// dev-b entró en HQ a las 10:05 y sigue dentro dos horas después.
	if err := org.AppendTrail("dev-b", cerca, replayT0.Add(3*time.Hour+5*time.Minute)); err != nil {
		t.Fatal(err)
	}
	p := policy.Policy{
		ID: "pol-dwell", Name: "Permanencia larga", Enabled: true, Severity: risk.SeverityMedium,
		When: []policy.Condition{
			{Field: "fence_state", Op: policy.OpEq, Value: "inside"},
			{Field: "dwell_seconds", Op: policy.OpGte, Value: 3600},
		},
		Actions: []policy.Action{{Action: action.Notify}},
	}
	res, err := e.Replay(ReplayRequest{Policy: p})
	if err != nil {
		t.Fatal(err)
	}
	if res.Firings != 1 || res.ByDevice["dev-b"] != 1 {
		t.Fatalf("solo el punto de dev-b dos horas después de entrar supera la hora: %+v", res)
	}
	if res.Approximation {
		t.Fatalf("el dwell se reconstruye del histórico: %+v", res.Notes)
	}
}

func TestSinTransicionPreviaElEstadoHistoricoEsDesconocido(t *testing.T) {
	e, org := replayEngine(t)
	if err := org.AppendTrail("dev-c", cerca, replayT0.Add(-time.Hour)); err != nil {
		t.Fatal(err)
	}
	p := politicaSalida()
	p.When = []policy.Condition{{Field: "fence_state", Op: policy.OpEq, Value: "unknown"}}
	res, err := e.Replay(ReplayRequest{Policy: p})
	if err != nil {
		t.Fatal(err)
	}
	if res.Firings != 1 || res.ByDevice["dev-c"] != 1 {
		t.Fatalf("un punto anterior a toda transición no se puede situar: %+v", res)
	}
}

func TestParseKeyDescomponeLaClaveDeTransicion(t *testing.T) {
	casos := []struct {
		key   string
		state device.FenceState
		id    string
	}{
		{"demo-hq:inside", device.Inside, "demo-hq"},
		{"none:outside", device.Outside, ""},
		{"none:unknown", device.Unknown, ""},
		{"sin-dos-puntos", device.Unknown, ""},
		{"demo-hq:inventado", device.Unknown, ""},
	}
	for _, c := range casos {
		state, id := parseKey(c.key)
		if state != c.state || id != c.id {
			t.Fatalf("parseKey(%q) = %q %q", c.key, state, id)
		}
	}
}

func TestDwellSecondsNuncaEsNegativo(t *testing.T) {
	at := replayT0
	if got := dwellSeconds(at.Add(-90*time.Second), at); got != 90 {
		t.Fatalf("dwell: %d", got)
	}
	if got := dwellSeconds(at.Add(time.Hour), at); got != 0 {
		t.Fatalf("un reloj hacia atrás no puede dar dwell negativo: %d", got)
	}
}

// estanciaLarga siembra el caso que separa los dos modos: dev-d lleva DENTRO
// de HQ desde hace 24 h —la transición lo fecha— y reporta cada diez minutos
// durante las tres horas que cubre la ventana simulada. El histórico sabe
// cuándo entró; las geocercas actuales solo ven la racha que empieza en el
// primer punto simulado.
func estanciaLarga(t *testing.T, org *store.OrgStore) {
	t.Helper()
	ds, err := org.Devices()
	if err != nil {
		t.Fatal(err)
	}
	nuevo := device.Device{ID: "dev-d", Name: "Portátil D", Platform: "android", Provider: "simulation"}
	if err := org.SaveDevices(append(ds, nuevo)); err != nil {
		t.Fatal(err)
	}
	if err := org.AppendEvent(transition.Transition{
		At: replayT0.Add(-24 * time.Hour), DeviceID: "dev-d", DeviceName: "Portátil D",
		From: "none:unknown", To: "demo-hq:inside",
	}); err != nil {
		t.Fatal(err)
	}
	for i := 0; i <= 18; i++ {
		if err := org.AppendTrail("dev-d", cerca, replayT0.Add(time.Duration(i)*10*time.Minute)); err != nil {
			t.Fatal(err)
		}
	}
}

// politicaPermanencia exige cuatro horas dentro de la geocerca: más que las
// tres que cubre la ventana simulada, que es lo que convierte el recorte del
// dwell en un cero.
func politicaPermanencia() policy.Policy {
	return policy.Policy{
		ID: "pol-dwell-largo", Name: "Permanencia larga", Enabled: true, Severity: risk.SeverityHigh,
		When: []policy.Condition{
			{Field: "fence_state", Op: policy.OpEq, Value: "inside"},
			{Field: "dwell_seconds", Op: policy.OpGte, Value: 14400},
		},
		Actions: []policy.Action{{Action: action.Lock}},
	}
}

// TestConGeocercasActualesElDwellNoSePuedeDeclararExacto es el falso verde que
// el brief no vio: el mismo dispositivo, la misma política y los mismos puntos
// dan 19 disparos leyendo el histórico y 0 recalculando con las geocercas de
// hoy, porque ahí la permanencia se cuenta desde el primer punto de la ventana
// y nunca llega a las cuatro horas. Un cero es una respuesta legítima; un cero
// declarado "Simulación exacta" delante de una regla que bloquea, no.
func TestConGeocercasActualesElDwellNoSePuedeDeclararExacto(t *testing.T) {
	e, org := replayEngine(t)
	estanciaLarga(t, org)
	hist, err := e.Replay(ReplayRequest{Policy: politicaPermanencia()})
	if err != nil {
		t.Fatal(err)
	}
	if hist.Firings != 19 || hist.Approximation || !contieneNota(hist.Notes, "Simulación exacta") {
		t.Fatalf("con el histórico el dwell sale entero de la transición: %d %v %v", hist.Firings, hist.Approximation, hist.Notes)
	}
	cur, err := e.Replay(ReplayRequest{Policy: politicaPermanencia(), UseCurrentFences: true})
	if err != nil {
		t.Fatal(err)
	}
	if cur.Firings != 0 || cur.PointsEvaluated != hist.PointsEvaluated {
		t.Fatalf("la racha empieza en la ventana: ningún punto llega a las cuatro horas: %+v", cur)
	}
	if !cur.Approximation {
		t.Fatalf("un cero que sale de una ventana recortada no es un resultado exacto: %v", cur.Notes)
	}
	if contieneNota(cur.Notes, "Simulación exacta") {
		t.Fatalf("nada de esto es exacto: %v", cur.Notes)
	}
	if !contieneNota(cur.Notes, "primer punto de la ventana simulada") {
		t.Fatalf("la nota tiene que decir de dónde sale la permanencia y hacia dónde falla: %v", cur.Notes)
	}
}

// TestConGeocercasActualesUnaPoliticaSinDwellSigueSiendoExacta es el reverso:
// recalcular el estado de geocerca con las de hoy es exacto (es el what-if que
// se pidió, no una aproximación), así que el aviso del dwell no puede aparecer
// donde no hay dwell ni marcar aproximada una política puramente espacial.
func TestConGeocercasActualesUnaPoliticaSinDwellSigueSiendoExacta(t *testing.T) {
	e, _ := replayEngine(t)
	res, err := e.Replay(ReplayRequest{Policy: politicaSalida(), UseCurrentFences: true})
	if err != nil {
		t.Fatal(err)
	}
	if res.Approximation || !contieneNota(res.Notes, "Simulación exacta") {
		t.Fatalf("sin dwell_seconds no hay nada que recortar: %v %v", res.Approximation, res.Notes)
	}
	if contieneNota(res.Notes, "primer punto de la ventana simulada") {
		t.Fatalf("una política que no mira dwell_seconds no necesita el aviso: %v", res.Notes)
	}
	if res.Firings != 2 {
		t.Fatalf("dev-a sale dos veces de HQ: %+v", res.ByDevice)
	}
}
