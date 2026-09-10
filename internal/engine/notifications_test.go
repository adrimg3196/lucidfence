package engine

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
	"github.com/adrimg3196/lucidfence/internal/notify"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

const secretoWebhook = "s3cr3to-de-pruebas"

// entrega es lo que el receptor vio de una petición de webhook.
type entrega struct {
	evento, firma, id, sello string
	cuerpo                   []byte
}

// receptor es un endpoint de webhook local: guarda lo recibido y responde
// siempre con el código que le fijó el test.
type receptor struct {
	mu       sync.Mutex
	codigo   int
	recibido []entrega
}

func (r *receptor) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	body, _ := io.ReadAll(io.LimitReader(req.Body, 1<<20))
	r.mu.Lock()
	r.recibido = append(r.recibido, entrega{
		evento: req.Header.Get(notify.EventHeader),
		firma:  req.Header.Get(notify.SignatureHeader),
		id:     req.Header.Get(notify.DeliveryHeader),
		sello:  req.Header.Get(notify.TimestampHeader),
		cuerpo: body,
	})
	r.mu.Unlock()
	w.WriteHeader(r.codigo)
}

func (r *receptor) porEvento(kind string) []entrega {
	r.mu.Lock()
	defer r.mu.Unlock()
	var out []entrega
	for _, e := range r.recibido {
		if e.evento == kind {
			out = append(out, e)
		}
	}
	return out
}

func (r *receptor) total() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.recibido)
}

func arrancarReceptor(t *testing.T, codigo int) (*receptor, string) {
	t.Helper()
	r := &receptor{codigo: codigo}
	srv := httptest.NewServer(r)
	t.Cleanup(srv.Close)
	return r, srv.URL + "/hook"
}

// secretosFijos resuelve los secretos de los canales sin tocar el disco.
type secretosFijos map[string]string

func (s secretosFijos) Secret(name string) (string, error) {
	if v, ok := s[name]; ok {
		return v, nil
	}
	return "", errors.New("secreto no configurado: " + name)
}

// ajustesWebhook apunta el webhook al receptor local. La allowlist de egress
// se abre a 127.0.0.1 con allow_private porque un receptor de pruebas vive en
// loopback, que el egress deniega por defecto (T9).
func ajustesWebhook(url, formato string, eventos []string) settings.Settings {
	set := settings.Default()
	set.Webhook = settings.Webhook{URL: url, Format: formato, Events: eventos, Enabled: true, SecretSet: true}
	set.Egress = settings.Egress{Hosts: []string{"127.0.0.1"}, AllowPrivate: true}
	return set
}

// motorNotificado monta el motor sobre la fixture demo con un Notifier
// determinista: reloj fijo, id de entrega fijo y backoff a cero (tres
// intentos sin dormir).
func motorNotificado(t *testing.T, set settings.Settings, ad uem.Adapter) (*Engine, *store.OrgStore) {
	t.Helper()
	return motorNotificadoEn(t, set, ad, &reloj{at: time.Date(2026, 9, 6, 12, 0, 0, 0, time.UTC)})
}

// motorNotificadoEn es lo mismo con el reloj que le pase el test: el
// enfriamiento de las alertas solo se puede observar moviendo la hora entre
// ciclos (el tipo reloj vive en risk_dwell_test.go, mismo paquete).
func motorNotificadoEn(t *testing.T, set settings.Settings, ad uem.Adapter, clock *reloj) (*Engine, *store.OrgStore) {
	t.Helper()
	s, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	if err := SeedDemo(org, clock.now()); err != nil {
		t.Fatal(err)
	}
	if err := org.SaveSettings(set); err != nil {
		t.Fatal(err)
	}
	mudo := slog.New(slog.DiscardHandler)
	n := notify.New(set, secretosFijos{notify.SecretWebhook: secretoWebhook}, org, notify.Options{
		Now: clock.now, Backoff: []time.Duration{0, 0, 0}, Logger: mudo,
		NewID: func() string { return "dlv-fijo" },
	})
	e := New(org, []uem.Adapter{ad}, Options{Mode: "simulation", Interval: time.Hour,
		Now: clock.now, Logger: mudo, Notifier: n})
	return e, org
}

// verificarEntrega comprueba que llegó un webhook de ese evento, firmado con
// el secreto de la organización y con las cuatro cabeceras del contrato.
func verificarEntrega(t *testing.T, rec *receptor, kind string) {
	t.Helper()
	got := rec.porEvento(kind)
	if len(got) == 0 {
		t.Fatalf("el receptor no recibió ningún %s", kind)
	}
	d := got[0]
	if !notify.Verify(secretoWebhook, d.cuerpo, d.firma) {
		t.Fatalf("%s: la firma no verifica el cuerpo recibido: %q", kind, d.firma)
	}
	if !strings.HasPrefix(d.firma, "sha256=") || d.id == "" || d.sello == "" || d.evento != kind {
		t.Fatalf("%s: faltan cabeceras del contrato: %+v", kind, d)
	}
}

// ultimaEntrega devuelve la última línea de deliveries.jsonl como mapa.
func ultimaEntrega(t *testing.T, org *store.OrgStore) map[string]any {
	t.Helper()
	ds, err := org.RecentDeliveries(50)
	if err != nil {
		t.Fatal(err)
	}
	if len(ds) == 0 {
		t.Fatal("deliveries.jsonl no puede quedar vacío: ninguna entrega es silenciosa")
	}
	var out map[string]any
	if err := json.Unmarshal(ds[len(ds)-1], &out); err != nil {
		t.Fatal(err)
	}
	return out
}

// TestElCicloEntregaWebhooksFirmadosDeSusEventos cubre las dos mitades del
// ciclo: la acción que se ejecuta al entrar en la geocerca y el incidente que
// abre la salida, cada uno con su webhook firmado y verificable.
func TestElCicloEntregaWebhooksFirmadosDeSusEventos(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusOK)
	ad := nuevaFlotaMovil(dentroHQ)
	e, org := motorNotificado(t, ajustesWebhook(url, settings.FormatNative, settings.WebhookEvents), ad)

	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.Deliveries == 0 || st.DeliveriesFailed != 0 {
		t.Fatalf("el receptor responde 200: %+v", st)
	}
	verificarEntrega(t, rec, notify.EventActionExecuted)

	ad.mover(fueraHQ)
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	verificarEntrega(t, rec, notify.EventIncidentOpened)

	if d := ultimaEntrega(t, org); d["ok"] != true || d["channel"] != "webhook" {
		t.Fatalf("deliveries.jsonl registra cada entrega: %v", d)
	}
}

// TestElCuerpoOCSFEsUnDetectionFindingSinCoordenadas: el formato ocsf emite un
// Detection Finding 2004 y la lista blanca de campos hace estructuralmente
// imposible publicar la ubicación (spec §6.4).
func TestElCuerpoOCSFEsUnDetectionFindingSinCoordenadas(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusOK)
	ad := nuevaFlotaMovil(fueraHQ)
	e, _ := motorNotificado(t, ajustesWebhook(url, settings.FormatOCSF, settings.WebhookEvents), ad)
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}

	got := rec.porEvento(notify.EventIncidentOpened)
	if len(got) == 0 {
		t.Fatal("el receptor no recibió el incident.opened")
	}
	var out map[string]any
	if err := json.Unmarshal(got[0].cuerpo, &out); err != nil {
		t.Fatal(err)
	}
	if out["class_uid"] != float64(notify.OCSFClassUID) || out["category_uid"] != float64(notify.OCSFCategoryUID) {
		t.Fatalf("el cuerpo debe ser un Detection Finding 2004: %v", out)
	}
	cuerpo := string(got[0].cuerpo)
	for _, prohibido := range []string{`"lat"`, `"lng"`, `"location"`, `"coordinates"`} {
		if strings.Contains(cuerpo, prohibido) {
			t.Fatalf("el cuerpo no puede publicar la ubicación (%s): %s", prohibido, cuerpo)
		}
	}
}

// TestUnWebhookCaidoNoAlteraElCiclo es el invariante de §6.4 y de 1.x ("the
// notifier NEVER raises"): la red de un tercero no cambia lo que el ciclo
// hizo con la flota. Solo incident.opened está suscrito, así que el ciclo de
// la salida entrega exactamente una vez y el contador es inequívoco.
func TestUnWebhookCaidoNoAlteraElCiclo(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusInternalServerError)
	ad := nuevaFlotaMovil(dentroHQ)
	e, org := motorNotificado(t, ajustesWebhook(url, settings.FormatNative, []string{notify.EventIncidentOpened}), ad)
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}

	ad.mover(fueraHQ)
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatalf("un webhook caído no puede hacer fallar el ciclo: %v", err)
	}
	if st.ActionsExecuted != 1 {
		t.Fatalf("la salida de demo-hq ejecuta su notify pase lo que pase con el webhook: %+v", st)
	}
	if st.Deliveries != 1 || st.DeliveriesFailed != 1 {
		t.Fatalf("una entrega intentada y fallida: %+v", st)
	}
	if rec.total() != 3 {
		t.Fatalf("un 500 se reintenta tres veces: %d peticiones", rec.total())
	}
	d := ultimaEntrega(t, org)
	if d["ok"] != false || d["attempts"] != float64(3) || d["error_type"] != notify.ErrorTypeHTTP {
		t.Fatalf("deliveries.jsonl deja constancia del fallo: %v", d)
	}
}

// TestUnEventoFueraDeLaListaNoSeEntrega: el filtro por canal es la única
// forma que tiene el operador de bajar el ruido, y el ciclo lo respeta.
func TestUnEventoFueraDeLaListaNoSeEntrega(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusOK)
	ad := nuevaFlotaMovil(fueraHQ)
	e, org := motorNotificado(t, ajustesWebhook(url, settings.FormatNative, []string{notify.EventIncidentClosed}), ad)

	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.IncidentsOpened == 0 {
		t.Fatalf("el ciclo abre el incidente de salida: %+v", st)
	}
	if st.Deliveries != 0 || rec.total() != 0 {
		t.Fatalf("solo incident.closed está suscrito: %+v (%d peticiones)", st, rec.total())
	}
	if ds, err := org.RecentDeliveries(10); err != nil || len(ds) != 0 {
		t.Fatalf("lo no suscrito no deja línea en deliveries.jsonl: %v %v", ds, err)
	}
}

// TestUnHandoffNuevoSeAnunciaUnaVezPorElNotificador es la línea del brief que
// no sujetaba nada ("cada handoff nuevo emite un handoff.pending por el
// notificador de T15") y su reverso ("solo se anuncian los que este ciclo
// abre"), comprobadas donde se ven de verdad: en el receptor del webhook, no
// en la bandeja. Que HandoffsPending valga uno no demuestra que el SOC se
// haya enterado; sin este test, borrar e.handoffEvents() de notifyCycle deja
// los diecisiete tests de la tarea en verde y el aviso de que hay una acción
// destructiva esperando una firma humana desaparece en silencio.
func TestUnHandoffNuevoSeAnunciaUnaVezPorElNotificador(t *testing.T) {
	rec, url := arrancarReceptor(t, http.StatusOK)
	rel := &reloj{at: tSOAR}
	// Fuera de la geocerca y no conforme casa con el playbook de fábrica
	// soar-noncompliant-outside, cuyo lock es destructivo: abre handoff.
	fleet := &grabadora{clock: rel, punto: fueraHQ, conforme: false}
	e, _ := motorNotificadoEn(t, ajustesWebhook(url, settings.FormatNative, settings.WebhookEvents), fleet, rel)

	if st := unCiclo(t, e); st.HandoffsPending != 1 {
		t.Fatalf("el ciclo deja exactamente una petición esperando: %+v", st)
	}
	got := rec.porEvento(notify.EventHandoffPending)
	if len(got) != 1 {
		t.Fatalf("un handoff nuevo sale por el notificador una vez: %d entregas", len(got))
	}
	verificarEntrega(t, rec, notify.EventHandoffPending)

	var cuerpo map[string]any
	if err := json.Unmarshal(got[0].cuerpo, &cuerpo); err != nil {
		t.Fatal(err)
	}
	ho, _ := cuerpo["handoff"].(map[string]any)
	quiero := playbook.HandoffID("dev-1", "soar-noncompliant-outside", action.Lock)
	if ho["id"] != quiero || ho["status"] != string(playbook.HandoffPending) {
		t.Fatalf("el sobre lleva la petición pendiente con su id determinista: %v", ho)
	}
	if ho["action"] != string(action.Lock) || ho["device_id"] != "dev-1" {
		t.Fatalf("el sobre dice qué se pide y sobre qué dispositivo: %v", ho)
	}

	// Segundo ciclo dentro de la ventana: la petición sigue pendiente, e.opened
	// queda vacío y el aviso no se repite con el mismo id.
	rel.avanzar(HandoffReopenAfter / 2)
	if st := unCiclo(t, e); st.HandoffsPending != 1 {
		t.Fatalf("la petición sigue esperando decisión: %+v", st)
	}
	if n := len(rec.porEvento(notify.EventHandoffPending)); n != 1 {
		t.Fatalf("una pendiente que sigue pendiente no se vuelve a anunciar: %d entregas", n)
	}
}
