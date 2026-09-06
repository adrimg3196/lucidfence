package api

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

func mustPanic(t *testing.T, name string, fn func()) {
	t.Helper()
	defer func() {
		if recover() == nil {
			t.Fatalf("%s: esperaba panic", name)
		}
	}()
	fn()
}

func TestRegistryInvariantes(t *testing.T) {
	reg := NewRegistry()
	reg.Add(Route{Method: "GET", Path: "/api/v1/devices", Cap: auth.DeviceRead})
	reg.Add(Route{Method: "GET", Path: "/api/v1/health", Public: true})
	if len(reg.Routes()) != 2 {
		t.Fatal("dos rutas")
	}
	mustPanic(t, "sin capacidad", func() { reg.Add(Route{Method: "GET", Path: "/api/v1/x"}) })
	mustPanic(t, "duplicada", func() { reg.Add(Route{Method: "GET", Path: "/api/v1/devices", Cap: auth.DeviceRead}) })
	mustPanic(t, "fuera de /api/v1", func() { reg.Add(Route{Method: "GET", Path: "/devices", Cap: auth.DeviceRead}) })
}
