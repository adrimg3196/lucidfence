package store

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

// cooldownsFile guarda la última ejecución por clave "<device>|<action>".
const cooldownsFile = "cooldowns.json"

// cooldowns es el documento persistido:
// {"schema_version":1,"entries":{"<device>|<action>":"<RFC3339>"}}.
// La marca se guarda como cadena RFC 3339 en UTC con resolución de segundo:
// el cooldown se configura en segundos (settings.Enforcement.ActionCooldownSeconds),
// así que no hay nada que ganar guardando nanosegundos y el fichero queda
// legible para un operador.
type cooldowns struct {
	SchemaVersion int               `json:"schema_version"`
	Entries       map[string]string `json:"entries"`
}

// cooldownKey compone la clave de 1.x
// (lucidfence/core/state_store.py::last_action_at).
func cooldownKey(deviceID string, a action.Action) string {
	return deviceID + "|" + string(a)
}

// loadCooldowns lee el documento; el llamante ya tiene el lock. Un fichero
// ausente o corrupto equivale a "sin marcas": la memoria de cooldown nunca
// debe impedir que el motor arranque.
func (o *OrgStore) loadCooldowns() cooldowns {
	var c cooldowns
	if err := ReadJSON(o.Path(cooldownsFile), &c); err != nil || c.Entries == nil {
		c.Entries = map[string]string{}
	}
	return c
}

// saveCooldowns escribe el documento de forma atómica; el llamante ya tiene
// el lock.
func (o *OrgStore) saveCooldowns(c cooldowns) error {
	c.SchemaVersion = schemaVersion
	if c.Entries == nil {
		c.Entries = map[string]string{}
	}
	return WriteJSON(o.Path(cooldownsFile), c)
}

// LastActionAt devuelve el instante de la última ejecución registrada de
// (dispositivo, acción). El booleano es el único discriminante: una acción
// nunca ejecutada devuelve (time.Time{}, false), no un cero ambiguo.
func (o *OrgStore) LastActionAt(deviceID string, a action.Action) (time.Time, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	raw, ok := o.loadCooldowns().Entries[cooldownKey(deviceID, a)]
	if !ok {
		return time.Time{}, false
	}
	at, err := time.Parse(time.RFC3339, raw)
	if err != nil {
		return time.Time{}, false
	}
	return at.UTC(), true
}

// RecordActionAt registra la ejecución de (dispositivo, acción). La marca
// sobrevive al reinicio del proceso: es la parte "cooldown not persisted
// across restart" del caso dorado de 1.x.
func (o *OrgStore) RecordActionAt(deviceID string, a action.Action, at time.Time) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	c := o.loadCooldowns()
	c.Entries[cooldownKey(deviceID, a)] = at.UTC().Format(time.RFC3339)
	return o.saveCooldowns(c)
}

// PruneCooldowns borra las marcas anteriores a before para que el fichero no
// crezca sin fin; una marca ilegible se borra también. Si no hay nada que
// borrar no escribe, y por tanto no crea el fichero si no existía.
func (o *OrgStore) PruneCooldowns(before time.Time) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	c := o.loadCooldowns()
	removed := 0
	for k, raw := range c.Entries {
		at, err := time.Parse(time.RFC3339, raw)
		if err == nil && !at.Before(before) {
			continue
		}
		delete(c.Entries, k)
		removed++
	}
	if removed == 0 {
		return nil
	}
	return o.saveCooldowns(c)
}
