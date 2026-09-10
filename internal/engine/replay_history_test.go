package engine

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
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
