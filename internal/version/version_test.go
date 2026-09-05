package version

import (
	"runtime"
	"strings"
	"testing"
)

func TestStringIncluyeVersionCommitYPlataforma(t *testing.T) {
	got := String()
	for _, want := range []string{"lucidfence ", Version, Commit, runtime.Version(), runtime.GOOS + "/" + runtime.GOARCH} {
		if !strings.Contains(got, want) {
			t.Fatalf("String() = %q, no contiene %q", got, want)
		}
	}
}

func TestVersionPorDefectoEsDev(t *testing.T) {
	if Version != "2.0.0-dev" {
		t.Fatalf("Version por defecto = %q, quiero 2.0.0-dev", Version)
	}
}
