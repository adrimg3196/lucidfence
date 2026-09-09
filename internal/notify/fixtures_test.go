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
