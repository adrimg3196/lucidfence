package engine

import (
	"errors"
	"os"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/alert"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
)

// SeedDemo escribe los datos demo (geocercas, ruta, POIs y seed) solo donde
// no exista nada; es idempotente y nunca sobrescribe.
func SeedDemo(org *store.OrgStore, now time.Time) error {
	if fs, err := org.Fences(); err != nil {
		return err
	} else if len(fs) == 0 {
		if err := org.SaveFences(demoFences(now)); err != nil {
			return err
		}
	}
	if rs, err := org.Routes(); err != nil {
		return err
	} else if len(rs) == 0 {
		if err := org.SaveRoutes(demoRoutes(now)); err != nil {
			return err
		}
	}
	if ps, err := org.POIs(); err != nil {
		return err
	} else if len(ps) == 0 {
		if err := org.SavePOIs(demoPOIs()); err != nil {
			return err
		}
	}
	if err := seedAutomation(org, now); err != nil {
		return err
	}
	if _, err := os.Stat(org.Path("seed.json")); errors.Is(err, os.ErrNotExist) {
		return simulation.SaveSeed(org.Path("seed.json"), simulation.DefaultSeed())
	}
	return nil
}

func demoFences(now time.Time) []fence.Fence {
	return []fence.Fence{
		{ID: "demo-hq", Name: "Demo HQ · Madrid", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
			Actions: []fence.Action{
				{Action: action.Message, When: fence.OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido a la Oficina HQ."}},
				{Action: action.Notify, When: fence.OnExit, Enabled: true, Params: map[string]any{"channel": "security", "msg": "Dispositivo ha salido de HQ"}},
			}, CreatedAt: now, UpdatedAt: now},
		{ID: "warehouse-poly", Name: "Almacén Sur", Kind: fence.Polygon,
			Polygon: []geo.Point{{Lat: 40.4030, Lng: -3.7140}, {Lat: 40.4030, Lng: -3.7080}, {Lat: 40.4080, Lng: -3.7080}, {Lat: 40.4080, Lng: -3.7140}},
			Actions: []fence.Action{{Action: action.Locate, When: fence.OnExit, Enabled: true}}, CreatedAt: now, UpdatedAt: now},
	}
}

func demoRoutes(now time.Time) []route.Route {
	return []route.Route{{ID: "route-centro", Name: "Ruta Comercial Centro", CorridorM: 300, DeviceIDs: []string{"dev-002"}, Color: "#3E7A5E",
		Waypoints: []geo.Point{{Lat: 40.4300, Lng: -3.6900}, {Lat: 40.4250, Lng: -3.7000}, {Lat: 40.4210, Lng: -3.7080}},
		Actions:   []fence.Action{{Action: action.Notify, When: fence.OnExit, Enabled: true, Params: map[string]any{"channel": "security", "msg": "Comercial fuera de la ruta asignada"}}},
		CreatedAt: now, UpdatedAt: now}}
}

func demoPOIs() []poi.POI {
	return []poi.POI{
		{ID: "poi-school-001", Name: "Colegio Público", Category: "school", Tags: []string{"education"}, Point: geo.Point{Lat: 40.418, Lng: -3.705}},
		{ID: "poi-hospital-001", Name: "Hospital Central", Category: "hospital", Tags: []string{"health"}, Point: geo.Point{Lat: 40.425, Lng: -3.700}},
	}
}

// seedAutomation siembra la automatización del modo demo: dos plantillas de
// política activadas, los tres playbooks de fábrica, una regla de alerta de
// riesgo alto y settings.json en observe. Como el resto de SeedDemo, solo
// escribe donde no hay nada.
func seedAutomation(org *store.OrgStore, now time.Time) error {
	if ps, err := org.Policies(); err != nil {
		return err
	} else if len(ps) == 0 {
		if err := org.SavePolicies(demoPolicies(now)); err != nil {
			return err
		}
	}
	if pbs, err := org.Playbooks(); err != nil {
		return err
	} else if len(pbs) == 0 {
		if err := org.SavePlaybooks(demoPlaybooks(now)); err != nil {
			return err
		}
	}
	if rs, err := org.Alerts(); err != nil {
		return err
	} else if len(rs) == 0 {
		if err := org.SaveAlerts(demoAlerts(now)); err != nil {
			return err
		}
	}
	return seedRiskSettings(org)
}

// seedRiskSettings deja el contexto de riesgo de la demo en settings.json.
// Settings() siembra los ajustes de fábrica (observe, jornada 20-7) la primera
// vez que se leen y no toca nada si el fichero ya existe; sobre ellos, y solo
// si el operador no ha configurado ninguna zona ni ningún turno, se añaden el
// riesgo del almacén y el turno de dev-004. Sin esta siembra las señales
// zone_risk y shift_match valdrían siempre lo neutro en el binario, porque el
// bloque risk de los ajustes no tiene PUT propio en M2 (T21) y nadie más lo
// escribe. La zona es warehouse-poly y no demo-hq a propósito: así el riesgo
// de zona se ve en dev-005 sin puntuar al dispositivo sano de referencia.
func seedRiskSettings(org *store.OrgStore) error {
	set, err := org.Settings()
	if err != nil {
		return err
	}
	if len(set.Risk.ZoneRisk) > 0 || len(set.Risk.ShiftZones) > 0 {
		return nil
	}
	set.Risk.ZoneRisk = map[string]float64{"warehouse-poly": 0.5}
	set.Risk.ShiftZones = map[string]string{"dev-004": "demo-hq"}
	return org.SaveSettings(set)
}

// demoTemplateIDs son las dos plantillas que la demo trae activadas. Ninguna
// es destructiva: notifican, mandan un mensaje o piden localización, de modo
// que el modo demo enseña la automatización sin poder tocar un dispositivo.
var demoTemplateIDs = map[string]bool{
	"tpl-block-on-route-exit":         true,
	"tpl-locate-unknown-noncompliant": true,
}

func demoPolicies(now time.Time) []policy.Policy {
	out := []policy.Policy{}
	for _, p := range policy.Templates() {
		if !demoTemplateIDs[p.ID] {
			continue
		}
		p.CreatedAt, p.UpdatedAt = now, now
		out = append(out, p)
	}
	return out
}

// demoAlerts es la regla que dispara con la propia flota demo: dev-004 está
// fuera, no es conforme, no va cifrado y trae la postura comprometida de la
// seed, así que satura el score en 100.
func demoAlerts(now time.Time) []alert.Rule {
	return []alert.Rule{{
		ID:        "alert-riesgo-alto",
		Name:      "Riesgo alto en la flota",
		Kind:      alert.KindRiskAbove,
		Threshold: 70,
		Severity:  risk.SeverityHigh,
		Enabled:   true,
		CreatedAt: now,
		UpdatedAt: now,
	}}
}

// demoPlaybooks son los tres playbooks de fábrica de T6 sellados con el reloj
// de la siembra. La demo los trae activados para que un solo ciclo deje una
// petición esperando a una persona (dev-004 está fuera de geocerca y no es
// conforme), que es lo que enseña la bandeja de aprobaciones. Ninguno de ellos
// puede tocar un dispositivo por su cuenta: el lock del primero es
// destructivo, así que abre handoff en vez de ejecutarse.
func demoPlaybooks(now time.Time) []playbook.Playbook {
	out := playbook.Defaults()
	for i := range out {
		out[i].CreatedAt, out[i].UpdatedAt = now, now
	}
	return out
}
