package device

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestValidateEIndex(t *testing.T) {
	if err := (Device{}).Validate(); err == nil {
		t.Fatal("id vacío debe fallar")
	}
	d := Device{ID: "dev-001", Name: "Tablet", Platform: "android"}
	if err := d.Validate(); err != nil {
		t.Fatal(err)
	}
	idx := Index([]Device{d, {ID: "dev-002"}})
	if len(idx) != 2 || idx["dev-001"].Name != "Tablet" {
		t.Fatal("Index")
	}
}

func TestJSONSnakeCaseYNullables(t *testing.T) {
	lvl := 87
	d := Device{ID: "dev-001", Name: "Tablet", Platform: "android", FenceState: Unknown, RouteState: Unassigned,
		Location:  Location{Point: &geo.Point{Lat: 40.42, Lng: -3.71}, Source: "simulation", ObservedAt: time.Date(2026, 9, 5, 0, 0, 0, 0, time.UTC)},
		Inventory: Inventory{BatteryLevel: &lvl, Model: "Galaxy Tab"},
		Risk:      Verdict{Reasons: []string{}, MatchedPolicies: []string{}}}
	b, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	for _, want := range []string{`"fence_state":"unknown"`, `"battery_level":87`, `"score":null`, `"observed_at":"2026-09-05T00:00:00Z"`, `"inside_fence":""`} {
		if !strings.Contains(s, want) {
			t.Fatalf("JSON %s sin %s", s, want)
		}
	}
	if strings.Contains(s, "FenceState") {
		t.Fatal("los campos deben ir en snake_case")
	}
}
