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
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
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
	_, reg := New(Deps{Engine: eng, Org: org, Store: st, Auth: as, Web: http.NotFoundHandler(), Config: config.Default()})
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

// openAPIEnum extrae la lista enum de una propiedad de components.schemas del
// mismo YAML restringido que lee parseOpenAPI: el esquema con indentación 4, la
// propiedad con 8 y el enum en línea (enum: [a, b, c]) en el nivel de la
// propiedad o dentro de su items. Falla si la propiedad no documenta ninguno,
// que es justo el caso que este fichero tiene que impedir: una cadena libre en
// el contrato donde el dominio valida una lista cerrada.
func openAPIEnum(t *testing.T, path, schema, prop string) []string {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("docs/openapi.yaml obligatorio (spec §6.1): %v", err)
	}
	defer func() { _ = f.Close() }()
	inSchema, inProp := false, false
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		indent := len(line) - len(strings.TrimLeft(line, " "))
		trim := strings.TrimSpace(line)
		switch {
		case indent == 4 && strings.HasSuffix(trim, ":"):
			inSchema, inProp = strings.TrimSuffix(trim, ":") == schema, false
		case inSchema && indent == 8 && strings.HasSuffix(trim, ":"):
			inProp = strings.TrimSuffix(trim, ":") == prop
		case inSchema && inProp && indent >= 10 && strings.HasPrefix(trim, "enum: ["):
			raw := strings.TrimSuffix(strings.TrimPrefix(trim, "enum: ["), "]")
			out := strings.Split(raw, ",")
			for i := range out {
				out[i] = strings.TrimSpace(out[i])
			}
			return out
		}
	}
	t.Fatalf("%s.%s se documenta sin enum: el editor de T23 se queda sin vocabulario y la descripción puede prometer un valor que el servidor rechaza con 400", schema, prop)
	return nil
}

// TestElContratoDocumentaElVocabularioDelDominio: las listas cerradas que el
// dominio valida (risk.Severities, policy.Ops y action.All) tienen una sola
// fuente de verdad, y docs/openapi.yaml —y por tanto schema.d.ts, y por tanto el
// editor de T23— no puede ofrecer un valor que el crud rechace ni callarse uno
// que acepta. Es el hermano de TestPolicyFieldsEsElUnicoVocabularioDelEditor
// para el cuerpo de los esquemas, que TestRutasYOpenAPICoinciden no mira.
func TestElContratoDocumentaElVocabularioDelDominio(t *testing.T) {
	ops := make([]string, 0, len(policy.Ops))
	for _, op := range policy.Ops {
		ops = append(ops, string(op))
	}
	acciones := make([]string, 0, len(action.All))
	for _, a := range action.All {
		acciones = append(acciones, string(a))
	}
	casos := []struct {
		schema, prop string
		want         []string
	}{
		{"Policy", "severity", risk.Severities},
		{"PolicyCondition", "op", ops},
		{"PolicyAction", "action", acciones},
		{"PolicyFieldCatalog", "ops", ops},
	}
	for _, c := range casos {
		got := openAPIEnum(t, "../../docs/openapi.yaml", c.schema, c.prop)
		if strings.Join(got, ",") != strings.Join(c.want, ",") {
			t.Errorf("%s.%s documenta %v; el dominio valida %v", c.schema, c.prop, got, c.want)
		}
	}
}

// openAPIParamEnum extrae el enum de un parámetro de query documentado bajo
// paths.<opPath>.<method>.parameters, fuera del alcance de openAPIEnum (que
// solo mira components.schemas). Mismo YAML restringido, misma disciplina de
// fallar alto si el parámetro no documenta ningún enum. El recorrido vive en
// paramScan: un método por nivel del árbol, para que ninguna función pase del
// techo de complejidad ciclomática de 15 (spec §9.1.1).
func openAPIParamEnum(t *testing.T, path, opPath, method, param string) []string {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("docs/openapi.yaml obligatorio (spec §6.1): %v", err)
	}
	defer func() { _ = f.Close() }()
	scan := paramScan{opPath: opPath, method: method, param: param}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		if values, ok := scan.step(sc.Text()); ok {
			return values
		}
	}
	t.Fatalf("%s %s: parámetro %q se documenta sin enum", method, opPath, param)
	return nil
}

// paramScan recuerda en qué nivel del YAML va el recorrido de
// openAPIParamEnum: la ruta, el método, el bloque parameters y el parámetro
// buscado. Cada nivel tiene su método y decide una sola cosa.
type paramScan struct {
	opPath, method, param             string
	inPath, inMethod, inList, inParam bool
}

// step consume una línea y devuelve el enum en cuanto lo encuentra dentro del
// parámetro buscado.
func (s *paramScan) step(line string) ([]string, bool) {
	indent := len(line) - len(strings.TrimLeft(line, " "))
	trim := strings.TrimSpace(line)
	switch {
	case indent == 2:
		s.enterPath(trim)
	case indent == 4:
		s.enterMethod(trim)
	case indent == 6:
		s.enterList(trim)
	case indent == 8:
		s.enterParam(trim)
	case s.inParam && indent >= 10:
		return parseEnumInline(trim)
	}
	return nil, false
}

// enterPath solo reacciona a una clave de ruta ("/api/...:"): cualquier otra
// cosa a esa indentación (components.parameters, por ejemplo) no toca nada.
func (s *paramScan) enterPath(trim string) {
	if !strings.HasPrefix(trim, "/") || !strings.HasSuffix(trim, ":") {
		return
	}
	s.inPath = strings.TrimSuffix(trim, ":") == s.opPath
	s.inMethod, s.inList, s.inParam = false, false, false
}

func (s *paramScan) enterMethod(trim string) {
	if !s.inPath || !strings.HasSuffix(trim, ":") {
		return
	}
	s.inMethod = strings.TrimSuffix(trim, ":") == s.method
	s.inList, s.inParam = false, false
}

func (s *paramScan) enterList(trim string) {
	if s.inMethod && trim == "parameters:" {
		s.inList = true
	}
}

func (s *paramScan) enterParam(trim string) {
	if s.inList && strings.HasPrefix(trim, "- name:") {
		s.inParam = strings.TrimSpace(strings.TrimPrefix(trim, "- name:")) == s.param
	}
}

// parseEnumInline lee la forma en línea "enum: [a, b, c]", la única que usa
// docs/openapi.yaml para los parámetros de query.
func parseEnumInline(trim string) ([]string, bool) {
	if !strings.HasPrefix(trim, "enum: [") {
		return nil, false
	}
	out := strings.Split(strings.TrimSuffix(strings.TrimPrefix(trim, "enum: ["), "]"), ",")
	for i := range out {
		out[i] = strings.TrimSpace(out[i])
	}
	return out, true
}

// TestFiltroDeSeveridadDocumentaElVocabularioDelDominio (M2-R63): el filtro
// ?severity de GET /api/v1/devices documenta los cuatro niveles de
// risk.Severities más "unknown" (risk.SeverityUnknown, el quinto valor real
// de Verdict.Severity), ni uno menos ni uno de más.
func TestFiltroDeSeveridadDocumentaElVocabularioDelDominio(t *testing.T) {
	want := append(append([]string{}, risk.Severities...), risk.SeverityUnknown)
	got := openAPIParamEnum(t, "../../docs/openapi.yaml", "/api/v1/devices", "get", "severity")
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Errorf("severity documenta %v; el dominio valida %v", got, want)
	}
}
