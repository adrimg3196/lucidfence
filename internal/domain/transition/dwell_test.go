package transition

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Se inspecciona el contrato JSON para que el RED compile también sobre M1.
func requireDwell(t *testing.T, d device.Device, since time.Time, seconds int) {
	t.Helper()
	b, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	var clock struct {
		Since   *time.Time `json:"fence_state_since"`
		Seconds *int       `json:"dwell_seconds"`
	}
	if err := json.Unmarshal(b, &clock); err != nil {
		t.Fatal(err)
	}
	if clock.Since == nil || !clock.Since.Equal(since) || clock.Seconds == nil || *clock.Seconds != seconds {
		t.Fatalf("reloj esperado %s / %d segundos; JSON: %s", since, seconds, b)
	}
}

func TestDwellRelojPrevioAusenteCeroYFuturo(t *testing.T) {
	at := time.Date(2026, 9, 8, 8, 0, 0, 0, time.UTC)
	zero, future, past := time.Time{}, at.Add(time.Hour), at.Add(-1500*time.Millisecond)
	for _, tc := range []struct {
		name    string
		origin  *time.Time
		want    time.Time
		seconds int
	}{
		{"M1 sin reloj", nil, at, 0},
		{"origen cero no es evidencia", &zero, at, 0},
		{"retroceso no negativo", &future, future, 0},
		{"segundos completos", &past, past, 1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			prev := device.Device{FenceState: device.Inside, InsideFence: "demo-hq", FenceStateSince: tc.origin, DwellSeconds: 999}
			cur := device.Device{Location: device.Location{Point: &geo.Point{Lat: 40.421, Lng: -3.708}}}
			if tr := Evaluate(&prev, &cur, fences, at); tr != nil {
				t.Fatalf("misma clave: %+v", tr)
			}
			requireDwell(t, cur, tc.want, tc.seconds)
			if tc.origin != nil && cur.FenceStateSince == tc.origin {
				t.Fatal("el origen no debe compartir memoria mutable con prev")
			}
		})
	}
}

func TestDwellCambiosDeClaveYUnknown(t *testing.T) {
	t0 := time.Date(2026, 9, 8, 8, 0, 0, 0, time.UTC)
	hq, big, outside := &geo.Point{Lat: 40.421, Lng: -3.708}, &geo.Point{Lat: 40.44, Lng: -3.708}, &geo.Point{Lat: 41, Lng: -3}
	invalid := &geo.Point{Lat: 91}
	var prev *device.Device
	for i, tc := range []struct {
		point           *geo.Point
		key, last       string
		origin, seconds int
		transition      bool
	}{
		{nil, "none:unknown", "", 0, 0, false},
		{invalid, "none:unknown", "", 0, 60, false},
		{hq, "demo-hq:inside", "demo-hq", 2, 0, true},
		{big, "big:inside", "big", 3, 0, true},
		{nil, "none:unknown", "big", 4, 0, true},
		{nil, "none:unknown", "big", 4, 60, false},
		{outside, "none:outside", "", 6, 0, true},
		{outside, "none:outside", "", 6, 60, false},
		{hq, "demo-hq:inside", "demo-hq", 8, 0, true},
	} {
		cur := device.Device{ID: "secuencia", Location: device.Location{Point: tc.point}}
		tr := Evaluate(prev, &cur, fences, t0.Add(time.Duration(i)*time.Minute))
		if (tr != nil) != tc.transition || Key(cur.InsideFence, cur.FenceState) != tc.key || cur.LastInsideFence != tc.last {
			t.Fatalf("paso %d: transición=%+v estado=%+v", i, tr, cur)
		}
		requireDwell(t, cur, t0.Add(time.Duration(tc.origin)*time.Minute), tc.seconds)
		prev = &cur
	}
}

func TestDwellArrancaYAcumulaDesdeElRelojDelCiclo(t *testing.T) {
	t0 := time.Date(2026, 9, 8, 8, 0, 0, 0, time.UTC)
	var prev *device.Device
	for _, seconds := range []int{0, 90, 300} {
		cur := device.Device{ID: "reloj", Location: device.Location{
			Point: &geo.Point{Lat: 40.421, Lng: -3.708}, ObservedAt: t0.Add(-24 * time.Hour),
		}}
		tr := Evaluate(prev, &cur, fences, t0.Add(time.Duration(seconds)*time.Second))
		if (tr != nil) != (prev == nil) {
			t.Fatalf("solo el primer ciclo debe generar transición: %+v", tr)
		}
		requireDwell(t, cur, t0, seconds)
		prev = &cur
	}
}
