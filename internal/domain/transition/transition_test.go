package transition

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

var fences = []fence.Fence{
	{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500},
	{ID: "big", Name: "Ciudad", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 5000},
}

func TestEvaluateFencePrimeraGana(t *testing.T) {
	state, id := EvaluateFence(&geo.Point{Lat: 40.421, Lng: -3.708}, fences)
	if state != device.Inside || id != "demo-hq" {
		t.Fatalf("%s %s", state, id)
	}
	state, id = EvaluateFence(&geo.Point{Lat: 40.44, Lng: -3.708}, fences)
	if state != device.Inside || id != "big" {
		t.Fatalf("%s %s: a 2 km solo la grande contiene", state, id)
	}
	if state, _ := EvaluateFence(&geo.Point{Lat: 41, Lng: -3}, fences); state != device.Outside {
		t.Fatal("lejos: outside")
	}
	if state, id := EvaluateFence(nil, fences); state != device.Unknown || id != "" {
		t.Fatal("sin ubicación: unknown")
	}
}

func TestKey(t *testing.T) {
	if Key("", device.Unknown) != "none:unknown" || Key("demo-hq", device.Inside) != "demo-hq:inside" || Key("", device.Outside) != "none:outside" {
		t.Fatal("Key")
	}
}

func TestEvaluateFirstTransition(t *testing.T) {
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	cur := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 40.421, Lng: -3.708}}}
	tr := Evaluate(nil, &cur, fences, at)
	if tr == nil {
		t.Fatal("primera evaluación debería crear transición")
	}
	if tr.From != "none:unknown" || tr.To != "demo-hq:inside" {
		t.Fatalf("transición incorrecta: %s -> %s", tr.From, tr.To)
	}
	if tr.DeviceID != "dev-1" || !tr.At.Equal(at) {
		t.Fatal("DeviceID o At incorrecto")
	}
	if cur.FenceState != device.Inside || cur.InsideFence != "demo-hq" {
		t.Fatal("FenceState o InsideFence incorrecto")
	}
	if cur.LastInsideFence != "demo-hq" {
		t.Fatal("LastInsideFence debería ser demo-hq")
	}
}

func TestEvaluateNoTransitionSameKey(t *testing.T) {
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	prev := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 40.421, Lng: -3.708}},
		FenceState: device.Inside, InsideFence: "demo-hq", LastInsideFence: "demo-hq"}
	same := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 40.4212, Lng: -3.708}}}
	tr := Evaluate(&prev, &same, fences, at)
	if tr != nil {
		t.Fatalf("sin cambio de clave no hay transición: %+v", tr)
	}
}

func TestEvaluateToUnknownPreservesLastInside(t *testing.T) {
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	prev := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 40.4212, Lng: -3.708}},
		FenceState: device.Inside, InsideFence: "demo-hq", LastInsideFence: "demo-hq"}
	unknown := device.Device{ID: "dev-1", Name: "Uno"}
	tr := Evaluate(&prev, &unknown, fences, at)
	if tr == nil {
		t.Fatal("transición a unknown debería generar cambio")
	}
	if tr.To != "none:unknown" {
		t.Fatalf("debería ir a none:unknown, no a %s", tr.To)
	}
	if unknown.LastInsideFence != "demo-hq" {
		t.Fatalf("LastInsideFence debería conservarse, got %q", unknown.LastInsideFence)
	}
}

func TestEvaluateToOutside(t *testing.T) {
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	prev := device.Device{ID: "dev-1", Name: "Uno",
		FenceState: device.Unknown, InsideFence: "", LastInsideFence: "demo-hq"}
	out := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 41, Lng: -3}}}
	tr := Evaluate(&prev, &out, fences, at)
	if tr == nil {
		t.Fatal("transición a outside debería generar cambio")
	}
	if tr.From != "none:unknown" || tr.To != "none:outside" {
		t.Fatalf("transición incorrecta: %s -> %s", tr.From, tr.To)
	}
	if out.LastInsideFence != "" {
		t.Fatalf("LastInsideFence debería limpiarse, got %q", out.LastInsideFence)
	}
}
