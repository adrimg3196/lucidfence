package playbook

import (
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// playbookValido es el playbook de referencia: el soar-rooted-outside de
// legacy/lucidfence/core/soar.py traducido a la gramática 2.0, con params
// anidados para comprobar que las copias son profundas.
func playbookValido() Playbook {
	at := time.Date(2026, 9, 6, 8, 0, 0, 0, time.UTC)
	return Playbook{
		ID:          "soar-qa",
		Name:        "No conforme fuera de geocerca",
		Description: "Bloqueo con aprobación humana y aviso al SOC",
		When: []policy.Condition{
			{Field: "compliant", Op: policy.OpEq, Value: false},
			{Field: "fence_state", Op: policy.OpEq, Value: "outside"},
			{Field: "platform", Op: policy.OpIn, Value: []string{"ios", "android"}},
		},
		Actions: []policy.Action{
			{Action: action.Lock, Params: map[string]any{"reason": "noncompliant_outside"}},
			{Action: action.Notify, Params: map[string]any{
				"channel":  "soc",
				"tags":     []string{"soc", "guardia"},
				"destinos": []any{"soc", "ciso"},
				"extra":    map[string]any{"prioridad": "alta"},
			}},
		},
		Enabled:   true,
		Severity:  risk.SeverityHigh,
		CreatedAt: at,
		UpdatedAt: at,
	}
}

// sujetoBrecha es el dispositivo dorado de
// legacy/tests/test_soar_geofence_breach.py::_device(outside=True,
// compliant=False): fuera de geocerca y no conforme.
func sujetoBrecha() policy.Subject {
	conforme := false
	score := 82.0
	d := device.Device{
		ID: "dev-1", Name: "iPad kiosco", Platform: "ios",
		Compliant: &conforme, FenceState: device.Outside, LastInsideFence: "almacen",
		RouteState: device.Unassigned,
	}
	v := device.Verdict{Score: &score, Severity: risk.SeverityCritical, Provenance: "tool", Verified: true}
	return policy.NewSubject(d, v, risk.Signals{})
}

// sujetoSinUbicacion es el dispositivo conforme que deja de reportar posición.
func sujetoSinUbicacion() policy.Subject {
	conforme := true
	d := device.Device{
		ID: "dev-7", Name: "Tablet almacén", Platform: "android",
		Compliant: &conforme, FenceState: device.Unknown, RouteState: device.Unassigned,
	}
	return policy.NewSubject(d, device.Verdict{Severity: risk.SeverityMedium}, risk.Signals{})
}

// sujetoFueraDeRuta es la furgoneta fuera de su corredor con riesgo crítico.
func sujetoFueraDeRuta() policy.Subject {
	conforme := true
	score, desvio := 91.0, 780.0
	d := device.Device{
		ID: "dev-2", Name: "Furgoneta 2", Platform: "android",
		Compliant: &conforme, FenceState: device.Inside, InsideFence: "almacen",
		RouteID: "ruta-norte", RouteState: device.OffRoute, RouteDeviationM: &desvio,
	}
	v := device.Verdict{Score: &score, Severity: risk.SeverityCritical, Provenance: "tool", Verified: true}
	return policy.NewSubject(d, v, risk.Signals{})
}

// casosInvalidos porta los errores de SOARPlaybook.validate() de 1.x
// (playbook sin id, nombre vacío, sin acciones, acción mal formada,
// condición inválida) más el formato de id y la severidad de 2.0.
var casosInvalidos = []struct {
	nombre string
	mutar  func(*Playbook)
	frags  []string
}{
	{"id ausente", func(p *Playbook) { p.ID = "" }, []string{`id ""`, "inválido"}},
	{"id con mayúsculas y espacios", func(p *Playbook) { p.ID = "SOAR Malo" }, []string{`"SOAR Malo"`, "inválido"}},
	{"nombre vacío", func(p *Playbook) { p.Name = "   " }, []string{"soar-qa", "nombre vacío"}},
	{"when vacío", func(p *Playbook) { p.When = nil }, []string{"soar-qa", "'when'"}},
	{"condición sin field", func(p *Playbook) { p.When[0].Field = "" }, []string{"soar-qa", "condición 0", "'field'"}},
	{"op desconocido", func(p *Playbook) { p.When[0].Op = policy.Op("glob") }, []string{"soar-qa", `"glob"`, "operador desconocido"}},
	{"value ausente", func(p *Playbook) { p.When[1].Value = nil }, []string{"soar-qa", "fence_state", "'value'"}},
	{"sin acciones", func(p *Playbook) { p.Actions = nil }, []string{"soar-qa", "sin acciones"}},
	{"acción fuera del catálogo", func(p *Playbook) { p.Actions[0].Action = action.Action("flag_app") }, []string{"soar-qa", `"flag_app"`, "desconocida"}},
	{"severidad inválida", func(p *Playbook) { p.Severity = "urgente" }, []string{"soar-qa", `"urgente"`, "severidad"}},
}

func TestValidateRechazaLosCasosDorados(t *testing.T) {
	for _, c := range casosInvalidos {
		p := playbookValido()
		c.mutar(&p)
		err := p.Validate()
		if err == nil {
			t.Errorf("%s: Validate() debería fallar", c.nombre)
			continue
		}
		for _, f := range c.frags {
			if !strings.Contains(err.Error(), f) {
				t.Errorf("%s: el error %q debe contener %q", c.nombre, err, f)
			}
		}
	}
}

func TestValidateAceptaElPlaybookDeReferencia(t *testing.T) {
	if err := playbookValido().Validate(); err != nil {
		t.Fatalf("el playbook de referencia debe validar: %v", err)
	}
}

func TestValidateAllExigeIdsUnicos(t *testing.T) {
	a, b := playbookValido(), playbookValido()
	b.Name = "Copia"
	err := ValidateAll([]Playbook{a, b})
	if err == nil || !strings.Contains(err.Error(), "duplicado") || !strings.Contains(err.Error(), "soar-qa") {
		t.Fatalf("ValidateAll debe reportar el id duplicado, dio: %v", err)
	}
	b.ID = "soar-qa-2"
	if err := ValidateAll([]Playbook{a, b}); err != nil {
		t.Fatalf("dos ids distintos validan: %v", err)
	}
	if err := ValidateAll(nil); err != nil {
		t.Fatalf("una lista vacía valida: %v", err)
	}
}

func TestFindByID(t *testing.T) {
	ps := []Playbook{playbookValido()}
	if p, ok := FindByID(ps, "soar-qa"); !ok || p.Name != "No conforme fuera de geocerca" {
		t.Fatalf("FindByID no encontró el playbook: %#v %v", p, ok)
	}
	if _, ok := FindByID(ps, "no-existe"); ok {
		t.Fatal("FindByID debe devolver false para un id ausente")
	}
}

func TestMatchAllAnotaLosCamposQueCasaron(t *testing.T) {
	p := playbookValido()
	got := MatchAll([]Playbook{p}, sujetoBrecha())
	if len(got) != 1 {
		t.Fatalf("MatchAll = %#v; el playbook de referencia casa con la brecha", got)
	}
	m := got[0]
	if m.PlaybookID != "soar-qa" || m.Name != p.Name || m.Severity != risk.SeverityHigh {
		t.Errorf("la coincidencia debe llevar id, nombre y severidad del playbook: %#v", m)
	}
	quiero := []string{"compliant", "fence_state", "platform"}
	if !reflect.DeepEqual(m.MatchedFields, quiero) {
		t.Errorf("MatchedFields = %#v, quiero %#v en el orden de 'when'", m.MatchedFields, quiero)
	}
	if len(m.Actions) != 2 || m.Actions[0].Action != action.Lock || m.Actions[1].Action != action.Notify {
		t.Fatalf("la coincidencia debe llevar las acciones del playbook: %#v", m.Actions)
	}
	m.Actions[0].Params["reason"] = "mutado"
	m.Actions[1].Params["tags"].([]string)[0] = "mutado"
	m.Actions[1].Params["destinos"].([]any)[0] = "mutado"
	m.Actions[1].Params["extra"].(map[string]any)["prioridad"] = "mutada"
	if p.Actions[0].Params["reason"] != "noncompliant_outside" ||
		p.Actions[1].Params["tags"].([]string)[0] != "soc" ||
		p.Actions[1].Params["destinos"].([]any)[0] != "soc" ||
		p.Actions[1].Params["extra"].(map[string]any)["prioridad"] != "alta" {
		t.Fatal("MatchAll debe devolver copias profundas de las acciones, no alias del playbook")
	}
}

func TestPlaybookDeshabilitadoNuncaCasa(t *testing.T) {
	apagado := playbookValido()
	apagado.Enabled = false
	if got := MatchAll([]Playbook{apagado}, sujetoBrecha()); got != nil {
		t.Fatalf("un playbook deshabilitado no casa nunca: %#v", got)
	}
	sinCondiciones := playbookValido()
	sinCondiciones.When = nil
	if got := MatchAll([]Playbook{sinCondiciones}, sujetoBrecha()); got != nil {
		t.Fatalf("un 'when' vacío no significa 'todos los dispositivos': %#v", got)
	}
	falla := playbookValido()
	falla.When[0].Value = true
	if got := MatchAll([]Playbook{falla}, sujetoBrecha()); got != nil {
		t.Fatalf("si una condición no se cumple no hay coincidencia: %#v", got)
	}
	if MatchAll(nil, sujetoBrecha()) != nil {
		t.Fatal("sin playbooks no hay coincidencias")
	}
}

func TestCondicionInvalidaSeDetectaEnValidateNoEnElCiclo(t *testing.T) {
	p := playbookValido()
	p.When[0].Op = policy.Op("glob")
	err := p.Validate()
	if err == nil || !strings.Contains(err.Error(), "operador desconocido") {
		t.Fatalf("Validate debe rechazar el operador de 1.x que 2.0 no porta, dio: %v", err)
	}
	if got := MatchAll([]Playbook{p}, sujetoBrecha()); got != nil {
		t.Fatalf("en el ciclo un playbook no compilable simplemente no casa: %#v", got)
	}
}

// idsDefaults fija el catálogo de fábrica portado de DEFAULT_PLAYBOOKS
// (legacy/lucidfence/core/soar.py) a la gramática 2.0.
var idsDefaults = []string{
	"soar-noncompliant-outside",
	"soar-locate-unknown",
	"soar-offroute-critical",
}

func TestDefaultsValidanYUsanElEnumDeAcciones(t *testing.T) {
	ps := Defaults()
	if len(ps) != len(idsDefaults) {
		t.Fatalf("Defaults() devolvió %d playbooks, quiero %d", len(ps), len(idsDefaults))
	}
	if err := ValidateAll(ps); err != nil {
		t.Fatalf("todo playbook de fábrica debe validar: %v", err)
	}
	for i, p := range ps {
		if p.ID != idsDefaults[i] {
			t.Errorf("playbook #%d = %q, quiero %q", i, p.ID, idsDefaults[i])
		}
		if !p.Enabled || p.Description == "" {
			t.Errorf("%s: playbook de fábrica incompleto: %#v", p.ID, p)
		}
		if !p.CreatedAt.IsZero() || !p.UpdatedAt.IsZero() {
			t.Errorf("%s: las marcas de tiempo las sella quien persiste, no el catálogo", p.ID)
		}
		for _, a := range p.Actions {
			if _, err := action.Parse(string(a.Action)); err != nil {
				t.Errorf("%s: %v", p.ID, err)
			}
		}
	}
}

func TestDefaultsCasanConSusSujetos(t *testing.T) {
	casos := []struct {
		nombre   string
		sujeto   policy.Subject
		quiero   string
		acciones []action.Action
	}{
		{"brecha de geocerca", sujetoBrecha(), "soar-noncompliant-outside", []action.Action{action.Lock, action.Notify}},
		{"ubicación perdida", sujetoSinUbicacion(), "soar-locate-unknown", []action.Action{action.Locate, action.Notify}},
		{"fuera de ruta crítico", sujetoFueraDeRuta(), "soar-offroute-critical", []action.Action{action.Notify}},
	}
	for _, c := range casos {
		got := MatchAll(Defaults(), c.sujeto)
		if len(got) != 1 || got[0].PlaybookID != c.quiero {
			t.Errorf("%s: casaron %#v, quiero solo %q", c.nombre, got, c.quiero)
			continue
		}
		if len(got[0].Actions) != len(c.acciones) {
			t.Errorf("%s: %d acciones, quiero %d", c.nombre, len(got[0].Actions), len(c.acciones))
			continue
		}
		for i, a := range c.acciones {
			if got[0].Actions[i].Action != a {
				t.Errorf("%s: acción #%d = %q, quiero %q", c.nombre, i, got[0].Actions[i].Action, a)
			}
		}
	}
}

func TestDentroYConformeNoDisparaNingunPlaybook(t *testing.T) {
	conforme := true
	d := device.Device{
		ID: "dev-3", Name: "Portátil dirección", Platform: "macos",
		Compliant: &conforme, FenceState: device.Inside, InsideFence: "oficina",
		RouteState: device.Unassigned,
	}
	s := policy.NewSubject(d, device.Verdict{Severity: risk.SeverityLow}, risk.Signals{})
	if got := MatchAll(Defaults(), s); got != nil {
		t.Fatalf("falso positivo dentro y conforme: %#v", got)
	}
}

func TestDefaultsDevuelveValoresIndependientes(t *testing.T) {
	a := Defaults()
	a[0].Name = "mutado"
	a[0].When[0].Value = true
	a[0].Actions[0].Params["reason"] = "mutado"
	b := Defaults()
	if b[0].Name == "mutado" || b[0].When[0].Value == true || b[0].Actions[0].Params["reason"] == "mutado" {
		t.Fatalf("cada llamada a Defaults() debe construir valores nuevos: %#v", b[0])
	}
}
