package incident

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func boolPtr(v bool) *bool      { return &v }
func f64Ptr(v float64) *float64 { return &v }

func healthy() device.Device {
	return device.Device{
		ID: "dev-ok", Name: "Sano", Platform: "android", Compliant: boolPtr(true),
		FenceState: device.Inside, InsideFence: "demo-hq", RouteState: device.Unassigned,
		LastReportAt: t0,
	}
}

func TestDeriveDispositivoSanoNoGeneraNada(t *testing.T) {
	if got := Derive([]device.Device{healthy()}, nil, t0); len(got) != 0 {
		t.Fatalf("un dispositivo sano no abre incidentes: %+v", got)
	}
	if got := Derive([]device.Device{{Name: "sin id"}}, nil, t0); len(got) != 0 {
		t.Fatalf("un dispositivo sin id se ignora: %+v", got)
	}
}

func TestDeriveFueraYNoConformeEscalaAUnSoloCritico(t *testing.T) {
	d := healthy()
	d.ID, d.Name = "dev-1", "Tablet"
	d.Compliant = boolPtr(false)
	d.FenceState, d.InsideFence, d.LastInsideFence = device.Outside, "", "demo-hq"
	d.DwellSeconds = 900

	got := Derive([]device.Device{d}, nil, t0)
	if len(got) != 2 {
		t.Fatalf("el incumplimiento y la salida son dos hechos distintos: %+v", got)
	}
	if got[0].Kind != KindGeofenceExit || got[0].Severity != "critical" {
		t.Fatalf("la salida escala a critical cuando además no cumple: %+v", got[0])
	}
	if got[1].Kind != KindNonCompliant || got[1].Severity != "high" {
		t.Fatalf("el incumplimiento se queda en high: %+v", got[1])
	}
	criticals := 0
	for _, inc := range got {
		if inc.Severity == "critical" {
			criticals++
		}
	}
	if criticals != 1 {
		t.Fatalf("un solo incidente critical, no dos: %+v", got)
	}
	if got[0].ID != "inc-geofence_exit-dev-1" || got[0].FenceID != "demo-hq" {
		t.Fatalf("id determinista y última geocerca conocida: %+v", got[0])
	}
	if got[0].Evidence[0] != "fence_state=outside" || got[0].Evidence[2] != "dwell_seconds=900" {
		t.Fatalf("evidencias de la salida: %+v", got[0].Evidence)
	}
}

func TestDeriveIdsEstablesEntreDosDerivaciones(t *testing.T) {
	d := healthy()
	d.ID, d.Name = "dev-1", "Tablet"
	d.FenceState, d.InsideFence = device.Unknown, ""

	first := Derive([]device.Device{d}, nil, t0)
	second := Derive([]device.Device{d}, nil, t0.Add(24*time.Hour))
	if len(first) != 1 || len(second) != 1 {
		t.Fatalf("una condición, un incidente: %d y %d", len(first), len(second))
	}
	if first[0].ID != second[0].ID || first[0].ID != "inc-device_unknown_location-dev-1" {
		t.Fatalf("el id no puede depender del reloj: %q vs %q", first[0].ID, second[0].ID)
	}
	if first[0].Severity != "medium" {
		t.Fatalf("ubicación desconocida es medium: %q", first[0].Severity)
	}
	if !second[0].OpenedAt.Equal(t0.Add(24 * time.Hour)) {
		t.Fatalf("la marca temporal sí avanza: %s", second[0].OpenedAt)
	}
}

func TestDeriveRiesgoRutaEIntegridad(t *testing.T) {
	d := healthy()
	d.ID, d.Name = "dev-1", "Tablet"
	d.Risk = device.Verdict{Score: f64Ptr(91), Severity: "critical", Reasons: []string{"fuera de horario"}}
	d.RouteState, d.RouteID, d.RouteDeviationM = device.OffRoute, "ruta-norte", f64Ptr(420.5)
	d.LocationIntegrity = device.Integrity{Suspicious: true, Checks: []string{"impossible_speed"}, SpeedKMH: f64Ptr(1200)}

	got := Derive([]device.Device{d}, nil, t0)
	if len(got) != 3 {
		t.Fatalf("riesgo, ruta e integridad: %+v", got)
	}
	severities := map[string]string{}
	for _, inc := range got {
		severities[inc.Kind] = inc.Severity
	}
	if severities[KindHighRisk] != "critical" || severities[KindRouteDeviation] != "high" || severities[KindLocationIntegrity] != "high" {
		t.Fatalf("severidades: %+v", severities)
	}

	risky, _ := FindByID(got, "inc-high_risk_device-dev-1")
	if risky.RiskScore == nil || *risky.RiskScore != 91 {
		t.Fatalf("el score viaja al incidente: %+v", risky)
	}
	if risky.Evidence[0] != "risk_score=91" || risky.Evidence[2] != "motivo: fuera de horario" {
		t.Fatalf("evidencias del riesgo: %+v", risky.Evidence)
	}
	deviated, _ := FindByID(got, "inc-route_deviation-dev-1")
	if deviated.Evidence[0] != "route_id=ruta-norte" || deviated.Evidence[1] != "route_deviation_m=420.5" {
		t.Fatalf("evidencias de la ruta: %+v", deviated.Evidence)
	}
	suspect, _ := FindByID(got, "inc-location_integrity-dev-1")
	if suspect.Evidence[0] != "check=impossible_speed" || suspect.Evidence[1] != "speed_kmh=1200" {
		t.Fatalf("evidencias de integridad: %+v", suspect.Evidence)
	}
}

func TestDeriveRiesgoPorDebajoDelUmbralNoAbreIncidente(t *testing.T) {
	d := healthy()
	d.ID = "dev-1"
	d.Risk = device.Verdict{Score: f64Ptr(HighRiskScore - 0.1), Severity: "high"}
	if got := Derive([]device.Device{d}, nil, t0); len(got) != 0 {
		t.Fatalf("84.9 no llega a 85: %+v", got)
	}
	d.Risk = device.Verdict{Score: nil, Severity: "unknown"}
	if got := Derive([]device.Device{d}, nil, t0); len(got) != 0 {
		t.Fatalf("un riesgo desconocido no abre incidente: %+v", got)
	}
}

func TestDeriveAccionFallidaYAccionBloqueada(t *testing.T) {
	results := []action.Result{
		{DeviceID: "dev-1", DeviceName: "Tablet", Action: action.Lock, OK: false, Adapter: "simulation",
			ErrorType: "auth", Error: "401 unauthorized", At: t0},
		{DeviceID: "dev-2", DeviceName: "Otro", Action: action.Wipe, OK: false, Blocked: true, Error: "wipe_not_allowed", At: t0},
		{DeviceID: "dev-3", DeviceName: "Tres", Action: action.Message, OK: true, At: t0},
	}
	got := Derive(nil, results, t0)
	if len(got) != 1 {
		t.Fatalf("solo el fallo real abre incidente; un bloqueo de guardarraíl no: %+v", got)
	}
	inc := got[0]
	if inc.ID != "inc-automation_failed-dev-1-lock" || inc.Kind != KindActionFailed || inc.Severity != "medium" {
		t.Fatalf("incidente de acción fallida: %+v", inc)
	}
	if inc.Title != "Falló la acción lock en Tablet" {
		t.Fatalf("título: %q", inc.Title)
	}
	want := []string{"action=lock", "adapter=simulation", "error_type=auth", "error=401 unauthorized"}
	for i, w := range want {
		if inc.Evidence[i] != w {
			t.Fatalf("evidencia %d: %q want %q", i, inc.Evidence[i], w)
		}
	}
}

func TestDeriveIgnoraResultadosIncompletosYUsaElRelojDelCiclo(t *testing.T) {
	incomplete := []action.Result{{OK: false, Action: action.Lock}, {OK: false, DeviceID: "dev-9"}}
	if got := Derive(nil, incomplete, t0); len(got) != 0 {
		t.Fatalf("un resultado sin dispositivo o sin acción no abre incidente: %+v", got)
	}
	got := Derive(nil, []action.Result{{DeviceID: "dev-1", Action: action.Reboot}}, t0)
	if len(got) != 1 || !got[0].OpenedAt.Equal(t0) || got[0].DeviceName != "dev-1" {
		t.Fatalf("sin marca propia manda el reloj del ciclo y sin nombre manda el id: %+v", got)
	}
}

func TestDeriveDeduplicaPorId(t *testing.T) {
	d := healthy()
	d.ID, d.FenceState = "dev-1", device.Unknown
	if got := Derive([]device.Device{d, d}, nil, t0); len(got) != 1 {
		t.Fatalf("el mismo id no se repite: %+v", got)
	}
}
