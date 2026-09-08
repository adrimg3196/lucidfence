package policy_test

import (
	"encoding/json"
	"os"
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/google/go-cmp/cmp"
)

func TestLasCincoPlantillasValidanYSeMarcan(t *testing.T) {
	ps := policy.Templates()
	if len(ps) != 5 {
		t.Fatalf("plantillas=%d", len(ps))
	}
	if err := policy.ValidateAll(ps); err != nil {
		t.Fatal(err)
	}
	for _, p := range ps {
		if !strings.HasPrefix(p.ID, "tpl-") || p.TemplateID != p.ID || p.Source != "template" || !p.Enabled {
			t.Fatal(p)
		}
	}
	data, err := os.ReadFile("testdata/templates.json")
	if err != nil {
		t.Fatal(err)
	}
	var wants []policy.Policy
	if err := json.Unmarshal(data, &wants); err != nil {
		t.Fatal(err)
	}
	for i, p := range ps {
		// Solo se omite copy editorial/metadatos; condiciones, params y orden son contractuales.
		got := policy.Policy{ID: p.ID, Severity: p.Severity, When: p.When, Actions: p.Actions}
		raw, err := json.Marshal(got)
		if err != nil {
			t.Fatal(err)
		}
		var normalized policy.Policy
		if err := json.Unmarshal(raw, &normalized); err != nil {
			t.Fatal(err)
		}
		if diff := cmp.Diff(wants[i], normalized); diff != "" {
			t.Fatal(diff)
		}
	}
}

func templateSubjects() []policy.Subject {
	return []policy.Subject{
		{Signals: risk.Signals{"route_state": {"route_state": "off_route"}}},
		{Device: device.Device{FenceState: device.Outside}, Signals: risk.Signals{"device_health": {"rooted": true}}},
		{Signals: risk.Signals{"route_state": {"route_state": "off_route", "route_deviation_m": 501.0}}},
		{Device: device.Device{FenceState: device.Outside}, Signals: risk.Signals{"shift_match": {"shift_known": true, "shift_match": false}}},
		{Device: device.Device{FenceState: device.Unknown, Compliant: ptr(false)}},
	}
}

func TestCadaPlantillaCasaConSuSujeto(t *testing.T) {
	ps := policy.Templates()
	subjects := templateSubjects()
	if len(ps) != len(subjects) {
		t.Fatal("catálogo ausente")
	}
	for i, p := range ps {
		if !p.Matches(subjects[i]) {
			t.Fatal(p.ID)
		}
		if p.Matches(policy.Subject{}) {
			t.Fatal("sujeto sin evidencia", p.ID)
		}
		for j := range p.When {
			negative := p
			negative.When = append([]policy.Condition{}, p.When...)
			negative.When[j].Value = "no-coincide"
			if negative.Matches(subjects[i]) {
				t.Fatal("AND incompleto", p.ID, j)
			}
		}
	}
}

func TestUmbralDeDesviacionYAccionesDeLasPlantillas(t *testing.T) {
	p, ok := policy.TemplateByID("tpl-ciso-deviation-500")
	if !ok {
		t.Fatal("ausente")
	}
	for _, n := range []float64{499.9, 500, 500.1} {
		s := policy.Subject{Signals: risk.Signals{"route_state": {"route_state": "off_route", "route_deviation_m": n}}}
		if p.Matches(s) != (n > 500) {
			t.Fatal(n)
		}
		s.Signals["route_state"]["route_state"] = "on_route"
		if p.Matches(s) {
			t.Fatal("desvío sin off_route")
		}
	}
}

func TestTurnoConocidoExigeDesajusteExplicito(t *testing.T) {
	p, ok := policy.TemplateByID("tpl-isolate-offshift-outside")
	if !ok {
		t.Fatal("ausente")
	}
	for _, match := range []any{nil, (*bool)(nil), true, "false", 0, false} {
		for _, known := range []any{nil, false, true, "true"} {
			signals := risk.Signals{"shift_match": {"shift_known": known, "shift_match": match}}
			raw, err := json.Marshal(signals)
			if err != nil {
				t.Fatal(err)
			}
			var restored risk.Signals
			if err := json.Unmarshal(raw, &restored); err != nil {
				t.Fatal(err)
			}
			for _, sig := range []risk.Signals{signals, restored} {
				s := policy.Subject{Device: device.Device{FenceState: device.Outside}, Signals: sig}
				want := known == true && match == false
				if p.Matches(s) != want {
					t.Fatalf("known=%v match=%v", known, match)
				}
			}
		}
	}
	s := policy.Subject{Device: device.Device{FenceState: device.Outside}, Signals: risk.Signals{"shift_match": {"shift_known": true}}}
	if p.Matches(s) {
		t.Fatal("match ausente")
	}
}

func TestTemplateByIDDevuelveCopia(t *testing.T) {
	ps := policy.Templates()
	if len(ps) != 5 {
		t.Fatal("catálogo")
	}
	original, err := json.Marshal(ps)
	if err != nil {
		t.Fatal(err)
	}
	p, ok := policy.TemplateByID(ps[0].ID)
	if !ok {
		t.Fatal("ausente")
	}
	p.When[0].Value = "mutado"
	p.Actions[0].Params["msg"] = "mutado"
	ps[0].When[0].Field = "mutado"
	ps[0].Actions[0].Params["extra"] = map[string]any{"list": []any{"a"}}
	after, err := json.Marshal(policy.Templates())
	if err != nil {
		t.Fatal(err)
	}
	if string(original) != string(after) {
		t.Fatal("catálogo comparte estado")
	}
	if _, ok := policy.TemplateByID("missing"); ok {
		t.Fatal("inventado")
	}
}
