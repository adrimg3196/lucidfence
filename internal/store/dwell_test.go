package store

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

func TestDwellYSignalsSobrevivenReapertura(t *testing.T) {
	root := t.TempDir()
	st, err := Open(root)
	if err != nil {
		t.Fatal(err)
	}
	org, err := st.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	since := time.Date(2026, 9, 8, 8, 0, 0, 0, time.UTC)
	want := []device.Device{
		{ID: "conocido", FenceState: device.Unknown, FenceStateSince: &since, DwellSeconds: 90,
			Signals: map[string]map[string]any{"absent": nil, "posture": {"rooted": false, "score": float64(0), "unknown": nil}}},
		{ID: "M1"},
	}
	if err := org.SaveDevices(want); err != nil {
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
	got, err := org.Devices()
	if err != nil || !reflect.DeepEqual(got, want) {
		t.Fatalf("campos alterados al reabrir: %+v, %v", got, err)
	}
	cur := device.Device{ID: "conocido"}
	if tr := transition.Evaluate(&got[0], &cur, nil, since.Add(5*time.Minute)); tr != nil || cur.DwellSeconds != 300 {
		t.Fatalf("reiniciar proceso no reinicia reloj: %+v, %+v", cur, tr)
	}
}
