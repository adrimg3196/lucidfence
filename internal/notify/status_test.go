package notify

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

func TestStatusCuentaExitosYFallosPorCanal(t *testing.T) {
	srv, _, _ := contador(http.StatusOK, http.StatusOK, http.StatusBadRequest)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))

	n.Notify(context.Background(), eventoIncidente())
	n.Notify(context.Background(), eventoIncidente())
	n.Notify(context.Background(), eventoIncidente())

	st := n.Status()
	if st.Webhook.Delivered != 2 || st.Webhook.Failed != 1 {
		t.Fatalf("webhook = %+v, quiero 2 entregadas y 1 fallida", st.Webhook)
	}
	if st.Webhook.LastOK == nil || !st.Webhook.LastOK.Equal(ahora) {
		t.Fatalf("LastOK = %v, quiero el reloj inyectado", st.Webhook.LastOK)
	}
	if st.Webhook.LastError == "" {
		t.Fatal("LastError vacío tras un 400")
	}
	if st.Ntfy.Delivered != 0 || st.Ntfy.Failed != 0 || st.Ntfy.Enabled {
		t.Fatalf("ntfy = %+v, quiero un canal apagado y a cero", st.Ntfy)
	}
}

func TestLastOKEsNilMientrasNoHayaEntregaCorrecta(t *testing.T) {
	srv, _, _ := contador(http.StatusInternalServerError)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))

	if st := n.Status(); st.Webhook.LastOK != nil {
		t.Fatalf("LastOK = %v antes de la primera entrega, quiero nil", st.Webhook.LastOK)
	}
	n.Notify(context.Background(), eventoIncidente())
	st := n.Status()
	if st.Webhook.LastOK != nil {
		t.Fatalf("LastOK = %v tras un fallo, quiero nil (nunca un time.Time cero como éxito)", st.Webhook.LastOK)
	}
	if st.Webhook.Failed != 1 {
		t.Fatalf("Failed = %d, quiero 1", st.Webhook.Failed)
	}
}

func TestUnExitoPosteriorLimpiaElUltimoError(t *testing.T) {
	srv, _, _ := contador(http.StatusBadRequest, http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))

	n.Notify(context.Background(), eventoIncidente())
	if n.Status().Webhook.LastError == "" {
		t.Fatal("LastError vacío tras el 400")
	}
	n.Notify(context.Background(), eventoIncidente())

	st := n.Status()
	if st.Webhook.LastError != "" {
		t.Fatalf("LastError = %q tras una entrega correcta, quiero vacío", st.Webhook.LastError)
	}
	if st.Webhook.Delivered != 1 || st.Webhook.Failed != 1 {
		t.Fatalf("contadores = %d/%d, quiero 1 entregada y 1 fallida", st.Webhook.Delivered, st.Webhook.Failed)
	}
}

func TestStatusPublicaEnabledYTargetSinSecretos(t *testing.T) {
	srv, _, _ := contador(http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	set := ajustes(srv, true)
	set.Webhook.URL = srv.URL + "/hook?token=tk_super_secreto"
	set.Ntfy = settings.Ntfy{URL: srv.URL + "/alertas?auth=tk_ntfy", Enabled: true, TokenSet: true}
	n := New(set, secretosFalsos{valores: map[string]string{SecretWebhook: "s", SecretNtfy: "t"}}, &sinkFalso{}, opciones(&buf))

	st := n.Status()

	if !st.Webhook.Enabled || !st.Ntfy.Enabled {
		t.Fatalf("Enabled = %v / %v, quiero los dos canales activos", st.Webhook.Enabled, st.Ntfy.Enabled)
	}
	if !strings.HasSuffix(st.Webhook.Target, "/hook") || !strings.HasSuffix(st.Ntfy.Target, "/alertas") {
		t.Fatalf("targets = %q / %q, quiero las URL sin query", st.Webhook.Target, st.Ntfy.Target)
	}
	for _, secreto := range []string{"tk_super_secreto", "tk_ntfy"} {
		if strings.Contains(st.Webhook.Target+st.Ntfy.Target, secreto) {
			t.Fatalf("el secreto %q aparece en el Status", secreto)
		}
	}
}

func TestStatusDevuelveUnaCopia(t *testing.T) {
	srv, _, _ := contador(http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))
	n.Notify(context.Background(), eventoIncidente())

	st := n.Status()
	*st.Webhook.LastOK = ahora.Add(72 * time.Hour)
	st.Webhook.Delivered = 999

	otra := n.Status()
	if otra.Webhook.Delivered != 1 || !otra.Webhook.LastOK.Equal(ahora) {
		t.Fatalf("Status devuelve estado interno mutable: %+v", otra.Webhook)
	}
}

func TestStatusDeUnNotifierApagadoEsSeguroDeSerializar(t *testing.T) {
	var buf bytes.Buffer
	n := New(settings.Default(), nil, nil, opciones(&buf))

	if ds := n.Notify(context.Background(), eventoIncidente()); len(ds) != 0 {
		t.Fatalf("entregas = %d con los dos canales apagados, quiero 0", len(ds))
	}
	st := n.Status()
	if st.Webhook.Enabled || st.Ntfy.Enabled || st.Webhook.Target != "" || st.Ntfy.Target != "" {
		t.Fatalf("status = %+v, quiero los dos canales apagados y sin destino", st)
	}
	// Es lo que /api/v1/health serializa en cada sondeo: sin ninguna entrega,
	// last_ok y last_error se omiten en vez de publicar la fecha cero.
	b, err := json.Marshal(st)
	if err != nil {
		t.Fatalf("json.Marshal(Status): %v", err)
	}
	got := string(b)
	quiero := `{"webhook":{"enabled":false,"delivered":0,"failed":0},"ntfy":{"enabled":false,"delivered":0,"failed":0}}`
	if got != quiero {
		t.Fatalf("Status serializado = %s, quiero %s", got, quiero)
	}
}
