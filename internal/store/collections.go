package store

import (
	"errors"

	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/settings"
)

// Ficheros de M2 dentro de <data>/orgs/<org>/ (spec §5.5). Las cinco
// colecciones reutilizan los genéricos readCollection/writeCollection de M1:
// mismo envoltorio {schema_version, items}, misma escritura atómica y mismo
// contrato de "fichero ausente = lista vacía, nunca error". settings.json no
// es una colección: es un documento único con su propio schema_version.
const (
	policiesFile  = "policies.json"
	playbooksFile = "playbooks.json"
	alertsFile    = "alerts.json"
	incidentsFile = "incidents.json"
	handoffsFile  = "handoffs.json"
	settingsFile  = "settings.json"
)

// Policies lee las políticas de la organización.
func (o *OrgStore) Policies() ([]policy.Policy, error) {
	return readCollection[policy.Policy](o, policiesFile)
}

// SavePolicies escribe las políticas tal cual: validarlas es del handler.
func (o *OrgStore) SavePolicies(ps []policy.Policy) error {
	return writeCollection(o, policiesFile, ps)
}

// Playbooks lee los playbooks SOAR.
func (o *OrgStore) Playbooks() ([]playbook.Playbook, error) {
	return readCollection[playbook.Playbook](o, playbooksFile)
}

// SavePlaybooks escribe los playbooks SOAR.
func (o *OrgStore) SavePlaybooks(ps []playbook.Playbook) error {
	return writeCollection(o, playbooksFile, ps)
}

// Alerts lee las reglas de alerta.
func (o *OrgStore) Alerts() ([]alert.Rule, error) {
	return readCollection[alert.Rule](o, alertsFile)
}

// SaveAlerts escribe las reglas de alerta.
func (o *OrgStore) SaveAlerts(rs []alert.Rule) error {
	return writeCollection(o, alertsFile, rs)
}

// Incidents lee los incidentes persistidos (abiertos, reconocidos y cerrados).
func (o *OrgStore) Incidents() ([]incident.Incident, error) {
	return readCollection[incident.Incident](o, incidentsFile)
}

// SaveIncidents escribe los incidentes.
func (o *OrgStore) SaveIncidents(is []incident.Incident) error {
	return writeCollection(o, incidentsFile, is)
}

// Handoffs lee los handoffs del gate humano.
func (o *OrgStore) Handoffs() ([]playbook.Handoff, error) {
	return readCollection[playbook.Handoff](o, handoffsFile)
}

// SaveHandoffs escribe los handoffs.
func (o *OrgStore) SaveHandoffs(hs []playbook.Handoff) error {
	return writeCollection(o, handoffsFile, hs)
}

// Settings lee los ajustes de la organización. La primera vez, si el fichero
// no existe, siembra los de fábrica con la allowlist de egress de config.json
// y los deja escritos: a partir de ahí settings.json es la fuente de verdad y
// config.json ya no interviene. Un fichero ilegible devuelve error: no se
// re-siembra encima de lo que el operador haya escrito.
func (o *OrgStore) Settings() (settings.Settings, error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	var s settings.Settings
	err := ReadJSON(o.Path(settingsFile), &s)
	if errors.Is(err, ErrNotFound) {
		return o.seedSettings()
	}
	if err != nil {
		return settings.Settings{}, err
	}
	return s.Normalized(), nil
}

// seedSettings escribe los ajustes de fábrica. Se llama con o.mu tomado.
func (o *OrgStore) seedSettings() (settings.Settings, error) {
	s := settings.Default()
	s.Egress = o.defaultEgress
	s = s.Normalized()
	if err := WriteJSON(o.Path(settingsFile), s); err != nil {
		return settings.Settings{}, err
	}
	return s, nil
}

// SaveSettings normaliza, valida y escribe los ajustes. El reloj es del
// llamante: UpdatedAt se guarda tal cual llega.
func (o *OrgStore) SaveSettings(s settings.Settings) error {
	s = s.Normalized()
	if err := s.Validate(); err != nil {
		return err
	}
	o.mu.Lock()
	defer o.mu.Unlock()
	return WriteJSON(o.Path(settingsFile), s)
}
