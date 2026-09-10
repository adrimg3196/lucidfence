package engine

import (
	"fmt"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// stance es la estancia en curso de un dispositivo: la clave de estado y desde
// cuándo rige. Solo la usa el modo "geocercas actuales", donde la clave es
// hipotética y no hay transición registrada que la feche.
type stance struct {
	key   string
	since time.Time
}

// history indexa events.jsonl por dispositivo para responder "¿dónde estaba
// este dispositivo en este instante?" sin recalcular nada: la transición
// registró la clave "<geocerca|none>:<estado>" y el instante exacto en que
// empezó a regir. En 2.0 el trail no guarda el estado de geocerca (a diferencia
// del trails.jsonl de 1.x), así que esta es la única fuente histórica.
type history struct {
	byDevice map[string][]transition.Transition
	cursor   map[string]int
}

func newHistory(evs []transition.Transition) *history {
	h := &history{byDevice: map[string][]transition.Transition{}, cursor: map[string]int{}}
	for _, ev := range evs {
		h.byDevice[ev.DeviceID] = append(h.byDevice[ev.DeviceID], ev)
	}
	return h
}

// advance devuelve la última transición del dispositivo en o antes de at. Los
// puntos de un mismo dispositivo llegan en orden cronológico, así que el cursor
// solo avanza y el coste total es lineal en transiciones, no el cuadrático de
// rebuscar el fichero entero por cada uno de los 20 000 puntos. Un punto que
// llegue fuera de orden rebobina el cursor en vez de dar una respuesta falsa.
func (h *history) advance(deviceID string, at time.Time) (transition.Transition, bool) {
	evs := h.byDevice[deviceID]
	i := h.cursor[deviceID]
	if i > 0 && evs[i-1].At.After(at) {
		i = 0
	}
	for i < len(evs) && !evs[i].At.After(at) {
		i++
	}
	h.cursor[deviceID] = i
	if i == 0 {
		return transition.Transition{}, false
	}
	return evs[i-1], true
}

// parseKey descompone la clave "<geocerca|none>:<estado>" de una transición.
// Una clave que no se reconoce vale "unknown" sin geocerca: inventar un estado
// sería peor que declarar que no se sabe.
func parseKey(key string) (device.FenceState, string) {
	id, state, ok := strings.Cut(key, ":")
	if !ok {
		return device.Unknown, ""
	}
	if id == "none" {
		id = ""
	}
	switch device.FenceState(state) {
	case device.Inside, device.Outside:
		return device.FenceState(state), id
	}
	return device.Unknown, ""
}

// placeAt sitúa el punto: estado de geocerca, geocerca y desde cuándo rige esa
// estancia (el reloj del dwell).
//
// Con UseCurrentFences el estado se RECALCULA contra las geocercas de hoy y la
// estancia se mide por rachas de puntos consecutivos con la misma clave, que es
// toda la resolución que da el trail. Sin él se usa el estado que registró el
// histórico de eventos, con el instante exacto de la transición; antes de la
// primera transición de un dispositivo el estado es unknown, que es con lo que
// arranca el motor. Esa racha empieza, como muy pronto, en el primer punto de
// la ventana simulada, así que el dwell que sale de aquí puede ser menor que la
// permanencia real; quien lo declara es dwellFromWindow, no esta función.
func (r *replayer) placeAt(entry store.TrailEntry) (device.FenceState, string, time.Time) {
	if !r.req.UseCurrentFences {
		ev, ok := r.history.advance(entry.DeviceID, entry.At)
		if !ok {
			return device.Unknown, "", entry.At
		}
		state, id := parseKey(ev.To)
		return state, id, ev.At
	}
	punto := entry.Point
	state, id := transition.EvaluateFence(&punto, r.fences)
	key := transition.Key(id, state)
	if prev, ok := r.stance[entry.DeviceID]; ok && prev.key == key {
		return state, id, prev.since
	}
	r.stance[entry.DeviceID] = stance{key: key, since: entry.At}
	return state, id, entry.At
}

// dwellSeconds mide la estancia. Un reloj que va hacia atrás da cero, nunca un
// dwell negativo (misma regla que transition.Evaluate).
func dwellSeconds(since, at time.Time) int {
	s := int(at.Sub(since) / time.Second)
	if s < 0 {
		return 0
	}
	return s
}

// dwellField es el campo de permanencia. Solo se reconstruye entero en modo
// histórico, donde la transición fecha el inicio de la estancia.
const dwellField = "dwell_seconds"

// spatialFields son los campos que la simulación reconstruye del histórico. El
// resto se lee del estado ACTUAL del dispositivo sobre una posición pasada y
// convierte el resultado en una aproximación. risk_score y severity quedan
// fuera a propósito, a diferencia de 1.x: se recalculan, sí, pero con señales
// de postura y de inventario de hoy, así que presentarlos como exactos sería el
// mismo falso verde que el proyecto prohíbe.
//
// dwellField está en la lista porque no se lee del dispositivo de hoy: es
// pasado reconstruido, y en modo histórico es exacto. Que con las geocercas
// actuales se quede corto es otra cosa, y de eso se ocupa dwellFromWindow: la
// nota que le corresponde no es "se evalúa con el estado actual".
var spatialFields = map[string]bool{
	"fence_state":  true,
	"inside_fence": true,
	dwellField:     true,
}

// timeSignalPrefix marca las señales que sí se reconstruyen: time_of_day sale
// del instante del punto, no del reloj de ahora.
const timeSignalPrefix = "signal:time_of_day."

// nonSpatial devuelve, sin repetir y en el orden de la política, los campos que
// la simulación no puede reconstruir.
func nonSpatial(p policy.Policy) []string {
	out := []string{}
	seen := map[string]bool{}
	for _, c := range p.When {
		if spatialFields[c.Field] || strings.HasPrefix(c.Field, timeSignalPrefix) || seen[c.Field] {
			continue
		}
		seen[c.Field] = true
		out = append(out, c.Field)
	}
	return out
}

// dwellFromWindow dice si la permanencia se está midiendo desde la ventana
// simulada en vez de desde la entrada real. Pasa solo con UseCurrentFences: allí
// la clave de estado es hipotética, ninguna transición la fecha y placeAt mide
// la estancia por rachas sobre r.stance, que nace vacío en cada llamada, así que
// el "desde" más antiguo posible es el primer punto de la ventana y el reloj se
// reinicia además en cada cambio de clave que provoque la geocerca de hoy. El
// dwell sale corto y la política dispara MENOS aquí que en producción, que es la
// dirección que hace parecer inofensiva una regla destructiva. Si la política no
// mira dwell_seconds la diferencia no cambia ningún resultado y la simulación
// sigue siendo exacta.
func (r *replayer) dwellFromWindow() bool {
	if !r.req.UseCurrentFences {
		return false
	}
	for _, c := range r.req.Policy.When {
		if c.Field == dwellField {
			return true
		}
	}
	return false
}

// notes explica en español lo que los números no dicen: de dónde sale cada
// cosa, qué no se pudo reconstruir y por qué un cero puede no significar nada.
func (r *replayer) notes(fields []string, limit int) []string {
	out := []string{"Simulación de solo lectura: no se ejecutó ninguna acción."}
	dwellCorto := r.dwellFromWindow()
	if r.req.UseCurrentFences {
		out = append(out, "El estado de geocerca se recalculó con las geocercas actuales.")
	} else {
		out = append(out, "El estado de geocerca es el que registró el histórico de eventos.")
	}
	if dwellCorto {
		out = append(out, "Con las geocercas actuales la permanencia se cuenta desde el primer punto de la ventana simulada, no desde la entrada real: dwell_seconds se queda corto y la política puede disparar aquí menos veces que en producción.")
	}
	if len(fields) > 0 {
		out = append(out, "Aproximación: las condiciones sobre "+strings.Join(fields, ", ")+
			" se evalúan con el estado actual del dispositivo sobre posiciones históricas.")
	} else if !dwellCorto {
		out = append(out, "Simulación exacta: la política solo usa campos reconstruidos del histórico.")
	}
	if r.res.PointsEvaluated == 0 {
		out = append(out, "El histórico está vacío: no hay nada que simular, no es que la política no dispare.")
	}
	if r.unknown > 0 {
		out = append(out, fmt.Sprintf("%d puntos son de dispositivos que ya no están en el inventario: solo se evalúa su posición.", r.unknown))
	}
	if r.res.PointsEvaluated == limit {
		out = append(out, fmt.Sprintf("Ventana limitada a los últimos %d puntos: puede quedar histórico más antiguo sin simular.", limit))
	}
	return out
}
