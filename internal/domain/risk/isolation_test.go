package risk

import (
	"reflect"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func TestComputeAislaCadaProveedor(t *testing.T) {
	baseline := sig(device.Device{})
	for _, broken := range Names {
		t.Run(broken, func(t *testing.T) {
			original := providers[broken]
			if original == nil {
				t.Fatal("proveedor de producción ausente")
			}
			t.Cleanup(func() { providers[broken] = original })
			for _, replacement := range []func(device.Device, Context) Signal{
				nil,
				func(device.Device, Context) Signal { return nil },
				func(device.Device, Context) Signal { panic("fallo sintético") },
				func(device.Device, Context) Signal { panic(nil) },
			} {
				providers[broken] = replacement
				got := sig(device.Device{})
				if got[broken] == nil || len(got[broken]) != 0 {
					t.Fatalf("fallo debe quedar vacío, no null: %v", got)
				}
				if len(got) != len(Names) {
					t.Fatalf("se perdió señal: %v", got)
				}
				for _, name := range Names {
					if name != broken && !reflect.DeepEqual(got[name], baseline[name]) {
						t.Fatalf("%s afectó a %s", broken, name)
					}
				}
			}
		})
	}
}

func TestComputeOrdenEstable(t *testing.T) {
	original := providers
	t.Cleanup(func() { providers = original })
	providers = make(map[string]func(device.Device, Context) Signal, len(Names))
	var order []string
	for _, name := range Names {
		providers[name] = func(device.Device, Context) Signal {
			order = append(order, name)
			return Signal{}
		}
	}
	Compute(device.Device{}, Context{})
	if !reflect.DeepEqual(order, Names) {
		t.Fatalf("orden: %v", order)
	}
}
