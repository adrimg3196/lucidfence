package store

import "errors"

// dwellMarksFile guarda, por clave "<device>|<fence>", el instante de inicio
// de la estancia cuyo on_enter por permanencia ya se emitió. Es el equivalente
// del dwell.json de 1.x (lucidfence/core/state_store.py::_persist_dwell): sin
// él, reiniciar el proceso repite ese on_enter en toda estancia que ya hubiera
// superado su umbral.
const dwellMarksFile = "dwell.json"

// dwellMarks es el documento persistido:
// {"schema_version":1,"entries":{"<device>|<fence>":"<RFC3339Nano>"}}.
// El valor es el fence_state_since de la estancia tal como lo formatea el
// motor (engine.stayOf), no una marca de "cuándo se disparó": comparar el
// inicio de la estancia es lo que distingue una estancia de la siguiente.
type dwellMarks struct {
	SchemaVersion int               `json:"schema_version"`
	Entries       map[string]string `json:"entries"`
}

// DwellMarks devuelve las marcas de estancia persistidas, nunca nil. Un
// fichero ausente es el primer arranque y no dice nada; uno corrupto o
// ilegible se avisa antes de seguir sin marcas, con el mismo criterio que
// loadCooldowns (ruling M2-R21): fallar en abierto y hacerlo en silencio son
// dos decisiones distintas, y aquí solo la primera está justificada, porque el
// precio de perder las marcas es una orden repetida sobre un dispositivo.
func (o *OrgStore) DwellMarks() map[string]string {
	o.mu.RLock()
	defer o.mu.RUnlock()
	var m dwellMarks
	err := ReadJSON(o.Path(dwellMarksFile), &m)
	if err != nil && !errors.Is(err, ErrNotFound) {
		o.logger.Warn("marcas de estancia ilegibles: se sigue sin marcas y el motor puede repetir un on_enter por permanencia",
			"fichero", o.Path(dwellMarksFile), "error", err)
	}
	if err != nil || m.Entries == nil {
		return map[string]string{}
	}
	return m.Entries
}

// SaveDwellMarks reemplaza el documento entero de forma atómica: el motor pasa
// su mapa completo, así que una clave que ya no está es una estancia que
// terminó. Copia el mapa porque el motor sigue siendo su dueño y lo muta en el
// ciclo siguiente.
func (o *OrgStore) SaveDwellMarks(entries map[string]string) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	cp := make(map[string]string, len(entries))
	for k, v := range entries {
		cp[k] = v
	}
	return WriteJSON(o.Path(dwellMarksFile), dwellMarks{SchemaVersion: schemaVersion, Entries: cp})
}
