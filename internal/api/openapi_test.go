package api

import (
	"bufio"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// parseOpenAPI extrae "METHOD /path" -> x-capability del YAML restringido.
func parseOpenAPI(t *testing.T, path string) map[string]string {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("docs/openapi.yaml obligatorio (spec §6.1): %v", err)
	}
	defer func() { _ = f.Close() }()
	out := map[string]string{}
	inPaths := false
	var curPath, curMethod string
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "paths:") {
			inPaths = true
			continue
		}
		if inPaths && len(line) > 0 && line[0] != ' ' {
			inPaths = false
		}
		if !inPaths {
			continue
		}
		indent := len(line) - len(strings.TrimLeft(line, " "))
		trim := strings.TrimSpace(line)
		switch {
		case indent == 2 && strings.HasPrefix(trim, "/"):
			curPath = strings.TrimSuffix(trim, ":")
		case indent == 4 && strings.HasSuffix(trim, ":"):
			curMethod = strings.ToUpper(strings.TrimSuffix(trim, ":"))
		case indent == 6 && strings.HasPrefix(trim, "x-capability:"):
			out[curMethod+" "+curPath] = strings.TrimSpace(strings.TrimPrefix(trim, "x-capability:"))
		}
	}
	return out
}

func TestRutasYOpenAPICoinciden(t *testing.T) {
	st, _ := store.Open(t.TempDir())
	org, _ := st.Org("default")
	as, _ := auth.Open(st.AuthDir(), time.Now)
	eng := engine.New(org, nil, engine.Options{Mode: "simulation"})
	_, reg := New(Deps{Engine: eng, Org: org, Auth: as, Web: http.NotFoundHandler(), Config: config.Default()})
	documented := parseOpenAPI(t, "../../docs/openapi.yaml")
	registered := map[string]string{}
	for _, r := range reg.Routes() {
		cap := string(r.Cap)
		if r.Public {
			cap = "public"
		}
		registered[r.Method+" "+r.Path] = cap
	}
	for k, cap := range registered {
		if doc, ok := documented[k]; !ok {
			t.Errorf("%s registrada pero no documentada en docs/openapi.yaml", k)
		} else if doc != cap {
			t.Errorf("%s: x-capability %q en OpenAPI, %q en el registro", k, doc, cap)
		}
	}
	for k := range documented {
		if _, ok := registered[k]; !ok {
			t.Errorf("%s documentada pero no registrada", k)
		}
	}
}
