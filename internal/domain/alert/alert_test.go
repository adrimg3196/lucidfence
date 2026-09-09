package alert

import (
	"errors"
	"math"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

var t0 = time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)

func boolPtr(v bool) *bool      { return &v }
func intPtr(v int) *int         { return &v }
func f64Ptr(v float64) *float64 { return &v }

func rule(id string, k Kind, threshold float64) Rule {
	return Rule{
		ID: id, Name: "Regla " + id, Kind: k, Threshold: threshold,
		Severity: "high", Enabled: true, CreatedAt: t0, UpdatedAt: t0,
	}
}

func base() device.Device {
	return device.Device{ID: "dev-1", Name: "Tablet", Platform: "android", FenceState: device.Inside, LastReportAt: t0}
}

func TestEvaluateLosSeisTiposJustoEnElUmbral(t *testing.T) {
	outBelow, outAbove := base(), base()
	outBelow.FenceState, outBelow.DwellSeconds = device.Outside, 540
	outAbove.FenceState, outAbove.DwellSeconds = device.Outside, 600

	riskBelow, riskAbove := base(), base()
	riskBelow.Risk.Score, riskAbove.Risk.Score = f64Ptr(79.9), f64Ptr(80)

	compBelow, compAbove := base(), base()
	compBelow.Compliant, compAbove.Compliant = boolPtr(true), boolPtr(false)

	batBelow, batAbove := base(), base()
	batBelow.Inventory.BatteryLevel, batAbove.Inventory.BatteryLevel = intPtr(20), intPtr(19)

	stoBelow, stoAbove := base(), base()
	stoBelow.Inventory.StorageFreeGB, stoAbove.Inventory.StorageFreeGB = f64Ptr(5), f64Ptr(4.5)

	staleBelow, staleAbove := base(), base()
	staleBelow.LastReportAt = t0.Add(-29 * time.Minute)
	staleAbove.LastReportAt = t0.Add(-30 * time.Minute)

	cases := []struct {
		rule   Rule
		below  device.Device
		above  device.Device
		value  float64
		reason string
	}{
		{rule("r-fuera", KindOutsideDuration, 10), outBelow, outAbove, 10, "fuera de geocerca 10 min (umbral 10 min)"},
		{rule("r-riesgo", KindRiskAbove, 80), riskBelow, riskAbove, 80, "riesgo 80 (umbral 80)"},
		{rule("r-cumplimiento", KindNonCompliant, 0), compBelow, compAbove, 1, "el dispositivo no cumple la política UEM"},
		{rule("r-bateria", KindBatteryBelow, 20), batBelow, batAbove, 19, "batería 19 % (umbral < 20 %)"},
		{rule("r-almacen", KindStorageLow, 5), stoBelow, stoAbove, 4.5, "almacenamiento libre 4.5 GB (umbral < 5 GB)"},
		{rule("r-checkin", KindStaleCheckin, 30), staleBelow, staleAbove, 30, "sin reportar desde hace 30 min (umbral 30 min)"},
	}
	for _, c := range cases {
		t.Run(string(c.rule.Kind), func(t *testing.T) {
			if got := Evaluate([]Rule{c.rule}, []device.Device{c.below}, t0); len(got) != 0 {
				t.Fatalf("por debajo del umbral no dispara: %+v", got)
			}
			got := Evaluate([]Rule{c.rule}, []device.Device{c.above}, t0)
			if len(got) != 1 {
				t.Fatalf("en el umbral dispara una vez: %+v", got)
			}
			f := got[0]
			if f.Value != c.value || f.Reason != c.reason {
				t.Fatalf("valor %v motivo %q", f.Value, f.Reason)
			}
			if f.RuleID != c.rule.ID || f.RuleName != c.rule.Name || f.Kind != c.rule.Kind {
				t.Fatalf("identidad de la regla: %+v", f)
			}
			if f.DeviceID != "dev-1" || f.DeviceName != "Tablet" || f.Severity != "high" || !f.At.Equal(t0) {
				t.Fatalf("disparo: %+v", f)
			}
		})
	}
}

func TestEvaluateReglaDeshabilitadaNoDispara(t *testing.T) {
	r := rule("r-cumplimiento", KindNonCompliant, 0)
	r.Enabled = false
	d := base()
	d.Compliant = boolPtr(false)
	if got := Evaluate([]Rule{r}, []device.Device{d}, t0); len(got) != 0 {
		t.Fatalf("una regla deshabilitada ni se evalúa: %+v", got)
	}
}

func TestEvaluateLoDesconocidoNoDispara(t *testing.T) {
	d := base()
	d.FenceState, d.DwellSeconds = device.Outside, 3600
	d.LastReportAt = time.Time{}
	rules := []Rule{
		rule("r-riesgo", KindRiskAbove, 0),
		rule("r-cumplimiento", KindNonCompliant, 0),
		rule("r-bateria", KindBatteryBelow, 100),
		rule("r-almacen", KindStorageLow, 100),
		rule("r-checkin", KindStaleCheckin, 0),
	}
	if got := Evaluate(rules, []device.Device{d}, t0); len(got) != 0 {
		t.Fatalf("score nil, compliant nil, inventario nil y sin reporte: nada dispara: %+v", got)
	}
}

func TestEvaluateOrdenDeterministaConVariosDispositivos(t *testing.T) {
	d1, d2 := base(), base()
	d2.ID, d2.Name = "dev-2", "Portátil"
	d1.Compliant, d2.Compliant = boolPtr(false), boolPtr(false)
	d1.Risk.Score, d2.Risk.Score = f64Ptr(90), f64Ptr(90)

	rules := []Rule{rule("r-riesgo", KindRiskAbove, 80), rule("r-cumplimiento", KindNonCompliant, 0)}
	got := Evaluate(rules, []device.Device{d1, d2}, t0)
	if len(got) != 4 {
		t.Fatalf("dos reglas por dos dispositivos: %+v", got)
	}
	want := []string{"r-riesgo:dev-1", "r-riesgo:dev-2", "r-cumplimiento:dev-1", "r-cumplimiento:dev-2"}
	for i, w := range want {
		if key := got[i].RuleID + ":" + got[i].DeviceID; key != w {
			t.Fatalf("orden %d: %s want %s", i, key, w)
		}
	}
}

func TestEvaluateIgnoraTipoSinMedidorYDispositivoSinId(t *testing.T) {
	d := base()
	d.Compliant = boolPtr(false)
	if got := Evaluate([]Rule{rule("r-x", Kind("cosa"), 1)}, []device.Device{d}, t0); len(got) != 0 {
		t.Fatalf("un tipo sin medidor no dispara: %+v", got)
	}
	anon := base()
	anon.ID, anon.Compliant = "", boolPtr(false)
	if got := Evaluate([]Rule{rule("r-c", KindNonCompliant, 0)}, []device.Device{anon}, t0); len(got) != 0 {
		t.Fatalf("un dispositivo sin id no se puede alertar: %+v", got)
	}
}

func TestEvaluateUsaElIdCuandoNoHayNombre(t *testing.T) {
	d := base()
	d.Name, d.Compliant = "", boolPtr(false)
	got := Evaluate([]Rule{rule("r-c", KindNonCompliant, 0)}, []device.Device{d}, t0)
	if len(got) != 1 || got[0].DeviceName != "dev-1" {
		t.Fatalf("sin nombre se muestra el id: %+v", got)
	}
}

func TestValidateRechazaTipoSeveridadYUmbral(t *testing.T) {
	ok := rule("r-riesgo", KindRiskAbove, 80)
	if err := ok.Validate(); err != nil {
		t.Fatal(err)
	}

	bad := ok
	bad.Kind = "cosa"
	if err := bad.Validate(); !errors.Is(err, ErrKind) {
		t.Fatalf("tipo desconocido: %v", err)
	}

	bad = ok
	bad.Threshold = -1
	if err := bad.Validate(); !errors.Is(err, ErrThreshold) {
		t.Fatalf("umbral negativo: %v", err)
	}

	bad = ok
	bad.Threshold = math.NaN()
	if err := bad.Validate(); !errors.Is(err, ErrThreshold) {
		t.Fatalf("umbral NaN: %v", err)
	}

	bad = ok
	bad.Threshold = 101
	if err := bad.Validate(); !errors.Is(err, ErrThreshold) {
		t.Fatalf("un riesgo por encima de 100 no dispararía jamás: %v", err)
	}

	bad = ok
	bad.Kind, bad.Threshold = KindStorageLow, 512
	if err := bad.Validate(); err != nil {
		t.Fatalf("512 GB libres es un umbral legítimo: %v", err)
	}

	bad = ok
	bad.Severity = "urgente"
	if err := bad.Validate(); err == nil {
		t.Fatal("severidad fuera del catálogo de risk")
	}

	bad = ok
	bad.ID = "Regla 1"
	if err := bad.Validate(); err == nil {
		t.Fatal("id con espacios y mayúsculas")
	}

	bad = ok
	bad.Name = "   "
	if err := bad.Validate(); err == nil {
		t.Fatal("nombre vacío")
	}
}

func TestValidateAllYFindByID(t *testing.T) {
	rs := []Rule{rule("r-a", KindRiskAbove, 80), rule("r-b", KindNonCompliant, 0)}
	if err := ValidateAll(rs); err != nil {
		t.Fatal(err)
	}
	if err := ValidateAll(append(rs, rule("r-a", KindStorageLow, 5))); err == nil {
		t.Fatal("id duplicado")
	}
	if got, ok := FindByID(rs, "r-b"); !ok || got.Kind != KindNonCompliant {
		t.Fatalf("FindByID: %+v", got)
	}
	if _, ok := FindByID(rs, "r-z"); ok {
		t.Fatal("id inexistente")
	}
}

func TestKindsCubreTodosLosMedidores(t *testing.T) {
	if len(Kinds) != len(measures) {
		t.Fatalf("%d tipos declarados y %d medidores", len(Kinds), len(measures))
	}
	for _, k := range Kinds {
		if _, ok := measures[k]; !ok {
			t.Fatalf("el tipo %s no tiene medidor", k)
		}
	}
}
