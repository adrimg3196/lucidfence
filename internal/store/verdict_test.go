package store

import (
	"errors"
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

func TestVerdictsPreserveFailureAndEvidenceOnReopen(t *testing.T) {
	root := t.TempDir()
	st, err := Open(root)
	if err != nil {
		t.Fatal(err)
	}
	org, err := st.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	at := time.Date(2026, 9, 6, 12, 0, 0, 0, time.UTC)
	d := device.Device{ID: "observed", FenceState: device.Outside}
	sig := risk.Signals{"shift_match": {"shift_known": true, "shift_match": nil}, "location_integrity": {"checks": nil}}
	d.Signals = sig.Raw()
	d.Risk = risk.Evaluate(d, sig, at)
	want := []device.Device{d, {ID: "failed", Risk: risk.Failed(errors.New("fallo sintético"), at)}}
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
		t.Fatalf("%+v %v", got, err)
	}
	restored := risk.Signals{}
	for name, metric := range got[0].Signals {
		restored[name] = risk.Signal(metric)
	}
	if v, ok := restored.Value("shift_match", "shift_match"); v != nil || ok {
		t.Fatal("unknown lost")
	}
	if v := risk.Evaluate(got[0], restored, at); !reflect.DeepEqual(v, d.Risk) {
		t.Fatal(v)
	}
}
