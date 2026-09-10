package engine

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// motorDeAjustes es un motor sin conectores sobre un directorio nuevo: estas
// pruebas no ejecutan ningún ciclo, solo miran lo que el motor expone fuera
// de él.
func motorDeAjustes(t *testing.T) *Engine {
	t.Helper()
	st, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := st.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	reloj := func() time.Time { return time.Date(2026, 9, 6, 9, 30, 0, 0, time.UTC) }
	return New(org, nil, Options{Mode: "simulation", Interval: time.Hour, Now: reloj})
}

// receptorMudo es un servidor que cuenta las peticiones que recibe. Validar
// unos ajustes no debe generar ni una: comprobar no es probar.
func receptorMudo(t *testing.T) (*httptest.Server, *atomic.Int64) {
	t.Helper()
	var visitas atomic.Int64
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		visitas.Add(1)
		w.WriteHeader(http.StatusNoContent)
	}))
	t.Cleanup(srv.Close)
	return srv, &visitas
}

func canal(t *testing.T, out SettingsCheck, nombre string) ChannelCheck {
	t.Helper()
	for _, c := range out.Channels {
		if c.Channel == nombre {
			return c
		}
	}
	t.Fatalf("falta el canal %q en %+v", nombre, out.Channels)
	return ChannelCheck{}
}

func TestApplySettingsSurteEfectoSinEsperarAlCiclo(t *testing.T) {
	e := motorDeAjustes(t)
	if got := e.Status().Enforcement.Mode; got != settings.ModeObserve {
		t.Fatalf("el motor nace en observe, no en %q", got)
	}
	set := settings.Default()
	set.Enforcement.Mode = settings.ModeEnforce
	set.Enforcement.LiveActions = []action.Action{action.Message}
	e.ApplySettings(set)
	st := e.Status().Enforcement
	if st.Mode != settings.ModeEnforce || len(st.LiveActions) != 1 || st.LiveActions[0] != action.Message {
		t.Fatalf("el enforcement debe estar vigente sin ciclo de por medio: %+v", st)
	}
}

func TestCheckSettingsDeniegaFueraDeLaAllowlistYNoAbreSocket(t *testing.T) {
	e := motorDeAjustes(t)
	srv, visitas := receptorMudo(t)
	set := settings.Default()
	set.Webhook = settings.Webhook{URL: srv.URL + "/hook", Format: settings.FormatNative,
		Events: []string{"incident.opened"}, Enabled: true}
	set.Egress = settings.Egress{Hosts: []string{"hooks.ejemplo.com"}}

	out := e.CheckSettings(context.Background(), set)
	c := canal(t, out, "webhook")
	if out.OK || c.OK || !strings.Contains(c.Reason, "allowlist") {
		t.Fatalf("un destino fuera de la allowlist se deniega nombrando el motivo: %+v", out)
	}
	if c.URL != srv.URL+"/hook" {
		t.Fatalf("la respuesta devuelve la URL comprobada: %q", c.URL)
	}

	set.Egress = settings.Egress{Hosts: []string{"127.0.0.1"}, AllowPrivate: true}
	out = e.CheckSettings(context.Background(), set)
	c = canal(t, out, "webhook")
	if !c.OK || len(c.Addresses) != 1 || c.Addresses[0] != "127.0.0.1" {
		t.Fatalf("con la allowlist correcta el destino se acepta y declara su dirección: %+v", c)
	}
	if n := canal(t, out, "ntfy"); n.Enabled || n.OK {
		t.Fatalf("ntfy está apagado y sin URL: %+v", n)
	}
	if got := visitas.Load(); got != 0 {
		t.Fatalf("validar no envía nada: %d peticiones al receptor", got)
	}
}

func TestCheckSettingsNombraElCampoInvalido(t *testing.T) {
	e := motorDeAjustes(t)
	set := settings.Default()
	set.Enforcement.Mode = "vigilante"
	out := e.CheckSettings(context.Background(), set)
	if out.OK || out.Field != "enforcement.mode" || out.Error == "" {
		t.Fatalf("un modo desconocido se rechaza nombrando el campo: %+v", out)
	}
}

func TestSettingsFieldSoloDevuelveCamposConocidos(t *testing.T) {
	casos := []struct {
		err    error
		quiero string
	}{
		{nil, ""},
		{errors.New("boom"), ""},
		{errors.New("enforcement.mode: valor desconocido \"vigilante\""), "enforcement.mode"},
		{errors.New("webhook.events[1] no es un evento del catálogo"), "webhook.events[1]"},
		{errors.New("ajustes inválidos: risk.off_hours_start fuera de 0-23"), "risk.off_hours_start"},
	}
	for _, c := range casos {
		if got := SettingsField(c.err); got != c.quiero {
			t.Fatalf("SettingsField(%v) = %q, quiero %q", c.err, got, c.quiero)
		}
	}
}
