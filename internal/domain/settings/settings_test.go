package settings

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

func TestDefaultEsObserveYNoPermiteWipe(t *testing.T) {
	d := Default()
	if d.Enforcement.Mode != ModeObserve {
		t.Fatalf("modo de fábrica: %q, quería %q", d.Enforcement.Mode, ModeObserve)
	}
	if len(d.Enforcement.LiveActions) != 0 {
		t.Fatalf("live_actions de fábrica debe estar vacío: %v", d.Enforcement.LiveActions)
	}
	if d.Enforcement.AllowWipe {
		t.Fatal("allow_wipe de fábrica debe ser false")
	}
	if d.Enforcement.ActionCooldownSeconds != 3600 {
		t.Fatalf("cooldown de fábrica: %d, quería 3600 (el de 1.x)", d.Enforcement.ActionCooldownSeconds)
	}
	if d.Risk.OffHoursStart != 20 || d.Risk.OffHoursEnd != 7 {
		t.Fatalf("off-hours de fábrica: %d-%d, quería 20-7", d.Risk.OffHoursStart, d.Risk.OffHoursEnd)
	}
	if d.Webhook.Enabled || d.Ntfy.Enabled {
		t.Fatal("ningún canal de salida está activo de fábrica")
	}
	if d.SchemaVersion != SchemaVersion {
		t.Fatalf("schema_version: %d", d.SchemaVersion)
	}
	if err := d.Validate(); err != nil {
		t.Fatalf("los ajustes de fábrica deben validar: %v", err)
	}
}

func TestDefaultDevuelveValoresIndependientes(t *testing.T) {
	a, b := Default(), Default()
	a.Enforcement.LiveActions = append(a.Enforcement.LiveActions, action.Lock)
	a.Enforcement.WipeAllowlist = append(a.Enforcement.WipeAllowlist, "dev-1")
	a.Egress.Hosts = append(a.Egress.Hosts, "siem.example.com")
	a.Webhook.Events[0] = "manipulado"
	a.Risk.ZoneRisk["z"] = 1
	a.Risk.ShiftZones["dev-1"] = "demo-hq"
	if len(b.Enforcement.LiveActions) != 0 || len(b.Enforcement.WipeAllowlist) != 0 || len(b.Egress.Hosts) != 0 {
		t.Fatal("Default comparte slices entre llamadas")
	}
	if b.Webhook.Events[0] != WebhookEvents[0] || len(b.Risk.ZoneRisk) != 0 || len(b.Risk.ShiftZones) != 0 {
		t.Fatal("Default comparte el catálogo de eventos o los mapas de riesgo")
	}
	if WebhookEvents[0] != "incident.opened" {
		t.Fatalf("el catálogo global quedó manipulado: %v", WebhookEvents)
	}
}

func TestValidateNombraElCampoQueFalla(t *testing.T) {
	cases := []struct {
		nombre string
		mutar  func(*Settings)
		campo  string
	}{
		{"modo desconocido", func(s *Settings) { s.Enforcement.Mode = "paranoico" }, "enforcement.mode"},
		{"formato desconocido", func(s *Settings) { s.Webhook.Format = "cef" }, "webhook.format"},
		{"evento inventado", func(s *Settings) { s.Webhook.Events = []string{"incident.opened", "device.exploded"} }, "webhook.events[1]"},
		{"cooldown negativo", func(s *Settings) { s.Enforcement.ActionCooldownSeconds = -1 }, "enforcement.action_cooldown_seconds"},
		{"acción inventada", func(s *Settings) { s.Enforcement.LiveActions = []action.Action{action.Lock, "autodestruir"} }, "enforcement.live_actions[1]"},
		{"off_hours_start fuera de rango", func(s *Settings) { s.Risk.OffHoursStart = 24 }, "risk.off_hours_start"},
		{"off_hours_end negativo", func(s *Settings) { s.Risk.OffHoursEnd = -1 }, "risk.off_hours_end"},
		{"riesgo de zona fuera de [0,1]", func(s *Settings) { s.Risk.ZoneRisk = map[string]float64{"demo-hq": 1.5} }, "risk.zone_risk"},
		{"host con esquema", func(s *Settings) { s.Egress.Hosts = []string{"https://siem.example.com"} }, "egress.hosts[0]"},
		{"id vacío en la allowlist de wipe", func(s *Settings) { s.Enforcement.WipeAllowlist = []string{"  "} }, "enforcement.wipe_allowlist[0]"},
	}
	for _, c := range cases {
		t.Run(c.nombre, func(t *testing.T) {
			s := Default()
			c.mutar(&s)
			err := s.Validate()
			if err == nil {
				t.Fatalf("%s debería fallar", c.nombre)
			}
			if !strings.Contains(err.Error(), c.campo) {
				t.Fatalf("el error debe nombrar %q: %v", c.campo, err)
			}
		})
	}
}

func TestWebhookActivoExigeURLHTTPYAlMenosUnEvento(t *testing.T) {
	s := Default()
	s.Webhook.Enabled = true
	s.Webhook.URL = ""
	if err := s.Validate(); err == nil || !strings.Contains(err.Error(), "webhook.url") {
		t.Fatalf("URL vacía con el canal activo: %v", err)
	}
	s.Webhook.URL = "ftp://siem.example.com/hec"
	if err := s.Validate(); err == nil || !strings.Contains(err.Error(), "webhook.url") {
		t.Fatalf("esquema no http(s): %v", err)
	}
	s.Webhook.URL = "https://siem.example.com/hec"
	s.Webhook.Events = []string{}
	if err := s.Validate(); err == nil || !strings.Contains(err.Error(), "webhook.events") {
		t.Fatalf("sin eventos: %v", err)
	}
	s.Webhook.Events = []string{"incident.opened"}
	if err := s.Validate(); err != nil {
		t.Fatalf("webhook válido: %v", err)
	}
}

func TestCanalDeshabilitadoNoValidaSuURL(t *testing.T) {
	s := Default()
	s.Ntfy = Ntfy{URL: "esto no es una url", Enabled: false}
	s.Webhook.URL = "tampoco"
	if err := s.Validate(); err != nil {
		t.Fatalf("un canal apagado no obliga a nada: %v", err)
	}
	s.Ntfy.Enabled = true
	if err := s.Validate(); err == nil || !strings.Contains(err.Error(), "ntfy.url") {
		t.Fatalf("al encenderlo sí: %v", err)
	}
}

func TestNormalizedRellenaVaciosYLimpiaHosts(t *testing.T) {
	s := Settings{Egress: Egress{Hosts: []string{" SIEM.Example.com ", "siem.example.com", "", "ntfy.sh"}}}
	n := s.Normalized()
	if n.SchemaVersion != SchemaVersion || n.Enforcement.Mode != ModeObserve || n.Webhook.Format != FormatNative {
		t.Fatalf("normalización de los enum: %+v", n)
	}
	if n.Enforcement.LiveActions == nil || n.Enforcement.WipeAllowlist == nil || n.Webhook.Events == nil {
		t.Fatal("ninguna lista puede quedar nil tras normalizar")
	}
	if n.Risk.ShiftZones == nil || n.Risk.ZoneRisk == nil {
		t.Fatal("ningún mapa puede quedar nil tras normalizar")
	}
	want := []string{"siem.example.com", "ntfy.sh"}
	if len(n.Egress.Hosts) != 2 || n.Egress.Hosts[0] != want[0] || n.Egress.Hosts[1] != want[1] {
		t.Fatalf("hosts: %v, quería %v (minúsculas, sin espacios, sin duplicados, orden estable)", n.Egress.Hosts, want)
	}
	if n.Risk.OffHoursStart != 0 || n.Risk.OffHoursEnd != 0 {
		t.Fatal("normalizar no inventa una franja nocturna: 0-0 es un valor legítimo")
	}
}

func TestJSONUsaSnakeCaseYNoPierdeNingunBloque(t *testing.T) {
	s := Default()
	s.Webhook = Webhook{URL: "https://siem.example.com/hec", Format: FormatOCSF,
		Events: []string{"incident.opened"}, Enabled: true, SecretSet: true}
	data, err := json.Marshal(s)
	if err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{`"schema_version"`, `"enforcement"`, `"live_actions"`, `"allow_wipe"`,
		`"wipe_allowlist"`, `"action_cooldown_seconds"`, `"webhook"`, `"secret_set"`, `"ntfy"`,
		`"token_set"`, `"egress"`, `"allow_private"`, `"risk"`, `"shift_zones"`, `"zone_risk"`,
		`"off_hours_start"`, `"off_hours_end"`, `"updated_at"`} {
		if !strings.Contains(string(data), k) {
			t.Fatalf("falta la clave %s en %s", k, data)
		}
	}
	var back Settings
	if err := json.Unmarshal(data, &back); err != nil {
		t.Fatal(err)
	}
	if back.Webhook.Format != FormatOCSF || !back.Webhook.SecretSet || back.Enforcement.ActionCooldownSeconds != 3600 {
		t.Fatalf("round-trip: %+v", back)
	}
}

func TestValidadoresPorBloqueSonUsablesSueltos(t *testing.T) {
	if err := (Enforcement{Mode: ModeEnforce, LiveActions: []action.Action{action.Message}}).Validate(); err != nil {
		t.Fatalf("bloque de enforcement válido: %v", err)
	}
	if err := (Egress{Hosts: []string{"siem.example.com"}}).Validate(); err != nil {
		t.Fatalf("bloque de egress válido: %v", err)
	}
	if err := (Risk{OffHoursStart: 22, OffHoursEnd: 6}).Validate(); err != nil {
		t.Fatalf("bloque de riesgo válido: %v", err)
	}
	if err := (Webhook{Format: "cef"}).Validate(); err == nil {
		t.Fatal("el bloque de webhook valida su propio formato")
	}
	if err := (Ntfy{Enabled: true, URL: "https://ntfy.sh/lucidfence"}).Validate(); err != nil {
		t.Fatalf("bloque de ntfy válido: %v", err)
	}
}
