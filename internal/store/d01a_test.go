package store

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestD01aSobreviveReaperturaDelStore(t *testing.T) {
	root := t.TempDir()
	st, err := Open(root)
	if err != nil {
		t.Fatal(err)
	}
	org, err := st.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	no := false
	wantDevices := []device.Device{
		{ID: "conocido", Posture: device.Posture{Rooted: &no, Country: "es", HardwareHealth: map[string]string{"disk": "ok"}}},
		{ID: "desconocido"},
	}
	wantAction := action.Result{DeviceID: "conocido", Action: action.Lock, DryRun: true, Simulated: true,
		At: time.Date(2026, 9, 7, 12, 0, 0, 0, time.UTC), RouteID: "r-1", PolicyID: "p-1", PlaybookID: "pb-1",
		Severity: "high", Blocked: true, ErrorType: "observe", Params: map[string]any{"message": "prueba local"}}
	if err := org.SaveDevices(wantDevices); err != nil {
		t.Fatal(err)
	}
	if err := org.AppendAction(wantAction); err != nil {
		t.Fatal(err)
	}
	st, err = Open(root)
	if err != nil {
		t.Fatal(err)
	}
	org, err = st.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	gotDevices, err := org.Devices()
	if err != nil || !reflect.DeepEqual(gotDevices, wantDevices) {
		t.Fatalf("postura conocida/desconocida alterada en disco: %+v, %v", gotDevices, err)
	}
	gotActions, err := org.RecentActions(10)
	if err != nil || !reflect.DeepEqual(gotActions, []action.Result{wantAction}) {
		t.Fatalf("trazas alteradas en JSONL: %+v, %v", gotActions, err)
	}
}
