package engine

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/notify"
)

// syncIncidents cierra el ciclo por el lado del operador: deriva los
// incidentes del estado de la flota y de los resultados de acción, los
// fusiona con incidents.json (que conserva el estado, la asignación, las
// notas y los sellos que puso una persona), persiste el resultado y devuelve
// un evento por cada apertura y cada cierre.
//
// Recibe la flota COMPLETA que se va a persistir, incluidos los dispositivos
// conservados de un conector caído (staleDevices): si solo viera los
// evaluados en este ciclo, una caída del proveedor cerraría en falso todos
// los incidentes de su flota y publicaría una tormenta de incident.closed.
func (e *Engine) syncIncidents(devices []device.Device, results []action.Result, now time.Time, st *CycleStats) []notify.Event {
	stored, err := e.org.Incidents()
	if err != nil {
		// Sin el fichero no se puede saber qué es nuevo: fusionar contra una
		// lista vacía reabriría y volvería a anunciar toda la bandeja. El
		// ciclo sigue, el fallo cuenta y health lo publica (M1-R11).
		e.logPersistenceError(st, "incidents", "", err)
		return nil
	}
	merged, opened, closed := incident.Merge(stored, incident.Derive(devices, results, now), now)
	if err := e.org.SaveIncidents(merged); err != nil {
		e.logPersistenceError(st, "incidents", "", err)
	}
	st.IncidentsOpened, st.IncidentsClosed = len(opened), len(closed)
	e.setOpenIncidents(pendientes(merged))
	evs := make([]notify.Event, 0, len(opened)+len(closed))
	for _, inc := range opened {
		evs = append(evs, incidentEvent(notify.EventIncidentOpened, inc, now))
	}
	for _, inc := range closed {
		evs = append(evs, incidentEvent(notify.EventIncidentClosed, inc, now))
	}
	return evs
}

// incidentEvent envuelve una copia del incidente: el evento viaja al Notifier
// y no comparte memoria con la lista que se acaba de guardar.
func incidentEvent(kind string, inc incident.Incident, at time.Time) notify.Event {
	cp := inc
	return notify.Event{Kind: kind, At: at, Incident: &cp}
}

// pendientes cuenta lo que el operador tiene por delante: abiertos y
// aceptados. Un incidente aceptado sigue siendo trabajo pendiente, así que
// entra en la cifra que publican /api/v1/engine/status y la bandeja.
func pendientes(is []incident.Incident) int {
	n := 0
	for _, inc := range is {
		if inc.Status != incident.StatusClosed {
			n++
		}
	}
	return n
}
