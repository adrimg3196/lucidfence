package engine

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// riesgoDeLaFlota corre un ciclo sobre la fixture demo y devuelve las
// estadísticas y los dispositivos ya persistidos, indexados por id: leer de
// devices.json y no de memoria comprueba de paso el round-trip por JSON.
func riesgoDeLaFlota(t *testing.T, e *Engine, org *store.OrgStore) (CycleStats, map[string]device.Device) {
	t.Helper()
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	ds, err := org.Devices()
	if err != nil {
		t.Fatal(err)
	}
	return st, device.Index(ds)
}

// tieneRazon busca una razón por prefijo: las que llevan magnitudes
// (velocidad, desviación, zona) traen el número dentro del texto.
func tieneRazon(reasons []string, prefix string) bool {
	for _, r := range reasons {
		if strings.HasPrefix(r, prefix) {
			return true
		}
	}
	return false
}

// TestCicloEvaluaElRiesgoDeTodaLaFlota es el caso dorado del hito: un solo
// ciclo sobre la flota demo deja los seis dispositivos con veredicto, con sus
// siete señales y con el reparto por severidad en las estadísticas.
func TestCicloEvaluaElRiesgoDeTodaLaFlota(t *testing.T) {
	e, org := newEngine(t)
	st, idx := riesgoDeLaFlota(t, e, org)

	t.Run("flota evaluada", func(t *testing.T) { assertFlotaEvaluada(t, st, idx) })
	t.Run("sano en cero", func(t *testing.T) { assertSanoEnCero(t, idx["dev-001"]) })
	t.Run("fuera y no conforme", func(t *testing.T) { assertFueraYNoConforme(t, idx["dev-004"]) })
	t.Run("reparto por severidad", func(t *testing.T) { assertRepartoPorSeveridad(t, st) })
}

func assertFlotaEvaluada(t *testing.T, st CycleStats, idx map[string]device.Device) {
	t.Helper()
	if st.RiskEvaluated != 6 || st.RiskFailed != 0 {
		t.Fatalf("los seis dispositivos deben quedar evaluados: %+v", st)
	}
	for id, d := range idx {
		if d.Risk.Score == nil || d.Risk.EvaluatedAt == nil {
			t.Fatalf("%s sin veredicto: %+v", id, d.Risk)
		}
		if len(d.Signals) != len(risk.Names) {
			t.Fatalf("%s debe publicar las %d señales: %v", id, len(risk.Names), d.Signals)
		}
		for _, name := range risk.Names {
			if _, ok := d.Signals[name]; !ok {
				t.Fatalf("%s sin la señal %q", id, name)
			}
		}
	}
}

func assertSanoEnCero(t *testing.T, d device.Device) {
	t.Helper()
	if d.Risk.Score == nil || *d.Risk.Score != 0 || d.Risk.Severity != risk.SeverityLow {
		t.Fatalf("dev-001 está dentro, es conforme y va cifrado: %+v", d.Risk)
	}
	if len(d.Risk.Reasons) != 0 || d.Risk.Provenance != "none" || d.Risk.Verified {
		t.Fatalf("sin hallazgos no hay razones ni evidencia que verificar: %+v", d.Risk)
	}
}

func assertFueraYNoConforme(t *testing.T, d device.Device) {
	t.Helper()
	// 35 (fuera) + 25 (no conforme) + 15 (root) + 10 (SO desactualizado) +
	// 15 (sin cifrar) + 8 (osquery inválido) + 20 (fuera de su turno) = 128,
	// acotado a 100 por risk.Evaluate.
	if d.Risk.Score == nil || *d.Risk.Score != 100 {
		t.Fatalf("dev-004 satura el score: %+v", d.Risk)
	}
	if d.Risk.Severity != risk.SeverityCritical {
		t.Fatalf("severidad esperada critical: %+v", d.Risk)
	}
	if d.Risk.Provenance != "tool" || !d.Risk.Verified {
		t.Fatalf("un veredicto con hallazgos viene de las señales: %+v", d.Risk)
	}
	for _, want := range []string{"fuera de geocerca permitida", "dispositivo no conforme", "almacenamiento sin cifrar",
		"dispositivo con root/jailbreak", "SO desactualizado", "configuración de osquery no válida",
		"dispositivo fuera de su turno asignado"} {
		if !tieneRazon(d.Risk.Reasons, want) {
			t.Fatalf("falta la razón %q en %v", want, d.Risk.Reasons)
		}
	}
	// La postura y el turno llegan de la seed y de los ajustes sembrados, no
	// de un default neutro: sin ellos estas tres claves serían siempre falsas.
	if rooted, ok := d.Signals["device_health"]["rooted"].(bool); !ok || !rooted {
		t.Fatalf("la postura observada debe llegar a las señales: %v", d.Signals["device_health"])
	}
	if inval, ok := d.Signals["device_posture"]["osquery_config_invalid"].(bool); !ok || !inval {
		t.Fatalf("osquery inválido es una observación: %v", d.Signals["device_posture"])
	}
	if match, ok := d.Signals["shift_match"]["shift_match"].(bool); !ok || match {
		t.Fatalf("dev-004 tiene turno en demo-hq y está fuera: %v", d.Signals["shift_match"])
	}
}

func assertRepartoPorSeveridad(t *testing.T, st CycleStats) {
	t.Helper()
	// dev-001 y dev-006 en 0, dev-003 en 10 (Lockdown Mode), dev-005 en 22
	// (Android 12 sin parchear mas el riesgo de la zona del almacén),
	// dev-002 en 30 (fuera menos crédito de ruta) y dev-004 saturado en 100
	// (fuera, no conforme, sin cifrar, con root, con el SO desactualizado,
	// con osquery inválido y fuera de su turno).
	want := map[string]int{risk.SeverityLow: 4, risk.SeverityMedium: 1, risk.SeverityCritical: 1}
	if len(st.BySeverity) != len(want) {
		t.Fatalf("by_severity: %v", st.BySeverity)
	}
	for sev, n := range want {
		if st.BySeverity[sev] != n {
			t.Fatalf("by_severity[%s] = %d, esperado %d (%v)", sev, st.BySeverity[sev], n, st.BySeverity)
		}
	}
}

// TestLosAjustesDeRiesgoLleganAlVeredicto: lo que el operador configura en
// settings.json (turnos, riesgo de zona y jornada) tiene que verse en el
// veredicto del ciclo siguiente, sin reiniciar el motor.
func TestLosAjustesDeRiesgoLleganAlVeredicto(t *testing.T) {
	e, org := newEngine(t)
	set, err := org.Settings()
	if err != nil {
		t.Fatal(err)
	}
	// La asignación sustituye entero el contexto que sembró SeedDemo: lo que
	// se comprueba es que manda el fichero, no la siembra.
	set.Risk = settings.Risk{
		ShiftZones:    map[string]string{"dev-004": "demo-hq"},
		ZoneRisk:      map[string]float64{"demo-hq": 0.5},
		OffHoursStart: 8,
		OffHoursEnd:   20,
	}
	if err := org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	_, idx := riesgoDeLaFlota(t, e, org)

	dentro := idx["dev-001"]
	if dentro.Risk.Score == nil || *dentro.Risk.Score != 20 {
		t.Fatalf("dev-001: 10 de jornada mas 10 de zona (0,5 x 20): %+v", dentro.Risk)
	}
	if !tieneRazon(dentro.Risk.Reasons, "fuera de horario laboral") ||
		!tieneRazon(dentro.Risk.Reasons, "zona de riesgo elevado (0.5)") {
		t.Fatalf("las dos razones del contexto deben aparecer: %v", dentro.Risk.Reasons)
	}

	fuera := idx["dev-004"]
	if !tieneRazon(fuera.Risk.Reasons, "dispositivo fuera de su turno asignado") {
		t.Fatalf("dev-004 tiene turno en demo-hq y está fuera: %v", fuera.Risk.Reasons)
	}
	if fuera.Risk.Severity != risk.SeverityCritical {
		t.Fatalf("35+25+15+10+15+8+10+20 = 138, acotado a 100: %+v", fuera.Risk)
	}
	if match, ok := fuera.Signals["shift_match"]["shift_match"].(bool); !ok || match {
		t.Fatalf("la señal de turno viaja con el dispositivo: %v", fuera.Signals["shift_match"])
	}
}

// TestAjustesIlegiblesEvaluanConLaJornadaDeFabrica: un settings.json corrupto
// no puede dejar la flota sin evaluar ni inventar una jornada.
func TestAjustesIlegiblesEvaluanConLaJornadaDeFabrica(t *testing.T) {
	e, org := newEngine(t)
	if err := os.WriteFile(org.Path("settings.json"), []byte("{no es json"), 0o600); err != nil {
		t.Fatal(err)
	}
	st, idx := riesgoDeLaFlota(t, e, org)
	if st.RiskEvaluated != 6 || st.RiskFailed != 0 {
		t.Fatalf("unos ajustes ilegibles no dejan la flota sin evaluar: %+v", st)
	}
	if d := idx["dev-001"]; d.Risk.Score == nil || *d.Risk.Score != 0 {
		t.Fatalf("a las 12:00 la jornada de fábrica (20-7) no es fuera de horario: %+v", d.Risk)
	}
}

// TestPoliticasIlegiblesDetienenElCiclo: al revés que los ajustes, unas
// políticas ilegibles no tienen lectura segura. El ciclo falla nombrando el
// fichero en vez de dejar de automatizar en silencio.
func TestPoliticasIlegiblesDetienenElCiclo(t *testing.T) {
	e, org := newEngine(t)
	if err := os.WriteFile(org.Path("policies.json"), []byte("{no es json"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := e.RunOnce(context.Background())
	if err == nil || !strings.Contains(err.Error(), "policies.json") {
		t.Fatalf("el ciclo debe fallar nombrando el fichero: %v", err)
	}
	if e.Status().Cycles != 0 || !strings.Contains(e.Status().LastError, "policies.json") {
		t.Fatalf("el fallo debe quedar visible en el estado: %+v", e.Status())
	}
}

// TestPanicoDejaVeredictoFallidoNoUnCeroLow es el caso dorado de
// legacy/tests/test_risk_silent_failure.py: un evaluador que revienta jamás
// puede presentarse como un dispositivo sano.
func TestPanicoDejaVeredictoFallidoNoUnCeroLow(t *testing.T) {
	e, org := newEngine(t)
	e.evalHook = func(d *device.Device) {
		if d.ID == "dev-004" {
			panic("boom: el proveedor de señales reventó")
		}
	}
	st, idx := riesgoDeLaFlota(t, e, org)
	if st.RiskFailed != 1 || st.RiskEvaluated != 5 || st.EvaluationErrors != 1 {
		t.Fatalf("un dispositivo roto se cuenta aparte: %+v", st)
	}
	if st.BySeverity[risk.SeverityUnknown] != 1 || st.BySeverity[risk.SeverityLow] != 4 {
		t.Fatalf("lo desconocido no se suma a low: %v", st.BySeverity)
	}
	assertVeredictoFallido(t, idx["dev-004"])
	if sano := idx["dev-001"]; sano.Risk.Score == nil || *sano.Risk.Score != 0 {
		t.Fatalf("el resto de la flota se evalúa igual: %+v", sano.Risk)
	}
}

// assertVeredictoFallido comprueba lo único honesto que se puede decir de un
// dispositivo cuya evaluación reventó: sin score, sin señales y con el motivo.
func assertVeredictoFallido(t *testing.T, roto device.Device) {
	t.Helper()
	if roto.Risk.Score != nil || roto.Risk.Severity != risk.SeverityUnknown {
		t.Fatalf("un evaluador que revienta jamás da 0/low: %+v", roto.Risk)
	}
	if len(roto.Risk.Reasons) != 1 || !tieneRazon(roto.Risk.Reasons, "no se pudo evaluar el riesgo: ") {
		t.Fatalf("la razón debe explicar el fallo: %v", roto.Risk.Reasons)
	}
	if roto.Risk.Provenance != "none" || roto.Risk.Verified || roto.EvaluationError == "" {
		t.Fatalf("sin evidencia y con el error a la vista: %+v", roto)
	}
	if len(roto.Signals) != 0 {
		t.Fatalf("una evaluación fallida no publica señales: %v", roto.Signals)
	}
}

// TestCountRiskCreaElMapaSiFalta cubre la guarda de countRisk para un
// CycleStats construido a mano (el ciclo siempre trae el mapa hecho).
func TestCountRiskCreaElMapaSiFalta(t *testing.T) {
	st := CycleStats{}
	score := 12.0
	countRisk(&st, device.Device{Risk: device.Verdict{Score: &score, Severity: risk.SeverityLow}})
	countRisk(&st, device.Device{Risk: device.Verdict{}})
	if st.RiskEvaluated != 1 || st.RiskFailed != 1 {
		t.Fatalf("un veredicto sin score cuenta como fallido: %+v", st)
	}
	if st.BySeverity[risk.SeverityLow] != 1 || st.BySeverity[risk.SeverityUnknown] != 1 {
		t.Fatalf("una severidad vacía se publica como unknown: %v", st.BySeverity)
	}
}
