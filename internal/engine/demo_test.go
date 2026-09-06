package engine

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/store"
)

func TestSeedDemoIdempotente(t *testing.T) {
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Now()
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	fs, _ := org.Fences()
	rs, _ := org.Routes()
	ps, _ := org.POIs()
	if len(fs) != 2 || fs[0].ID != "demo-hq" || fs[1].ID != "warehouse-poly" || len(rs) != 1 || len(ps) != 2 {
		t.Fatalf("demo: %d fences %d routes %d pois", len(fs), len(rs), len(ps))
	}
	_ = org.SaveFences(fs[:1])
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	if fs, _ = org.Fences(); len(fs) != 1 {
		t.Fatal("no debe sobrescribir geocercas existentes")
	}
}
