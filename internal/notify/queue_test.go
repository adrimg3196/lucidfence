package notify

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// reloj fijo: todas las entregas de los tests llevan este instante.
var ahora = time.Date(2026, 9, 6, 9, 30, 0, 0, time.UTC)

// sinkFalso guarda las líneas que el Notifier le pasa, ya serializadas a
// JSON, que es exactamente lo que store.AppendDelivery escribiría en
// deliveries.jsonl. Serializar aquí permite comprobar el contenido del
// fichero sin montar un store.
type sinkFalso struct {
	mu     sync.Mutex
	lineas []string
	err    error
}

func (s *sinkFalso) AppendDelivery(v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lineas = append(s.lineas, string(b))
	return s.err
}

func (s *sinkFalso) todo() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return strings.Join(s.lineas, "\n")
}

func (s *sinkFalso) cuenta() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.lineas)
}

// secretosFalsos es el proveedor de secretos del test.
type secretosFalsos struct {
	valores map[string]string
	err     error
}

func (s secretosFalsos) Secret(name string) (string, error) {
	if s.err != nil {
		return "", s.err
	}
	v, ok := s.valores[name]
	if !ok {
		return "", errors.New("no existe")
	}
	return v, nil
}

// eventoIncidente es el evento de referencia de los tests: el incidente que
// 1.x usa en tests/test_notifier_channels.py, traducido al dominio de 2.0.
func eventoIncidente() Event {
	return Event{
		Kind: EventIncidentOpened,
		At:   ahora,
		Incident: &incident.Incident{
			ID:         "inc-42",
			DeviceID:   "dev-7",
			DeviceName: "Tablet almacén",
			Kind:       incident.KindGeofenceExit,
			Severity:   "high",
			Title:      "Salida de geocerca",
			FenceID:    "hq",
			Status:     incident.StatusOpen,
			OpenedAt:   ahora,
			UpdatedAt:  ahora,
		},
	}
}

// ajustes construye unos Settings con el webhook apuntando a srv y el egress
// abierto a 127.0.0.1 (httptest siempre escucha en loopback).
func ajustes(srv *httptest.Server, secreto bool) settings.Settings {
	s := settings.Default()
	s.Webhook = settings.Webhook{
		URL:       srv.URL + "/hook",
		Format:    settings.FormatNative,
		Events:    []string{EventIncidentOpened, EventIncidentClosed},
		Enabled:   true,
		SecretSet: secreto,
	}
	s.Egress = settings.Egress{Hosts: []string{"127.0.0.1"}, AllowPrivate: true}
	return s
}

// opciones fija reloj, ids e intentos deterministas y sin esperas.
func opciones(buf *bytes.Buffer) Options {
	var n int
	var mu sync.Mutex
	return Options{
		Now:     func() time.Time { return ahora },
		Backoff: []time.Duration{0, 0, 0},
		Timeout: 2 * time.Second,
		Logger:  slog.New(slog.NewTextHandler(buf, nil)),
		NewID: func() string {
			mu.Lock()
			defer mu.Unlock()
			n++
			return "del-" + string(rune('0'+n))
		},
	}
}

// contador cuenta peticiones y responde con la secuencia de códigos dada;
// agotada la secuencia repite el último.
func contador(codigos ...int) (*httptest.Server, func() int, func() []*http.Request) {
	var mu sync.Mutex
	var recibidas []*http.Request
	var cuerpos [][]byte
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cuerpo := make([]byte, 0, 1024)
		buf := make([]byte, 1024)
		for {
			n, err := r.Body.Read(buf)
			cuerpo = append(cuerpo, buf[:n]...)
			if err != nil {
				break
			}
		}
		mu.Lock()
		i := len(recibidas)
		recibidas = append(recibidas, r.Clone(context.Background()))
		cuerpos = append(cuerpos, cuerpo)
		mu.Unlock()
		if i >= len(codigos) {
			i = len(codigos) - 1
		}
		w.WriteHeader(codigos[i])
	}))
	peticiones := func() int {
		mu.Lock()
		defer mu.Unlock()
		return len(recibidas)
	}
	vistas := func() []*http.Request {
		mu.Lock()
		defer mu.Unlock()
		for i, r := range recibidas {
			r.Body = nil
			r.Header.Set("X-Test-Body", string(cuerpos[i]))
		}
		return recibidas
	}
	return srv, peticiones, vistas
}

func TestEntregaCorrectaALaPrimera(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusOK)
	defer srv.Close()
	sink := &sinkFalso{}
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, sink, opciones(&buf))

	ds := n.Notify(context.Background(), eventoIncidente())

	if len(ds) != 1 {
		t.Fatalf("entregas = %d, quiero 1", len(ds))
	}
	d := ds[0]
	if !d.OK || d.Attempts != 1 || d.HTTPStatus != http.StatusOK {
		t.Fatalf("entrega = %+v, quiero ok con un intento y 200", d)
	}
	if d.Channel != ChannelWebhook || d.Event != EventIncidentOpened || d.ID == "" {
		t.Fatalf("metadatos de la entrega = %+v", d)
	}
	if !d.At.Equal(ahora) {
		t.Fatalf("At = %v, quiero el reloj inyectado %v", d.At, ahora)
	}
	if peticiones() != 1 {
		t.Fatalf("peticiones = %d, quiero 1", peticiones())
	}
	if sink.cuenta() != 1 {
		t.Fatalf("líneas en deliveries = %d, quiero 1", sink.cuenta())
	}
}

func TestQuinientosPersistenteAgotaLosTresIntentos(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusInternalServerError)
	defer srv.Close()
	sink := &sinkFalso{}
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, sink, opciones(&buf))

	ds := n.Notify(context.Background(), eventoIncidente())

	d := ds[0]
	if d.OK || d.Attempts != 3 || d.HTTPStatus != http.StatusInternalServerError {
		t.Fatalf("entrega = %+v, quiero fallo con tres intentos y 500", d)
	}
	if d.ErrorType != ErrorTypeHTTP {
		t.Fatalf("error_type = %q, quiero %q", d.ErrorType, ErrorTypeHTTP)
	}
	if peticiones() != 3 {
		t.Fatalf("peticiones = %d, quiero 3", peticiones())
	}
	if sink.cuenta() != 1 {
		t.Fatalf("líneas en deliveries = %d, quiero 1 (una por entrega, no por intento)", sink.cuenta())
	}
}

func TestQuinientosSeguidoDeDoscientosEntregaEnElSegundoIntento(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusInternalServerError, http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if !d.OK || d.Attempts != 2 || d.HTTPStatus != http.StatusOK {
		t.Fatalf("entrega = %+v, quiero ok en el segundo intento", d)
	}
	if d.Error != "" || d.ErrorType != "" {
		t.Fatalf("una entrega correcta no arrastra el error del primer intento: %+v", d)
	}
	if peticiones() != 2 {
		t.Fatalf("peticiones = %d, quiero 2", peticiones())
	}
}

func TestCuatrocientosNoSeReintenta(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusBadRequest)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if d.OK || d.Attempts != 1 || d.HTTPStatus != http.StatusBadRequest {
		t.Fatalf("entrega = %+v, quiero un solo intento y 400", d)
	}
	if peticiones() != 1 {
		t.Fatalf("peticiones = %d, quiero 1: un 4xx es definitivo", peticiones())
	}
}

func TestUnSoloBackoffEsUnSoloIntento(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusInternalServerError)
	defer srv.Close()
	var buf bytes.Buffer
	opts := opciones(&buf)
	opts.Backoff = []time.Duration{0}
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opts)

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if d.Attempts != 1 || peticiones() != 1 {
		t.Fatalf("intentos = %d, peticiones = %d, quiero 1 y 1 (len(Backoff) manda)", d.Attempts, peticiones())
	}
}

func TestDestinoFueraDeLaAllowlistNoAbreSocket(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusOK)
	defer srv.Close()
	sink := &sinkFalso{}
	var buf bytes.Buffer
	set := ajustes(srv, false)
	set.Egress = settings.Egress{Hosts: []string{"receptor.example"}, AllowPrivate: true}
	n := New(set, secretosFalsos{}, sink, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if d.OK || d.Attempts != 0 || d.ErrorType != ErrorTypeEgress {
		t.Fatalf("entrega = %+v, quiero denegada por egress sin intentos de red", d)
	}
	if d.Error == "" {
		t.Fatal("una denegación por egress nunca es silenciosa: falta el motivo")
	}
	if peticiones() != 0 {
		t.Fatalf("peticiones = %d, quiero 0: no se abre socket a un host denegado", peticiones())
	}
	if sink.cuenta() != 1 || !strings.Contains(sink.todo(), `"error_type":"egress"`) {
		t.Fatalf("deliveries = %q, quiero una línea con error_type egress", sink.todo())
	}
}

func TestEventoFueraDeLaListaEventsNoGeneraEntrega(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusOK)
	defer srv.Close()
	sink := &sinkFalso{}
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, sink, opciones(&buf))

	ev := eventoIncidente()
	ev.Kind = EventActionExecuted // no está en Events

	if ds := n.Notify(context.Background(), ev); len(ds) != 0 {
		t.Fatalf("entregas = %d, quiero 0", len(ds))
	}
	if peticiones() != 0 || sink.cuenta() != 0 {
		t.Fatalf("peticiones = %d, líneas = %d, quiero 0 y 0", peticiones(), sink.cuenta())
	}
}

func TestElReceptorVerificaLaFirmaYElCuerpoByteAByte(t *testing.T) {
	srv, _, vistas := contador(http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, true), secretosFalsos{valores: map[string]string{SecretWebhook: "s3cr3t"}}, &sinkFalso{}, opciones(&buf))

	ev := eventoIncidente()
	d := n.Notify(context.Background(), ev)[0]

	req := vistas()[0]
	cuerpo := []byte(req.Header.Get("X-Test-Body"))
	ev.DeliveryID = d.ID
	esperado, err := PayloadFor(settings.FormatNative, ev)
	if err != nil {
		t.Fatalf("PayloadFor: %v", err)
	}
	if !bytes.Equal(cuerpo, esperado) {
		t.Fatalf("cuerpo recibido = %q, quiero %q", cuerpo, esperado)
	}
	firma := req.Header.Get(SignatureHeader)
	if !Verify("s3cr3t", cuerpo, firma) {
		t.Fatalf("la firma %q no verifica contra el cuerpo recibido", firma)
	}
	if Verify("otra-clave", cuerpo, firma) || Verify("s3cr3t", append(cuerpo, 'x'), firma) {
		t.Fatal("la firma verifica con otra clave o con el cuerpo alterado")
	}
	if req.Header.Get(DeliveryHeader) != d.ID || req.Header.Get(EventHeader) != EventIncidentOpened {
		t.Fatalf("cabeceras de entrega = %q / %q", req.Header.Get(DeliveryHeader), req.Header.Get(EventHeader))
	}
}

func TestElSecretoNoApareceEnLasEntregasNiEnElLog(t *testing.T) {
	srv, _, _ := contador(http.StatusInternalServerError)
	defer srv.Close()
	sink := &sinkFalso{}
	var buf bytes.Buffer
	set := ajustes(srv, true)
	set.Webhook.URL = srv.URL + "/hook?token=tk_super_secreto"
	n := New(set, secretosFalsos{valores: map[string]string{SecretWebhook: "s3cr3t"}}, sink, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	for _, secreto := range []string{"s3cr3t", "tk_super_secreto"} {
		if strings.Contains(sink.todo(), secreto) {
			t.Fatalf("el secreto %q aparece en deliveries.jsonl: %s", secreto, sink.todo())
		}
		if strings.Contains(buf.String(), secreto) {
			t.Fatalf("el secreto %q aparece en el log: %s", secreto, buf.String())
		}
		if strings.Contains(d.Target, secreto) || strings.Contains(d.Error, secreto) {
			t.Fatalf("el secreto %q aparece en la entrega: %+v", secreto, d)
		}
	}
	if !strings.HasSuffix(d.Target, "/hook") {
		t.Fatalf("Target = %q, quiero la URL sin query", d.Target)
	}
}

func TestErrorDeTransporteNoFiltraLaURLCompleta(t *testing.T) {
	srv, _, _ := contador(http.StatusOK)
	set := ajustes(srv, false)
	set.Webhook.URL = srv.URL + "/hook?token=tk_super_secreto"
	srv.Close() // el destino ya no escucha: error de transporte en los tres intentos
	sink := &sinkFalso{}
	var buf bytes.Buffer
	n := New(set, secretosFalsos{}, sink, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if d.OK || d.Attempts != 3 || d.ErrorType != ErrorTypeTransport {
		t.Fatalf("entrega = %+v, quiero tres intentos fallidos de transporte", d)
	}
	if strings.Contains(d.Error, "tk_super_secreto") || strings.Contains(sink.todo(), "tk_super_secreto") {
		t.Fatalf("el error de transporte filtra la query: %q", d.Error)
	}
}

func TestSinkQueFallaNoPropagaElError(t *testing.T) {
	srv, _, _ := contador(http.StatusOK)
	defer srv.Close()
	sink := &sinkFalso{err: errors.New("disco lleno")}
	var buf bytes.Buffer
	n := New(ajustes(srv, false), secretosFalsos{}, sink, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if !d.OK {
		t.Fatalf("un Sink roto no cambia el resultado de la red: %+v", d)
	}
	if !strings.Contains(buf.String(), "disco lleno") {
		t.Fatalf("el fallo del Sink debe quedar en el log: %s", buf.String())
	}
}

func TestSecretoQueNoSeResuelveNoAbreSocket(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	n := New(ajustes(srv, true), secretosFalsos{err: errors.New("no existe")}, &sinkFalso{}, opciones(&buf))

	d := n.Notify(context.Background(), eventoIncidente())[0]

	if d.OK || d.Attempts != 0 || d.ErrorType != ErrorTypeSecret {
		t.Fatalf("entrega = %+v, quiero fallo de secreto sin intentos", d)
	}
	if peticiones() != 0 {
		t.Fatalf("peticiones = %d, quiero 0", peticiones())
	}
}

func TestLosDosCanalesEntreganYCadaUnoLlevaSuID(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	set := ajustes(srv, false)
	set.Ntfy = settings.Ntfy{URL: srv.URL + "/alertas", Enabled: true, TokenSet: true}
	sec := secretosFalsos{valores: map[string]string{SecretNtfy: "tk_abc"}}
	n := New(set, sec, &sinkFalso{}, opciones(&buf))

	ds := n.Notify(context.Background(), eventoIncidente())

	if len(ds) != 2 || ds[0].Channel != ChannelWebhook || ds[1].Channel != ChannelNtfy {
		t.Fatalf("entregas = %+v, quiero webhook y luego ntfy", ds)
	}
	if ds[0].ID == ds[1].ID {
		t.Fatalf("los dos canales comparten id de entrega %q", ds[0].ID)
	}
	if peticiones() != 2 {
		t.Fatalf("peticiones = %d, quiero 2", peticiones())
	}
}

func TestReloadCambiaLaConfiguracionEnCaliente(t *testing.T) {
	viejo, viejas, _ := contador(http.StatusOK)
	defer viejo.Close()
	nuevo, nuevas, _ := contador(http.StatusOK)
	defer nuevo.Close()
	var buf bytes.Buffer
	n := New(ajustes(viejo, false), secretosFalsos{}, &sinkFalso{}, opciones(&buf))

	n.Notify(context.Background(), eventoIncidente())
	n.Reload(ajustes(nuevo, false))
	n.Notify(context.Background(), eventoIncidente())

	if viejas() != 1 || nuevas() != 1 {
		t.Fatalf("peticiones viejo = %d, nuevo = %d, quiero 1 y 1", viejas(), nuevas())
	}
	if st := n.Status(); st.Webhook.Delivered != 2 {
		t.Fatalf("Delivered = %d, quiero 2: Reload no reinicia los contadores", st.Webhook.Delivered)
	}
}

func TestContextoCanceladoCortaLosReintentos(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusInternalServerError)
	defer srv.Close()
	var buf bytes.Buffer
	opts := opciones(&buf)
	opts.Backoff = []time.Duration{time.Minute, time.Minute, time.Minute}
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opts)

	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		for peticiones() < 1 {
			time.Sleep(time.Millisecond)
		}
		cancel()
	}()
	d := n.Notify(ctx, eventoIncidente())[0]

	if d.Attempts != 1 {
		t.Fatalf("intentos = %d, quiero 1: la cancelación corta la espera del backoff", d.Attempts)
	}
}

// El invariante de 1.x ("the notifier NEVER raises", cabecera de
// legacy/lucidfence/core/notifier.py) traído a 2.0: pase lo que pase dentro
// del canal de salida, el ciclo del motor sigue vivo. Se provoca desde NewID
// porque es la única dependencia inyectada que corre antes de tocar la red.
func TestNotifyNoPropagaPanico(t *testing.T) {
	srv, peticiones, _ := contador(http.StatusOK)
	defer srv.Close()
	var buf bytes.Buffer
	opts := opciones(&buf)
	opts.NewID = func() string { panic("generador de ids roto") }
	n := New(ajustes(srv, false), secretosFalsos{}, &sinkFalso{}, opts)

	ds := n.Notify(context.Background(), eventoIncidente())

	if len(ds) != 0 {
		t.Fatalf("entregas = %d, quiero 0: el pánico corta la entrega", len(ds))
	}
	if peticiones() != 0 {
		t.Fatalf("peticiones = %d, quiero 0", peticiones())
	}
	if !strings.Contains(buf.String(), "pánico entregando notificación") {
		t.Fatalf("el pánico debe quedar registrado: %s", buf.String())
	}
}
