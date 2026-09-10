package store

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

// pageT0 es el instante del primer evento sembrado; el evento i cae en
// pageT0 + i minutos, así que el orden es comprobable por At.
var pageT0 = time.Date(2026, 9, 6, 0, 0, 0, 0, time.UTC)

func seedEvents(t *testing.T, o *OrgStore, desde, hasta int) {
	t.Helper()
	for i := desde; i < hasta; i++ {
		ev := transition.Transition{
			At:       pageT0.Add(time.Duration(i) * time.Minute),
			DeviceID: "dev-1",
			From:     "none:unknown",
			To:       "demo-hq:inside",
		}
		if err := o.AppendEvent(ev); err != nil {
			t.Fatal(err)
		}
	}
}

// collectPages recorre todas las páginas siguiendo next y devuelve el tamaño
// de cada una y los instantes en el orden en que se leyeron.
func collectPages(t *testing.T, o *OrgStore, limit int) ([]int, []time.Time) {
	t.Helper()
	var sizes []int
	var seen []time.Time
	for cursor := ""; ; {
		items, next, err := o.EventsPage(limit, cursor)
		if err != nil {
			t.Fatal(err)
		}
		sizes = append(sizes, len(items))
		for _, ev := range items {
			seen = append(seen, ev.At)
		}
		if next == "" {
			return sizes, seen
		}
		if len(sizes) > 10 {
			t.Fatal("paginación que no termina")
		}
		cursor = next
	}
}

func TestEventsPagePaginaDeCienEnCienSinRepetirNiSaltar(t *testing.T) {
	o := org(t)
	seedEvents(t, o, 0, 250)
	sizes, seen := collectPages(t, o, 100)
	if len(sizes) != 3 || sizes[0] != 100 || sizes[1] != 100 || sizes[2] != 50 {
		t.Fatalf("tamaños de página: %v", sizes)
	}
	if len(seen) != 250 {
		t.Fatalf("elementos vistos: %d", len(seen))
	}
	// Del más reciente al más antiguo, sin repetir ni saltarse ninguno.
	for i, at := range seen {
		want := pageT0.Add(time.Duration(249-i) * time.Minute)
		if !at.Equal(want) {
			t.Fatalf("posición %d: %s, esperaba %s", i, at, want)
		}
	}
}

func TestEventsPageEsEstableAunqueElMotorSigaEscribiendo(t *testing.T) {
	o := org(t)
	seedEvents(t, o, 0, 250)
	primera, next, err := o.EventsPage(100, "")
	if err != nil || len(primera) != 100 || next == "" {
		t.Fatalf("primera página: %d %q %v", len(primera), next, err)
	}
	if !primera[99].At.Equal(pageT0.Add(150 * time.Minute)) {
		t.Fatalf("última de la primera página: %s", primera[99].At)
	}
	// El motor sigue escribiendo entre las dos páginas.
	seedEvents(t, o, 250, 270)
	segunda, _, err := o.EventsPage(100, next)
	if err != nil || len(segunda) != 100 {
		t.Fatalf("segunda página: %d %v", len(segunda), err)
	}
	if !segunda[0].At.Equal(pageT0.Add(149*time.Minute)) || !segunda[99].At.Equal(pageT0.Add(50*time.Minute)) {
		t.Fatalf("los índices ya emitidos no se desplazan: %s .. %s", segunda[0].At, segunda[99].At)
	}
}

func TestCursorManipuladoDevuelveErrBadCursor(t *testing.T) {
	malos := []string{
		"",
		"!!no-es-base64!!",
		base64.RawURLEncoding.EncodeToString([]byte("abc")),
		base64.RawURLEncoding.EncodeToString([]byte("-5")),
		base64.RawURLEncoding.EncodeToString([]byte("1.5")),
	}
	for _, bad := range malos {
		if _, err := DecodeCursor(bad); !errors.Is(err, ErrBadCursor) {
			t.Fatalf("DecodeCursor(%q): %v", bad, err)
		}
	}
	o := org(t)
	seedEvents(t, o, 0, 5)
	if _, _, err := o.EventsPage(10, "!!no-es-base64!!"); !errors.Is(err, ErrBadCursor) {
		t.Fatalf("EventsPage: %v", err)
	}
	if _, _, err := o.ActionsPage(10, "!!no-es-base64!!"); !errors.Is(err, ErrBadCursor) {
		t.Fatalf("ActionsPage: %v", err)
	}
}

func TestEncodeDecodeCursorIdaYVuelta(t *testing.T) {
	for _, index := range []int{0, 1, 149, 100000} {
		c := EncodeCursor(index)
		if strings.ContainsAny(c, "+/=") {
			t.Fatalf("el cursor debe ser base64url sin relleno: %q", c)
		}
		got, err := DecodeCursor(c)
		if err != nil || got != index {
			t.Fatalf("ida y vuelta de %d: %d %v", index, got, err)
		}
	}
	if EncodeCursor(-1) != "" {
		t.Fatal("un índice negativo es el cursor vacío: no queda nada por delante")
	}
}

func TestLimitePorDefectoYTope(t *testing.T) {
	o := org(t)
	seedEvents(t, o, 0, 250)
	items, next, err := o.EventsPage(0, "")
	if err != nil || len(items) != DefaultPageLimit || next == "" {
		t.Fatalf("limit 0 usa el defecto: %d %q %v", len(items), next, err)
	}
	if negativo, _, _ := o.EventsPage(-7, ""); len(negativo) != DefaultPageLimit {
		t.Fatalf("un limit negativo usa el defecto: %d", len(negativo))
	}
	grande := org(t)
	seedEvents(t, grande, 0, 600)
	acotada, next2, err := grande.EventsPage(10000, "")
	if err != nil || len(acotada) != MaxPageLimit {
		t.Fatalf("limit 10000 se acota a MaxPageLimit: %d %v", len(acotada), err)
	}
	if next2 == "" {
		t.Fatal("quedan 100 eventos por delante: next no puede estar vacío")
	}
}

func TestActionsPageDevuelveLosResultadosDelMasRecienteAlMasAntiguo(t *testing.T) {
	o := org(t)
	for i := 0; i < 3; i++ {
		res := action.Result{
			Adapter: "simulation", OK: true, DeviceID: "dev-1", Action: action.Message,
			DryRun: true, At: pageT0.Add(time.Duration(i) * time.Minute),
			PolicyID: "pol-" + strconv.Itoa(i), Severity: "medium",
		}
		if err := o.AppendAction(res); err != nil {
			t.Fatal(err)
		}
	}
	items, next, err := o.ActionsPage(2, "")
	if err != nil || len(items) != 2 || items[0].PolicyID != "pol-2" || items[1].PolicyID != "pol-1" {
		t.Fatalf("primera página: %+v %v", items, err)
	}
	if items[0].Severity != "medium" {
		t.Fatalf("los campos nuevos de action.Result viajan enteros: %+v", items[0])
	}
	resto, next2, err := o.ActionsPage(2, next)
	if err != nil || len(resto) != 1 || resto[0].PolicyID != "pol-0" || next2 != "" {
		t.Fatalf("segunda página: %+v %q %v", resto, next2, err)
	}
}

func TestPaginaVaciaSinFichero(t *testing.T) {
	o := org(t)
	items, next, err := o.EventsPage(10, "")
	if err != nil || len(items) != 0 || next != "" {
		t.Fatalf("eventos: %d %q %v", len(items), next, err)
	}
	acts, next2, err := o.ActionsPage(10, "")
	if err != nil || len(acts) != 0 || next2 != "" {
		t.Fatalf("acciones: %d %q %v", len(acts), next2, err)
	}
	if items == nil || acts == nil {
		t.Fatal("una página vacía se serializa [] y nunca null")
	}
}

func TestCursorMasAllaDelFinalSeAjusta(t *testing.T) {
	o := org(t)
	seedEvents(t, o, 0, 5)
	items, next, err := o.EventsPage(10, EncodeCursor(99))
	if err != nil || len(items) != 5 || next != "" {
		t.Fatalf("cursor por delante del final: %d %q %v", len(items), next, err)
	}
	if !items[0].At.Equal(pageT0.Add(4 * time.Minute)) {
		t.Fatalf("debe empezar por la última línea real: %s", items[0].At)
	}
}

// TestLineaIlegibleNoTumbaElHistorico: un JSONL de solo append se corrompe
// por el final (un kill a mitad de AppendJSONL, un disco lleno). Esa media
// línea se descarta y el resto del histórico se sirve; devolver error dejaba
// /api/v1/events, /api/v1/actions y el what-if en 500 para siempre, sin más
// recuperación que editar el fichero a mano. Es lo que TrailAll ya hacía.
func TestLineaIlegibleNoTumbaElHistorico(t *testing.T) {
	o := org(t)
	seedEvents(t, o, 0, 2)
	if err := AppendJSONL(o.Path("events.jsonl"), json.RawMessage(`"no es un objeto"`)); err != nil {
		t.Fatal(err)
	}
	seedEvents(t, o, 2, 3)

	items, next, err := o.EventsPage(10, "")
	if err != nil || next != "" {
		t.Fatalf("una línea ilegible no puede tumbar la página: %v %q", err, next)
	}
	if len(items) != 3 || !items[0].At.Equal(pageT0.Add(2*time.Minute)) {
		t.Fatalf("las tres líneas buenas se sirven, la ilegible no: %+v", items)
	}
	recientes, err := o.RecentEvents(0)
	if err != nil || len(recientes) != 3 {
		t.Fatalf("RecentEvents (lo que lee el what-if) tampoco se cae: %v %+v", err, recientes)
	}
}
