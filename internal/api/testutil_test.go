package api

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// fakeFleet es un uem.Adapter de prueba: depguard prohíbe a internal/api
// (tests incluidos) importar internal/uem/simulation, así que la flota demo
// vive aquí, con las mismas seis fichas que usaría un conector real.
type fakeFleet struct {
	now func() time.Time
}

func (f *fakeFleet) Name() string { return "fake" }

func (f *fakeFleet) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true}
}

func fakeDevice(id, name, platform string, lat, lng float64, inv device.Inventory, at time.Time) device.Device {
	return device.Device{
		ID: id, Name: name, Platform: platform, Provider: "fake", ProviderRefs: map[string]string{"fake": id},
		Location:  device.Location{Point: &geo.Point{Lat: lat, Lng: lng}, AccuracyM: ptrF(12), Source: "fake", ObservedAt: at},
		Inventory: inv, FenceState: device.Unknown, RouteState: device.Unassigned,
		Risk: device.Verdict{Reasons: []string{}, MatchedPolicies: []string{}}, LastReportAt: at,
	}
}

func ptrF(v float64) *float64 { return &v }

func (f *fakeFleet) FetchDevices(context.Context) ([]device.Device, error) {
	at := f.now()
	return []device.Device{
		fakeDevice("dev-001", "Tablet Campo A1", "android", 40.4205, -3.7085,
			device.Inventory{Model: "Samsung Galaxy Tab Active5", AssignedUser: "Lucía Fernández", Department: "Operaciones", OSVersion: "Android 14"}, at),
		fakeDevice("dev-002", "Móvil Reparto B7", "android", 40.4300, -3.6900,
			device.Inventory{Model: "Zebra TC22", AssignedUser: "Marcos Gil"}, at),
		fakeDevice("dev-003", "iPad Recepción", "ios", 40.4212, -3.7078,
			device.Inventory{Model: "iPad Air", AssignedUser: "Recepción"}, at),
		fakeDevice("dev-004", "Portátil Ventas", "macos", 40.4500, -3.6500,
			device.Inventory{Model: "MacBook Air M3", AssignedUser: "Sara López"}, at),
		fakeDevice("dev-005", "Escáner Almacén", "android", 40.4050, -3.7100,
			device.Inventory{Model: "Honeywell CT45"}, at),
		fakeDevice("dev-006", "Portátil Soporte", "windows", 40.4210, -3.7080,
			device.Inventory{Model: "Dell Latitude 5450", AssignedUser: "Diego Ruiz"}, at),
	}, nil
}

func (f *fakeFleet) Execute(_ context.Context, dev device.Device, a action.Action, params map[string]any, dryRun bool) action.Result {
	return action.Result{Adapter: "fake", OK: true, DeviceID: dev.ID, DeviceName: dev.Name, Action: a, Params: params,
		DryRun: dryRun, Simulated: true, CommandID: "fake-" + string(a), At: f.now()}
}

func (f *fakeFleet) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "fake"}
}

type testEnv struct {
	t      *testing.T
	srv    *httptest.Server
	auth   *auth.Store
	org    *store.OrgStore
	cookie *http.Cookie
	csrf   string
}

func newTestEnv(t *testing.T) *testEnv {
	t.Helper()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	// fakeFleet en vez de un conector real: internal/api nunca importa un
	// conector concreto, ni siquiera en tests (spec §5.2, depguard), pero los
	// handlers de dispositivos y motor sí necesitan un ciclo con flota real.
	return newTestEnvWithFleet(t, &fakeFleet{now: func() time.Time { return now }}, now)
}

// newTestEnvWithFleet es newTestEnv con un uem.Adapter propio: lo usan los
// tests que necesitan controlar cuándo termina un ciclo del motor (p. ej.
// para provocar de forma determinista un 409 cycle_in_progress).
func newTestEnvWithFleet(t *testing.T, fleet uem.Adapter, now time.Time) *testEnv {
	t.Helper()
	clock := func() time.Time { return now }
	st, _ := store.Open(t.TempDir())
	org, _ := st.Org("default")
	as, err := auth.Open(st.AuthDir(), clock)
	if err != nil {
		t.Fatal(err)
	}
	eng := engine.New(org, []uem.Adapter{fleet}, engine.Options{Mode: "simulation", Interval: time.Hour, Now: clock})
	h, _ := New(Deps{Engine: eng, Org: org, Auth: as, Web: http.NotFoundHandler(), Config: config.Default(), Now: clock})
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	return &testEnv{t: t, srv: srv, auth: as, org: org}
}

func (e *testEnv) do(method, path string, body any, authed bool) (*http.Response, map[string]any) {
	e.t.Helper()
	var buf bytes.Buffer
	if body != nil {
		_ = json.NewEncoder(&buf).Encode(body)
	}
	req, _ := http.NewRequest(method, e.srv.URL+path, &buf)
	req.Header.Set("Content-Type", "application/json")
	if authed && e.cookie != nil {
		req.AddCookie(e.cookie)
		req.Header.Set(CSRFHeader, e.csrf)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	_ = res.Body.Close()
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	return res, out
}

func (e *testEnv) setup(mode string) map[string]any {
	e.t.Helper()
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "adri@example.com", "name": "Adri", "password": "contraseña-larga-1", "mode": mode}, false)
	if res.StatusCode != 201 {
		e.t.Fatalf("setup: %d %v", res.StatusCode, out)
	}
	for _, c := range res.Cookies() {
		if c.Name == CookieName {
			e.cookie = c
		}
	}
	e.csrf, _ = out["csrf"].(string)
	if e.cookie == nil || e.csrf == "" {
		e.t.Fatalf("setup sin cookie/csrf: %v", out)
	}
	return out
}

func newRequest(e *testEnv, method, path string) (*http.Request, error) {
	return http.NewRequest(method, e.srv.URL+path, nil)
}

func send(e *testEnv, req *http.Request) (*http.Response, map[string]any) {
	e.t.Helper()
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	_ = res.Body.Close()
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	return res, out
}
