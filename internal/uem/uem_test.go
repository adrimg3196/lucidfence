package uem

import (
	"context"
	"errors"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

type fake struct{ name string }

func (f fake) Name() string { return f.name }
func (f fake) Capabilities() Capabilities {
	return Capabilities{Actions: []action.Action{action.Message}}
}
func (f fake) FetchDevices(context.Context) ([]device.Device, error) { return nil, nil }
func (f fake) Execute(_ context.Context, d device.Device, a action.Action, _ map[string]any, dry bool) action.Result {
	return action.Result{Adapter: f.name, OK: true, DeviceID: d.ID, Action: a, DryRun: dry}
}
func (f fake) TestConnection(context.Context) ConnectionResult {
	return ConnectionResult{OK: true, Verified: "fake"}
}

func TestCapabilitiesSupports(t *testing.T) {
	c := Capabilities{Actions: []action.Action{action.Lock, action.Message}}
	if !c.Supports(action.Lock) || c.Supports(action.Wipe) {
		t.Fatal("Supports")
	}
}

func TestRegistry(t *testing.T) {
	r := NewRegistry()
	r.Register("zeta", func(map[string]any, map[string]string) (Adapter, error) { return fake{"zeta"}, nil })
	r.Register("alpha", func(map[string]any, map[string]string) (Adapter, error) { return fake{"alpha"}, nil })
	if names := r.Names(); len(names) != 2 || names[0] != "alpha" || names[1] != "zeta" {
		t.Fatalf("Names=%v", names)
	}
	a, err := r.New("alpha", nil, nil)
	if err != nil || a.Name() != "alpha" {
		t.Fatal(err)
	}
	if _, err := r.New("nope", nil, nil); !errors.Is(err, ErrUnknownProvider) {
		t.Fatalf("esperaba ErrUnknownProvider, got %v", err)
	}
	defer func() {
		if recover() == nil {
			t.Fatal("registrar dos veces debe hacer panic")
		}
	}()
	r.Register("alpha", nil)
}
