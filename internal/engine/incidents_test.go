package engine

import (
	"context"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/incident"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// dentroHQ es el centro de demo-hq (radio 500 m) y fueraHQ un punto a más de
// 8 km, fuera de las dos geocercas de la fixture demo.
var (
	dentroHQ = geo.Point{Lat: 40.421, Lng: -3.708}
	fueraHQ  = geo.Point{Lat: 40.500, Lng: -3.600}
)

// incidenteFuera es el id determinista que incident.Derive (T5) da a la
// salida de geocerca de dev-movil: "inc-<tipo>-<device_id>".
const incidenteFuera = "inc-" + incident.KindGeofenceExit + "-dev-movil"

// flotaMovil es un conector de un solo dispositivo al que se le puede cambiar
// la posición entre ciclos: es lo mínimo para observar el ciclo de vida
// completo de un incidente (abrir en un ciclo, cerrar en el siguiente).
type flotaMovil struct {
	dev device.Device
}

func nuevaFlotaMovil(p geo.Point) *flotaMovil {
	return &flotaMovil{dev: device.Device{
		ID: "dev-movil", Name: "Tablet móvil", Platform: "android", Provider: "movil",
		Location:   device.Location{Point: &p, Source: "movil"},
		FenceState: device.Unknown, RouteState: device.Unassigned,
	}}
}

func (f *flotaMovil) mover(p geo.Point) { f.dev.Location.Point = &p }

func (f *flotaMovil) Name() string { return "movil" }

func (f *flotaMovil) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true}
}

// FetchDevices copia el punto: el motor muta lo que recibe y el conector no
// puede quedarse con el estado de un ciclo anterior.
func (f *flotaMovil) FetchDevices(context.Context) ([]device.Device, error) {
	d := f.dev
	p := *d.Location.Point
	d.Location.Point = &p
	return []device.Device{d}, nil
}

func (f *flotaMovil) Execute(_ context.Context, d device.Device, a action.Action, params map[string]any, dryRun bool) action.Result {
	return action.Result{Adapter: "movil", OK: true, DeviceID: d.ID, DeviceName: d.Name, Action: a,
		Params: params, DryRun: dryRun, Simulated: true}
}

func (f *flotaMovil) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "simulated"}
}

// incidenteGuardado lee el incidente de salida de dev-movil de
// incidents.json, no de memoria: el round-trip por JSON es parte de lo que se
// comprueba. Los tres tests de este fichero solo derivan ese incidente, así
// que el id no es un parámetro: unparam lo marcaría muerto.
func incidenteGuardado(t *testing.T, org *store.OrgStore) incident.Incident {
	t.Helper()
	is, err := org.Incidents()
	if err != nil {
		t.Fatal(err)
	}
	inc, ok := incident.FindByID(is, incidenteFuera)
	if !ok {
		t.Fatalf("incidents.json debe contener %s: %+v", incidenteFuera, is)
	}
	return inc
}

// transitar aplica y persiste la transición que haría una persona desde la
// API (T19). Es justo el trabajo que el ciclo no puede pisar.
func transitar(t *testing.T, org *store.OrgStore, id string, to incident.Status, nota string) {
	t.Helper()
	is, err := org.Incidents()
	if err != nil {
		t.Fatal(err)
	}
	for i, inc := range is {
		if inc.ID != id {
			continue
		}
		upd, err := inc.Transition(to, "usr-soc", "soc@acme.test", nota, inc.UpdatedAt.Add(time.Minute))
		if err != nil {
			t.Fatal(err)
		}
		is[i] = upd
	}
	if err := org.SaveIncidents(is); err != nil {
		t.Fatal(err)
	}
}

// TestElCicloAbreYCierraElIncidenteDeSalidaDeGeocerca cubre el ciclo de vida
// automático: la condición aparece y abre, desaparece y cierra sola con su
// entrada de auditoría.
func TestElCicloAbreYCierraElIncidenteDeSalidaDeGeocerca(t *testing.T) {
	ad := nuevaFlotaMovil(fueraHQ)
	e, org := newEngine(t, ad)

	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.IncidentsOpened == 0 || st.IncidentsClosed != 0 {
		t.Fatalf("el primer ciclo abre el incidente de salida y no cierra nada: %+v", st)
	}
	abierto := incidenteGuardado(t, org)
	if abierto.Status != incident.StatusOpen || abierto.DeviceID != "dev-movil" || abierto.Count != 1 {
		t.Fatalf("incidente recién abierto: %+v", abierto)
	}
	if e.Status().Incidents == 0 {
		t.Fatalf("el estado del motor publica los incidentes sin cerrar: %+v", e.Status())
	}

	ad.mover(dentroHQ)
	st, err = e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.IncidentsClosed == 0 {
		t.Fatalf("volver dentro cierra el incidente de salida: %+v", st)
	}
	cerrado := incidenteGuardado(t, org)
	if cerrado.Status != incident.StatusClosed || cerrado.ClosedAt == nil {
		t.Fatalf("el incidente debe quedar cerrado y sellado: %+v", cerrado)
	}
	if len(cerrado.Timeline) == 0 {
		t.Fatalf("el cierre automático deja entrada de auditoría: %+v", cerrado)
	}
}

// TestUnIncidenteAceptadoSobreviveALosCiclos es el caso dorado de
// legacy/tests/test_incidents.py::test_incident_lifecycle_persists_and_records_audit:
// el ciclo refresca los hechos y jamás pisa el estado, la asignación ni la
// auditoría que puso una persona.
func TestUnIncidenteAceptadoSobreviveALosCiclos(t *testing.T) {
	ad := nuevaFlotaMovil(fueraHQ)
	e, org := newEngine(t, ad)
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	transitar(t, org, incidenteFuera, incident.StatusAck, "Investigando")

	for i := 1; i <= 2; i++ {
		st, err := e.RunOnce(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if st.IncidentsOpened != 0 {
			t.Fatalf("ciclo %d: la condición ya tenía incidente, no se abre otro: %+v", i, st)
		}
	}

	inc := incidenteGuardado(t, org)
	if inc.Status != incident.StatusAck || inc.Assignee != "soc@acme.test" || inc.AckedAt == nil {
		t.Fatalf("el ciclo no puede pisar lo que puso el operador: %+v", inc)
	}
	if inc.Count != 3 {
		t.Fatalf("cada ciclo que vuelve a observar la condición suma una repetición: %+v", inc)
	}
	if len(inc.Timeline) != 1 || inc.Timeline[0].To != string(incident.StatusAck) {
		t.Fatalf("la auditoría conserva la única transición humana: %+v", inc.Timeline)
	}
}

// TestUnIncidenteCerradoAManoNoSeReabre es el caso dorado de
// legacy/tests/test_incidents.py::test_resolved_incident_reopens_when_risk_reappears_only_when_requested:
// reabrir es una decisión de una persona, nunca un efecto secundario de que
// la condición se siga observando.
func TestUnIncidenteCerradoAManoNoSeReabre(t *testing.T) {
	ad := nuevaFlotaMovil(fueraHQ)
	e, org := newEngine(t, ad)
	if _, err := e.RunOnce(context.Background()); err != nil {
		t.Fatal(err)
	}
	transitar(t, org, incidenteFuera, incident.StatusClosed, "Dispositivo recuperado")

	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.IncidentsOpened != 0 || st.IncidentsClosed != 0 {
		t.Fatalf("un cerrado que se vuelve a derivar no abre ni cierra nada: %+v", st)
	}
	inc := incidenteGuardado(t, org)
	if inc.Status != incident.StatusClosed || inc.ClosedAt == nil {
		t.Fatalf("sigue cerrado: %+v", inc)
	}
	if inc.Count != 2 {
		t.Fatalf("cerrado no es invisible: el ciclo sigue contando la repetición: %+v", inc)
	}
}
