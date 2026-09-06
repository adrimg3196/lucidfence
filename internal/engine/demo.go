package engine

import (
	"errors"
	"os"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
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
