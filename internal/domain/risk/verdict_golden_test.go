package risk

import (
	"encoding/json"
	"os"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/google/go-cmp/cmp"
)

func TestTablaDoradaDeVeredictos(t *testing.T) {
	data, err := os.ReadFile("testdata/verdicts.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		SchemaVersion int `json:"schema_version"`
		Cases         []struct {
			Name    string        `json:"name"`
			Device  device.Device `json:"device"`
			Context struct {
				Now        time.Time          `json:"now"`
				ShiftZones map[string]string  `json:"shift_zones"`
				ZoneRisk   map[string]float64 `json:"zone_risk"`
			} `json:"context"`
			Want device.Verdict `json:"want"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(data, &fixture); err != nil {
		t.Fatal(err)
	}
	if fixture.SchemaVersion != 1 || len(fixture.Cases) != 10 {
		t.Fatalf("fixture: version=%d cases=%d", fixture.SchemaVersion, len(fixture.Cases))
	}
	names := map[string]bool{}
	for _, tc := range fixture.Cases {
		if names[tc.Name] {
			t.Fatalf("duplicate %s", tc.Name)
		}
		names[tc.Name] = true
		t.Run(tc.Name, func(t *testing.T) {
			ctx := DefaultContext(tc.Context.Now)
			ctx.ShiftZones = tc.Context.ShiftZones
			ctx.ZoneRisk = tc.Context.ZoneRisk
			got := Evaluate(tc.Device, Compute(tc.Device, ctx), ctx.Now)
			if diff := cmp.Diff(tc.Want, got); diff != "" {
				t.Fatal(diff)
			}
			b, err := json.Marshal(got)
			if err != nil {
				t.Fatal(err)
			}
			var restored device.Verdict
			if err := json.Unmarshal(b, &restored); err != nil {
				t.Fatal(err)
			}
			if diff := cmp.Diff(got, restored); diff != "" {
				t.Fatal(diff)
			}
		})
	}
}
