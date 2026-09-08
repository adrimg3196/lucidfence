package risk

import (
	"reflect"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

var noon = time.Date(2026, 9, 6, 12, 0, 0, 0, time.UTC)

func ptr[T any](v T) *T { return &v }

func sig(d device.Device) Signals { return Compute(d, DefaultContext(noon)) }

func metric(t *testing.T, s Signals, name, key string, want any) {
	t.Helper()
	got, ok := s.Value(name, key)
	if !ok || !reflect.DeepEqual(got, want) {
		t.Fatalf("%s.%s = %#v (presente=%v), esperado %#v", name, key, got, ok, want)
	}
}

func absent(t *testing.T, s Signals, name, key string) {
	t.Helper()
	if got, ok := s.Value(name, key); ok {
		t.Fatalf("%s.%s desconocido, recibido %#v", name, key, got)
	}
}

func TestComputeSieteSenales(t *testing.T) {
	want := []string{"time_of_day", "shift_match", "device_health", "device_posture", "location_integrity", "zone_risk", "route_state"}
	if !reflect.DeepEqual(Names, want) {
		t.Fatalf("Names = %v", Names)
	}
	for _, d := range []device.Device{{}, {ID: "d", InsideFence: "hq"}} {
		for _, ctx := range []Context{{}, DefaultContext(noon)} {
			s := Compute(d, ctx)
			if len(s) != len(want) {
				t.Fatalf("señales = %v", s)
			}
			for _, name := range want {
				if s[name] == nil {
					t.Fatalf("falta %s", name)
				}
			}
		}
	}
}

func TestTimeOfDayJornadas(t *testing.T) {
	for _, window := range []struct{ start, end int }{{20, 7}, {10, 14}, {8, 8}, {0, 23}, {23, 0}, {-1, 7}, {20, 24}} {
		for hour := range 24 {
			start, end := window.start, window.end
			if start < 0 || end > 23 {
				start, end = 20, 7
			}
			want := hour >= start && hour < end
			if start > end {
				want = hour >= start || hour < end
			}
			ctx := Context{Now: time.Date(2026, 9, 6, hour, 59, 59, 0, time.FixedZone("local", 7200)), OffHoursStart: window.start, OffHoursEnd: window.end}
			s := Compute(device.Device{}, ctx)
			metric(t, s, "time_of_day", "hour", hour)
			metric(t, s, "time_of_day", "off_hours", want)
		}
	}
	ctx := DefaultContext(noon)
	if ctx.Now != noon || ctx.OffHoursStart != 20 || ctx.OffHoursEnd != 7 {
		t.Fatalf("defaults = %+v", ctx)
	}
	unknown := Compute(device.Device{}, Context{})
	absent(t, unknown, "time_of_day", "hour")
	metric(t, unknown, "time_of_day", "off_hours", false)
}

func TestShiftSoloDeclarado(t *testing.T) {
	d := device.Device{ID: "d", InsideFence: "hq"}
	for _, zones := range []map[string]string{nil, {}, {"other": "hq"}, {"d": "  "}} {
		s := Compute(d, Context{ShiftZones: zones})
		metric(t, s, "shift_match", "shift_known", false)
		absent(t, s, "shift_match", "shift_match")
	}
	for _, zone := range []string{"hq", " hq ", "away"} {
		s := Compute(d, Context{ShiftZones: map[string]string{"d": zone}})
		metric(t, s, "shift_match", "shift_known", true)
		metric(t, s, "shift_match", "shift_match", zone != "away")
	}
}
