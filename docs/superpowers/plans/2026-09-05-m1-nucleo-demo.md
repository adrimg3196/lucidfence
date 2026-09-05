# LucidFence 2.0 · Hito M1 "Núcleo demo" · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un binario `lucidfence serve` que en una máquina limpia deja, en menos de un minuto, un dashboard usable en modo demo: asistente inicial, visión general, mapa en vivo, dispositivos y geocercas, con el motor evaluando una flota simulada y registrando transiciones y acciones en dry-run.

**Architecture:** Dominio puro (`internal/domain/*`) sin I/O; `store` persiste JSON/JSONL atómico por org; `uem/simulation` implementa el contrato `Adapter`; `engine` ejecuta el ciclo bajo `TryLock` y aplica guardarraíles (`observe` = todo dry-run); `auth` da setup, sesiones con CSRF y token local; `api` monta rutas `/api/v1` con capacidad obligatoria y sirve el dashboard embebido; el frontend React consume tipos generados desde `docs/openapi.yaml`.

**Tech Stack:** Go 1.27 (stdlib + `golang.org/x/crypto` v0.56.0 para argon2id), React 19.2 + TypeScript 7 + Vite 8 + Tailwind 4.3 + shadcn/ui + Phosphor + TanStack Query 5 + react-router 8 + react-hook-form 7 + zod 4 + MapLibre GL 6.7 + openapi-fetch 0.17 + openapi-typescript 7.13, Vitest 5, Playwright 1.63.

**Spec:** `docs/superpowers/specs/2026-09-05-lucidfence-2-go-rewrite-design.md` (§4.1, §5.3-§5.8, §6.1-§6.3, §7, §9.1, §11, §12, §14 M1).

## Global Constraints

- Prerrequisito: hito M0 completado (`main` = esqueleto Go verde; `make verify` funciona). Trabajo en `/Users/adri/lucidfence-v2` en la rama `m1/nucleo-demo` creada desde `origin/main`.
- Fronteras de importación de `ARCHITECTURE.md` (`depguard` las valida): `domain` solo stdlib y `domain/*`; `uem` → `domain`, `uem`; `store` → `domain`; `engine` → `domain`, `uem`, `store`, `config`; `auth` → `domain`, `store`, `x/crypto`; `api` → `engine`, `auth`, `store`, `domain`, `uem` (nunca `uem/<conector>`), `config`, `version`.
- Límites físicos: `.go` ≤ 400 líneas, `.tsx` ≤ 300, funciones ≤ 60 líneas / 40 sentencias, ciclomática ≤ 15. Si una tarea produce un fichero mayor, se divide en dos ficheros del mismo paquete.
- Suelos de cobertura: `internal/domain/**` e `internal/engine` 85 %; resto 70 %; `cmd/battery` exento. Todo paquete nuevo lleva tests.
- Dependencia Go nueva en este hito: solo `golang.org/x/crypto v0.56.0` (ya en `internal/arch/allowlist_go.txt`).
- Cada paquete nuevo se añade a la tabla "## Paquetes" de `ARCHITECTURE.md` en el mismo commit (el test `TestArchitectureDocListsEveryPackage` lo exige).
- JSON de la API en `snake_case`; fechas en RFC 3339 UTC; errores `{error, code, detail}`; rutas bajo `/api/v1`.
- Enforcement en M1: siempre `observe` (dry-run). `internal/engine/guardrails.go` es el único sitio que decide `dryRun`; M2 lo amplía.
- UI en español por defecto, inglés disponible; sin emojis; acento único `#3E7A5E`; radio 8 px; cuatro estados por vista (cargando, vacío, error, contenido).
- Commits terminan con:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w
  ```

---

## Mapa de ficheros del hito

| Fichero | Responsabilidad |
|---------|-----------------|
| `internal/domain/geo/geo.go` (+`_test`) | `Point`, haversine, punto en polígono, distancia a segmento y polilínea |
| `internal/domain/action/action.go` (+`_test`) | enum `Action`, `Result` de una acción UEM |
| `internal/domain/fence/fence.go` (+`_test`) | `Fence`, `Contains`, `Validate`, `ValidateAll`, `FindByID` |
| `internal/domain/route/route.go` (+`_test`) | `Route`, `DistanceM`, `ForDevice`, validación |
| `internal/domain/poi/poi.go` (+`_test`) | `POI`, validación, `ToGeoJSON` |
| `internal/domain/device/device.go` (+`_test`) | `Device`, `Location`, `Inventory`, `Verdict`, `TrailPoint`, estados |
| `internal/domain/transition/transition.go` (+`_test`) | evaluación de geocerca y detección de transición |
| `internal/store/store.go`, `orgstore.go`, `jsonl.go` (+`_test`) | persistencia atómica JSON/JSONL por org |
| `internal/uem/adapter.go`, `registry.go` (+`_test`) | contrato `Adapter`, `Capabilities`, `Registry` |
| `internal/uem/simulation/seed.go`, `simulation.go` (+`_test`) | seed embebida, movimiento por waypoints, acciones simuladas |
| `internal/config/config.go` (+`_test`) | `Config`, defaults, `Load`, `Validate`, `Save` |
| `internal/engine/engine.go`, `cycle.go`, `actions.go`, `guardrails.go`, `demo.go` (+`_test`) | ciclo, planificación de acciones, guardarraíles, seed demo |
| `internal/auth/password.go`, `rbac.go`, `store.go` (+`_test`) | argon2id, roles y capacidades, usuarios, sesiones, token local |
| `internal/api/respond.go`, `registry.go`, `middleware.go`, `server.go` (+`_test`) | núcleo HTTP |
| `internal/api/handlers_health.go`, `handlers_auth.go`, `handlers_devices.go`, `handlers_fences.go`, `handlers_routes.go`, `handlers_pois.go`, `handlers_engine.go` (+`_test`) | recursos |
| `internal/api/openapi_test.go`, `docs/openapi.yaml` | contrato rutas ↔ OpenAPI ↔ capacidades |
| `cmd/lucidfence/serve.go`, `doctor.go`, `open.go` (+`_test`) | subcomandos |
| `internal/battery/checks_m1.go`, `server.go` | checks en vivo del hito |
| `web/src/lib/i18n.ts`, `permissions.ts`, `utils.ts`, `query.ts` | utilidades |
| `web/src/api/schema.d.ts` (generado), `client.ts`, `hooks.ts` | cliente tipado |
| `web/src/components/states/*`, `components/ui/*` (shadcn) | componentes base |
| `web/src/app/router.tsx`, `Shell.tsx`, `AuthGate.tsx`, `nav.ts` | shell y rutas |
| `web/src/features/setup/`, `login/`, `overview/`, `map/`, `devices/`, `fences/` | vistas |
| `web/e2e/demo.spec.ts`, `web/playwright.config.ts` | end-to-end |
| `.github/workflows/ci.yml` (job `e2e`) | CI |

---

### Task 1: Geometría (`internal/domain/geo`)

**Files:**
- Create: `internal/domain/geo/geo.go`, `internal/domain/geo/geo_test.go`
- Modify: `ARCHITECTURE.md` (tabla de paquetes)

**Interfaces:**
- Produces:
  ```go
  type Point struct { Lat float64 `json:"lat"`; Lng float64 `json:"lng"` }
  func NewPoint(lat, lng float64) (Point, error)   // rechaza NaN/Inf y fuera de rango
  func (p Point) Valid() error
  func HaversineM(a, b Point) float64
  func PointInPolygon(p Point, polygon []Point) bool // ray casting, seguro en el antimeridiano
  func DistanceToSegmentM(p, a, b Point) float64    // cross-track esférico con clamp a extremos
  func DistanceToPolylineM(p Point, line []Point) float64
  const EarthRadiusM = 6_371_000.0
  ```

- [ ] **Step 1: Crear la rama del hito**

```bash
git fetch origin && git checkout -q -b m1/nucleo-demo origin/main
```

- [ ] **Step 2: Tests dorados (fallan)**

`internal/domain/geo/geo_test.go`:
```go
package geo

import (
	"math"
	"testing"
)

func near(t *testing.T, got, want, tol float64, msg string) {
	t.Helper()
	if math.Abs(got-want) > tol {
		t.Fatalf("%s: got %.3f want %.3f (±%.3f)", msg, got, want, tol)
	}
}

func TestNewPointRechazaValoresInvalidos(t *testing.T) {
	bad := [][2]float64{{91, 0}, {-91, 0}, {0, 181}, {0, -181}, {math.NaN(), 0}, {0, math.Inf(1)}}
	for _, c := range bad {
		if _, err := NewPoint(c[0], c[1]); err == nil {
			t.Fatalf("NewPoint(%v) debería fallar", c)
		}
	}
	if _, err := NewPoint(40.42, -3.71); err != nil {
		t.Fatal(err)
	}
}

func TestHaversineCasosDorados(t *testing.T) {
	near(t, HaversineM(Point{0, 0}, Point{0, 1}), 111194.93, 0.5, "1 grado de longitud en el ecuador")
	near(t, HaversineM(Point{0, 0}, Point{1, 0}), 111194.93, 0.5, "1 grado de latitud")
	near(t, HaversineM(Point{0, 0}, Point{0, 180}), math.Pi*EarthRadiusM, 1, "antípoda")
	near(t, HaversineM(Point{40.42, -3.71}, Point{40.42, -3.71}), 0, 0, "mismo punto")
	near(t, HaversineM(Point{40.4168, -3.7038}, Point{40.4200, -3.7100}), 634, 3, "Sol a Plaza de España aprox")
}

func TestPointInPolygonCuadradoYConcavo(t *testing.T) {
	square := []Point{{40.40, -3.72}, {40.40, -3.70}, {40.44, -3.70}, {40.44, -3.72}}
	if !PointInPolygon(Point{40.42, -3.71}, square) {
		t.Fatal("centro del cuadrado debe estar dentro")
	}
	if PointInPolygon(Point{40.45, -3.71}, square) {
		t.Fatal("fuera por el norte")
	}
	// Forma en L: (0,0)-(2,0)-(2,1)-(1,1)-(1,2)-(0,2). El punto (1.5,1.5) está en el hueco.
	l := []Point{{0, 0}, {0, 2}, {1, 2}, {1, 1}, {2, 1}, {2, 0}}
	if !PointInPolygon(Point{0.5, 0.5}, l) {
		t.Fatal("(0.5,0.5) dentro de la L")
	}
	if PointInPolygon(Point{1.5, 1.5}, l) {
		t.Fatal("(1.5,1.5) en el hueco de la L")
	}
	if PointInPolygon(Point{0, 0}, []Point{{0, 0}, {1, 1}}) {
		t.Fatal("menos de 3 vértices nunca contiene")
	}
}

func TestPointInPolygonAntimeridiano(t *testing.T) {
	// Cuadrado de 4° de ancho que cruza lng ±180.
	poly := []Point{{-1, 178}, {-1, -178}, {1, -178}, {1, 178}}
	if !PointInPolygon(Point{0, 179.5}, poly) || !PointInPolygon(Point{0, -179.5}, poly) {
		t.Fatal("puntos a ambos lados del antimeridiano deben estar dentro")
	}
	if PointInPolygon(Point{0, 0}, poly) {
		t.Fatal("lng 0 está fuera de una banda de 4°")
	}
}

func TestDistanceToSegment(t *testing.T) {
	a, b := Point{0, 0}, Point{0, 1}
	near(t, DistanceToSegmentM(Point{0, 0.5}, a, b), 0, 0.01, "punto sobre el segmento")
	near(t, DistanceToSegmentM(Point{0.01, 0.5}, a, b), 1111.95, 1, "perpendicular a 0.01°")
	near(t, DistanceToSegmentM(Point{0, -0.01}, a, b), 1111.95, 1, "antes de a: clamp a a")
	near(t, DistanceToSegmentM(Point{0, 1.01}, a, b), 1111.95, 1, "después de b: clamp a b")
	near(t, DistanceToSegmentM(Point{0.01, 0}, a, a), 1111.95, 1, "segmento degenerado")
}

func TestDistanceToPolyline(t *testing.T) {
	line := []Point{{0, 0}, {0, 1}, {1, 1}}
	near(t, DistanceToPolylineM(Point{0.5, 1.001}, line), 111.2, 1, "cerca del segundo segmento")
	if d := DistanceToPolylineM(Point{0, 0}, nil); !math.IsInf(d, 1) {
		t.Fatalf("polilínea vacía debe dar +Inf, got %v", d)
	}
	near(t, DistanceToPolylineM(Point{0.01, 0}, []Point{{0, 0}}), 1111.95, 1, "un solo punto")
}
```

- [ ] **Step 3: Ejecutar y ver que falla**

Run: `go test ./internal/domain/geo/`
Expected: `undefined: NewPoint` (compilación).

- [ ] **Step 4: Implementar `geo.go`**

```go
// Package geo contiene la geometría esférica de LucidFence: distancias,
// pertenencia a polígono y distancia a rutas. Sin I/O. Portado de 1.x con los
// mismos casos dorados (antimeridiano, clamp a extremos).
package geo

import (
	"errors"
	"fmt"
	"math"
)

// EarthRadiusM es el radio medio terrestre usado por haversine.
const EarthRadiusM = 6_371_000.0

// Point es una coordenada WGS84 en grados.
type Point struct {
	Lat float64 `json:"lat"`
	Lng float64 `json:"lng"`
}

// NewPoint valida rango y finitud. Una geocerca es un control de seguridad:
// un NaN o un 9999 debe fallar aquí, nunca evaluarse como "fuera".
func NewPoint(lat, lng float64) (Point, error) {
	p := Point{Lat: lat, Lng: lng}
	return p, p.Valid()
}

// Valid devuelve error si la coordenada no es finita o está fuera de rango.
func (p Point) Valid() error {
	if math.IsNaN(p.Lat) || math.IsInf(p.Lat, 0) || p.Lat < -90 || p.Lat > 90 {
		return fmt.Errorf("lat fuera de rango o no finita: %v", p.Lat)
	}
	if math.IsNaN(p.Lng) || math.IsInf(p.Lng, 0) || p.Lng < -180 || p.Lng > 180 {
		return fmt.Errorf("lng fuera de rango o no finita: %v", p.Lng)
	}
	return nil
}

func rad(deg float64) float64 { return deg * math.Pi / 180 }

// HaversineM es la distancia de círculo máximo en metros.
func HaversineM(a, b Point) float64 {
	dLat := rad(b.Lat - a.Lat)
	dLng := rad(b.Lng - a.Lng)
	x := math.Pow(math.Sin(dLat/2), 2) + math.Cos(rad(a.Lat))*math.Cos(rad(b.Lat))*math.Pow(math.Sin(dLng/2), 2)
	return EarthRadiusM * 2 * math.Asin(math.Min(1, math.Sqrt(x)))
}

// unwrapLng devuelve la longitud equivalente a lng dentro de ±180° de ref,
// para que una figura que cruza el antimeridiano se trate con su anchura real.
func unwrapLng(lng, ref float64) float64 {
	return ref + math.Mod(lng-ref+180+360, 360) - 180
}

// PointInPolygon aplica ray casting. Seguro para polígonos de menos de 180°
// de longitud (toda geocerca real). El borde exacto queda indefinido.
func PointInPolygon(p Point, polygon []Point) bool {
	n := len(polygon)
	if n < 3 {
		return false
	}
	ref := polygon[0].Lng
	xs := make([]float64, n)
	ys := make([]float64, n)
	for i, v := range polygon {
		xs[i], ys[i] = unwrapLng(v.Lng, ref), v.Lat
	}
	lat, lng := p.Lat, unwrapLng(p.Lng, ref)
	inside := false
	for i, j := 0, n-1; i < n; j, i = i, i+1 {
		if (ys[i] > lat) != (ys[j] > lat) && lng < (xs[j]-xs[i])*(lat-ys[i])/(ys[j]-ys[i])+xs[i] {
			inside = !inside
		}
	}
	return inside
}

func bearing(a, b Point) float64 {
	lat1, lat2 := rad(a.Lat), rad(b.Lat)
	dLng := rad(b.Lng - a.Lng)
	y := math.Sin(dLng) * math.Cos(lat2)
	x := math.Cos(lat1)*math.Sin(lat2) - math.Sin(lat1)*math.Cos(lat2)*math.Cos(dLng)
	return math.Atan2(y, x)
}

func clamp1(v float64) float64 { return math.Max(-1, math.Min(1, v)) }

// DistanceToSegmentM es la distancia mínima de p al segmento a-b usando las
// fórmulas esféricas de cross-track y along-track, con clamp al extremo más
// cercano cuando el pie de la perpendicular cae fuera del segmento.
func DistanceToSegmentM(p, a, b Point) float64 {
	if a == b {
		return HaversineM(p, a)
	}
	dAP := HaversineM(a, p) / EarthRadiusM
	if dAP == 0 {
		return 0
	}
	delta := bearing(a, p) - bearing(a, b)
	if math.Cos(delta) < 0 {
		return HaversineM(p, a)
	}
	xt := math.Asin(clamp1(math.Sin(dAP) * math.Sin(delta)))
	cosXT := math.Cos(xt)
	at := 0.0
	if cosXT != 0 {
		at = math.Acos(clamp1(math.Cos(dAP) / cosXT))
	}
	if at > HaversineM(a, b)/EarthRadiusM {
		return HaversineM(p, b)
	}
	return math.Abs(xt) * EarthRadiusM
}

// DistanceToPolylineM es el mínimo sobre todos los segmentos; +Inf si no hay puntos.
func DistanceToPolylineM(p Point, line []Point) float64 {
	switch len(line) {
	case 0:
		return math.Inf(1)
	case 1:
		return HaversineM(p, line[0])
	}
	best := math.Inf(1)
	for i := 0; i+1 < len(line); i++ {
		best = math.Min(best, DistanceToSegmentM(p, line[i], line[i+1]))
	}
	return best
}

// ErrEmptyPolygon se usa por los validadores de dominio.
var ErrEmptyPolygon = errors.New("polígono con menos de 3 vértices")
```

- [ ] **Step 5: Ejecutar tests (pasan) y cobertura**

Run: `go test ./internal/domain/geo/ -cover -v`
Expected: todos PASS, cobertura ≥ 85 %.

- [ ] **Step 6: Documentar el paquete y commit**

Añadir a la tabla "## Paquetes" de `ARCHITECTURE.md`:
```
| `internal/domain/geo` | Geometría esférica: distancias, punto en polígono, distancia a polilínea. Sin I/O. |
```

```bash
go test ./internal/arch/ && golangci-lint run ./internal/domain/...
git add internal/domain/geo ARCHITECTURE.md
git commit -q -m "feat(domain): geometría esférica con casos dorados (haversine, ray casting, cross-track)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 2: Acciones y geocercas (`internal/domain/action`, `internal/domain/fence`)

**Files:**
- Create: `internal/domain/action/action.go` (+`action_test.go`)
- Create: `internal/domain/fence/fence.go` (+`fence_test.go`)
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces (`action`):
  ```go
  type Action string
  const ( Lock Action = "lock"; Wipe = "wipe"; Message = "message"; Locate = "locate"; Reboot = "reboot"
          ClearPasscode = "clear_passcode"; SetCompliance = "set_compliance"; Custom = "custom"; Notify = "notify" )
  func Parse(s string) (Action, error)
  func (a Action) Destructive() bool // lock, wipe, clear_passcode, reboot
  type Result struct { Adapter string `json:"adapter"`; OK bool `json:"ok"`; DeviceID string `json:"device_id"`; DeviceName string `json:"device_name"`
                       Action Action `json:"action"`; Params map[string]any `json:"params,omitempty"`; DryRun bool `json:"dry_run"`; Simulated bool `json:"simulated"`
                       Error string `json:"error,omitempty"`; CommandID string `json:"command_id,omitempty"`; Note string `json:"note,omitempty"`
                       At time.Time `json:"at"`; FenceID string `json:"fence_id,omitempty"`; Trigger string `json:"trigger,omitempty"` }
  ```
- Produces (`fence`):
  ```go
  type Kind string  // "circle" | "polygon"
  type When string  // "on_enter" | "on_exit" | "on_violation" | "on_unknown"
  type Action struct { Action action.Action `json:"action"`; When When `json:"when"`; Params map[string]any `json:"params,omitempty"`; Enabled bool `json:"enabled"` }
  type Rules struct { ViolationIntervalCycles int `json:"violation_interval_cycles,omitempty"`; DwellSeconds int `json:"dwell_seconds,omitempty"` }
  type Fence struct { ID string `json:"id"`; Name string `json:"name"`; Kind Kind `json:"kind"`; Center *geo.Point `json:"center,omitempty"`; RadiusM float64 `json:"radius_m,omitempty"`
                      Polygon []geo.Point `json:"polygon,omitempty"`; Rules Rules `json:"rules"`; Actions []Action `json:"actions"`
                      CreatedAt time.Time `json:"created_at"`; UpdatedAt time.Time `json:"updated_at"` }
  func (f Fence) Contains(p geo.Point) bool
  func (f Fence) Validate() error
  func ValidateAll(fs []Fence) error
  func FindByID(fs []Fence, id string) (Fence, bool)
  func (f Fence) ActionsFor(w When) []Action  // solo habilitadas
  var IDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,63}$`)
  ```

- [ ] **Step 1: Tests de `action` (fallan)**

`internal/domain/action/action_test.go`:
```go
package action

import "testing"

func TestParseYDestructive(t *testing.T) {
	for _, s := range []string{"lock", "wipe", "message", "locate", "reboot", "clear_passcode", "set_compliance", "custom", "notify"} {
		if _, err := Parse(s); err != nil {
			t.Fatalf("Parse(%q): %v", s, err)
		}
	}
	if _, err := Parse("format_disk"); err == nil {
		t.Fatal("acción desconocida debe fallar")
	}
	for a, want := range map[Action]bool{Lock: true, Wipe: true, ClearPasscode: true, Reboot: true, Message: false, Locate: false, Notify: false, SetCompliance: false, Custom: false} {
		if a.Destructive() != want {
			t.Fatalf("%s.Destructive()=%v", a, !want)
		}
	}
}
```

- [ ] **Step 2: Implementar `action.go`**

```go
// Package action define las acciones UEM que LucidFence puede ordenar y el
// resultado normalizado que devuelve todo conector.
package action

import (
	"fmt"
	"time"
)

// Action es una orden al UEM.
type Action string

const (
	Lock          Action = "lock"
	Wipe          Action = "wipe"
	Message       Action = "message"
	Locate        Action = "locate"
	Reboot        Action = "reboot"
	ClearPasscode Action = "clear_passcode"
	SetCompliance Action = "set_compliance"
	Custom        Action = "custom"
	Notify        Action = "notify"
)

// All enumera las acciones válidas en orden estable.
var All = []Action{Lock, Wipe, Message, Locate, Reboot, ClearPasscode, SetCompliance, Custom, Notify}

// Parse valida una cadena.
func Parse(s string) (Action, error) {
	for _, a := range All {
		if string(a) == s {
			return a, nil
		}
	}
	return "", fmt.Errorf("acción desconocida %q", s)
}

// Destructive marca las acciones que exigen handoff humano en SOAR y
// guardarraíles en enforce (spec §6.5).
func (a Action) Destructive() bool {
	switch a {
	case Lock, Wipe, ClearPasscode, Reboot:
		return true
	}
	return false
}

// Result es el resultado normalizado de ejecutar una acción.
type Result struct {
	Adapter    string         `json:"adapter"`
	OK         bool           `json:"ok"`
	DeviceID   string         `json:"device_id"`
	DeviceName string         `json:"device_name"`
	Action     Action         `json:"action"`
	Params     map[string]any `json:"params,omitempty"`
	DryRun     bool           `json:"dry_run"`
	Simulated  bool           `json:"simulated"`
	Error      string         `json:"error,omitempty"`
	CommandID  string         `json:"command_id,omitempty"`
	Note       string         `json:"note,omitempty"`
	At         time.Time      `json:"at"`
	FenceID    string         `json:"fence_id,omitempty"`
	Trigger    string         `json:"trigger,omitempty"`
}
```

Run: `go test ./internal/domain/action/ -v` → PASS.

- [ ] **Step 3: Tests de `fence` (fallan)**

`internal/domain/fence/fence_test.go`:
```go
package fence

import (
	"strings"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func circle() Fence {
	return Fence{ID: "demo-hq", Name: "Demo HQ", Kind: Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
		Actions: []Action{{Action: action.Message, When: OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido"}}}}
}

func polygon() Fence {
	return Fence{ID: "warehouse-poly", Name: "Almacén", Kind: Polygon,
		Polygon: []geo.Point{{Lat: 40.40, Lng: -3.72}, {Lat: 40.40, Lng: -3.70}, {Lat: 40.41, Lng: -3.70}, {Lat: 40.41, Lng: -3.72}}}
}

func TestContainsCirculoBordeInclusivo(t *testing.T) {
	f := circle()
	if !f.Contains(geo.Point{Lat: 40.421, Lng: -3.708}) {
		t.Fatal("centro dentro")
	}
	if f.Contains(geo.Point{Lat: 40.43, Lng: -3.708}) {
		t.Fatal("a 1 km debe estar fuera")
	}
	// ~500 m al norte: 500/111194.93 grados de latitud.
	edge := geo.Point{Lat: 40.421 + 500.0/111194.93, Lng: -3.708}
	if !f.Contains(edge) {
		t.Fatal("el borde exacto es inclusivo (<=)")
	}
}

func TestContainsPoligono(t *testing.T) {
	f := polygon()
	if !f.Contains(geo.Point{Lat: 40.405, Lng: -3.71}) || f.Contains(geo.Point{Lat: 40.42, Lng: -3.71}) {
		t.Fatal("pertenencia al polígono incorrecta")
	}
	if (Fence{Kind: "hexagon"}).Contains(geo.Point{}) {
		t.Fatal("tipo desconocido nunca contiene")
	}
}

func TestValidate(t *testing.T) {
	cases := map[string]Fence{
		"id inválido":          {ID: "Demo HQ", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10},
		"sin nombre":           {ID: "a", Kind: Circle, Center: &geo.Point{}, RadiusM: 10},
		"círculo sin centro":   {ID: "a", Name: "x", Kind: Circle, RadiusM: 10},
		"radio cero":           {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 0},
		"centro fuera de rango": {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{Lat: 95}, RadiusM: 10},
		"polígono corto":       {ID: "a", Name: "x", Kind: Polygon, Polygon: []geo.Point{{}, {}}},
		"tipo desconocido":     {ID: "a", Name: "x", Kind: "hexagon"},
		"acción desconocida":   {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10, Actions: []Action{{Action: "explode", When: OnEnter}}},
		"when desconocido":     {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10, Actions: []Action{{Action: action.Lock, When: "sometimes"}}},
		"intervalo negativo":   {ID: "a", Name: "x", Kind: Circle, Center: &geo.Point{}, RadiusM: 10, Rules: Rules{ViolationIntervalCycles: -1}},
	}
	for name, f := range cases {
		if err := f.Validate(); err == nil {
			t.Errorf("%s: debería fallar", name)
		}
	}
	if err := circle().Validate(); err != nil {
		t.Fatal(err)
	}
	if err := polygon().Validate(); err != nil {
		t.Fatal(err)
	}
}

func TestValidateAllIDsUnicos(t *testing.T) {
	err := ValidateAll([]Fence{circle(), circle()})
	if err == nil || !strings.Contains(err.Error(), "duplicado") {
		t.Fatalf("esperaba error de id duplicado, got %v", err)
	}
	if err := ValidateAll([]Fence{circle(), polygon()}); err != nil {
		t.Fatal(err)
	}
}

func TestFindByIDYActionsFor(t *testing.T) {
	fs := []Fence{circle(), polygon()}
	if f, ok := FindByID(fs, "warehouse-poly"); !ok || f.Name != "Almacén" {
		t.Fatal("FindByID")
	}
	if _, ok := FindByID(fs, "nope"); ok {
		t.Fatal("no debería encontrar")
	}
	f := circle()
	f.Actions = append(f.Actions, Action{Action: action.Lock, When: OnExit, Enabled: false})
	if got := f.ActionsFor(OnEnter); len(got) != 1 || got[0].Action != action.Message {
		t.Fatalf("ActionsFor(on_enter)=%v", got)
	}
	if got := f.ActionsFor(OnExit); len(got) != 0 {
		t.Fatal("las deshabilitadas no cuentan")
	}
}
```

- [ ] **Step 4: Ejecutar y ver que falla**

Run: `go test ./internal/domain/fence/`
Expected: `undefined: Fence`.

- [ ] **Step 5: Implementar `fence.go`**

```go
// Package fence modela geocercas (círculo o polígono) y sus acciones por
// evento. Sin I/O. El borde del círculo es inclusivo; el del polígono queda
// indefinido por diseño (medida cero con GPS real).
package fence

import (
	"errors"
	"fmt"
	"regexp"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Kind es la forma de la geocerca.
type Kind string

// When es el evento que dispara una acción.
type When string

const (
	Circle  Kind = "circle"
	Polygon Kind = "polygon"

	OnEnter     When = "on_enter"
	OnExit      When = "on_exit"
	OnViolation When = "on_violation"
	OnUnknown   When = "on_unknown"
)

// IDPattern es el formato de los identificadores de dominio (slug).
var IDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,63}$`)

// Action es una acción ligada a un evento de geocerca.
type Action struct {
	Action  action.Action  `json:"action"`
	When    When           `json:"when"`
	Params  map[string]any `json:"params,omitempty"`
	Enabled bool           `json:"enabled"`
}

// Rules ajusta el comportamiento de la geocerca.
type Rules struct {
	ViolationIntervalCycles int `json:"violation_interval_cycles,omitempty"`
	DwellSeconds            int `json:"dwell_seconds,omitempty"`
}

// Fence es una geocerca.
type Fence struct {
	ID        string      `json:"id"`
	Name      string      `json:"name"`
	Kind      Kind        `json:"kind"`
	Center    *geo.Point  `json:"center,omitempty"`
	RadiusM   float64     `json:"radius_m,omitempty"`
	Polygon   []geo.Point `json:"polygon,omitempty"`
	Rules     Rules       `json:"rules"`
	Actions   []Action    `json:"actions"`
	CreatedAt time.Time   `json:"created_at"`
	UpdatedAt time.Time   `json:"updated_at"`
}

// Contains indica si el punto cae dentro de la geocerca.
func (f Fence) Contains(p geo.Point) bool {
	switch f.Kind {
	case Circle:
		return f.Center != nil && geo.HaversineM(p, *f.Center) <= f.RadiusM
	case Polygon:
		return geo.PointInPolygon(p, f.Polygon)
	}
	return false
}

// Validate comprueba id, nombre, forma, reglas y acciones.
func (f Fence) Validate() error {
	if !IDPattern.MatchString(f.ID) {
		return fmt.Errorf("id %q inválido: usa minúsculas, dígitos y guiones", f.ID)
	}
	if f.Name == "" {
		return errors.New("nombre obligatorio")
	}
	if err := f.validateShape(); err != nil {
		return err
	}
	if f.Rules.ViolationIntervalCycles < 0 || f.Rules.DwellSeconds < 0 {
		return errors.New("las reglas no admiten valores negativos")
	}
	for i, a := range f.Actions {
		if _, err := action.Parse(string(a.Action)); err != nil {
			return fmt.Errorf("acción %d: %w", i, err)
		}
		switch a.When {
		case OnEnter, OnExit, OnViolation, OnUnknown:
		default:
			return fmt.Errorf("acción %d: evento %q desconocido", i, a.When)
		}
	}
	return nil
}

func (f Fence) validateShape() error {
	switch f.Kind {
	case Circle:
		if f.Center == nil {
			return errors.New("círculo sin centro")
		}
		if err := f.Center.Valid(); err != nil {
			return fmt.Errorf("centro: %w", err)
		}
		if f.RadiusM <= 0 {
			return errors.New("radio debe ser > 0")
		}
	case Polygon:
		if len(f.Polygon) < 3 {
			return geo.ErrEmptyPolygon
		}
		for i, p := range f.Polygon {
			if err := p.Valid(); err != nil {
				return fmt.Errorf("vértice %d: %w", i, err)
			}
		}
	default:
		return fmt.Errorf("tipo %q desconocido (circle|polygon)", f.Kind)
	}
	return nil
}

// ValidateAll valida cada geocerca y la unicidad de ids.
func ValidateAll(fs []Fence) error {
	seen := map[string]bool{}
	for _, f := range fs {
		if err := f.Validate(); err != nil {
			return fmt.Errorf("geocerca %q: %w", f.ID, err)
		}
		if seen[f.ID] {
			return fmt.Errorf("id duplicado %q", f.ID)
		}
		seen[f.ID] = true
	}
	return nil
}

// FindByID busca una geocerca.
func FindByID(fs []Fence, id string) (Fence, bool) {
	for _, f := range fs {
		if f.ID == id {
			return f, true
		}
	}
	return Fence{}, false
}

// ActionsFor devuelve las acciones habilitadas para un evento.
func (f Fence) ActionsFor(w When) []Action {
	var out []Action
	for _, a := range f.Actions {
		if a.Enabled && a.When == w {
			out = append(out, a)
		}
	}
	return out
}
```

- [ ] **Step 6: Ejecutar tests (pasan), documentar, commit**

Run: `go test ./internal/domain/... -cover` → PASS ≥ 85 %.

`ARCHITECTURE.md`, tabla de paquetes:
```
| `internal/domain/action` | Enum de acciones UEM y resultado normalizado de ejecución. |
| `internal/domain/fence` | Geocercas círculo/polígono, pertenencia, validación y acciones por evento. |
```

```bash
git add internal/domain ARCHITECTURE.md
git commit -q -m "feat(domain): acciones UEM y geocercas con validación

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 3: Rutas y POIs (`internal/domain/route`, `internal/domain/poi`)

**Files:**
- Create: `internal/domain/route/route.go` (+`route_test.go`), `internal/domain/poi/poi.go` (+`poi_test.go`)
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces (`route`):
  ```go
  type Route struct { ID string `json:"id"`; Name string `json:"name"`; CorridorM float64 `json:"corridor_m"`; Waypoints []geo.Point `json:"waypoints"`
                      DeviceIDs []string `json:"device_ids"`; Color string `json:"color,omitempty"`; Actions []fence.Action `json:"actions"`
                      CreatedAt time.Time `json:"created_at"`; UpdatedAt time.Time `json:"updated_at"` }
  func (r Route) DistanceM(p geo.Point) float64
  func (r Route) Validate() error
  func ValidateAll(rs []Route) error
  func ForDevice(rs []Route, deviceID string) (Route, bool)
  func FindByID(rs []Route, id string) (Route, bool)
  ```
- Produces (`poi`):
  ```go
  type POI struct { ID string `json:"id"`; Name string `json:"name"`; Category string `json:"category"`; Tags []string `json:"tags,omitempty"`
                    Point geo.Point `json:"point"`; Metadata map[string]string `json:"metadata,omitempty"` }
  func (p POI) Validate() error
  func ValidateAll(ps []POI) error
  func FindByID(ps []POI, id string) (POI, bool)
  func ToGeoJSON(ps []POI) map[string]any  // FeatureCollection con geometry Point [lng, lat]
  ```

- [ ] **Step 1: Tests (fallan)**

`internal/domain/route/route_test.go`:
```go
package route

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func sample() Route {
	return Route{ID: "route-centro", Name: "Ruta Comercial Centro", CorridorM: 300, DeviceIDs: []string{"dev-002"},
		Waypoints: []geo.Point{{Lat: 40.43, Lng: -3.69}, {Lat: 40.42, Lng: -3.71}},
		Actions:   []fence.Action{{Action: action.Notify, When: fence.OnExit, Enabled: true, Params: map[string]any{"msg": "fuera de ruta"}}}}
}

func TestDistanceMYForDevice(t *testing.T) {
	r := sample()
	if d := r.DistanceM(geo.Point{Lat: 40.43, Lng: -3.69}); d > 0.01 {
		t.Fatalf("waypoint sobre la ruta: %v", d)
	}
	if d := r.DistanceM(geo.Point{Lat: 40.44, Lng: -3.69}); d < 1000 {
		t.Fatalf("1 km al norte: %v", d)
	}
	if got, ok := ForDevice([]Route{r}, "dev-002"); !ok || got.ID != "route-centro" {
		t.Fatal("ForDevice")
	}
	if _, ok := ForDevice([]Route{r}, "dev-001"); ok {
		t.Fatal("dev-001 no tiene ruta")
	}
}

func TestValidate(t *testing.T) {
	bad := map[string]Route{
		"id":        {ID: "Ruta", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}},
		"nombre":    {ID: "r", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}},
		"corredor":  {ID: "r", Name: "x", CorridorM: 0, Waypoints: []geo.Point{{}, {Lat: 1}}},
		"waypoints": {ID: "r", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}}},
		"coords":    {ID: "r", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 99}}},
		"when":      {ID: "r", Name: "x", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}, Actions: []fence.Action{{Action: action.Notify, When: fence.OnEnter}}},
	}
	for name, r := range bad {
		if err := r.Validate(); err == nil {
			t.Errorf("%s: debería fallar", name)
		}
	}
	if err := sample().Validate(); err != nil {
		t.Fatal(err)
	}
	if err := ValidateAll([]Route{sample(), sample()}); err == nil {
		t.Fatal("ids duplicados")
	}
}
```

`internal/domain/poi/poi_test.go`:
```go
package poi

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestValidateYGeoJSON(t *testing.T) {
	p := POI{ID: "poi-school-001", Name: "Colegio Público", Category: "school", Tags: []string{"education"}, Point: geo.Point{Lat: 40.418, Lng: -3.705}}
	if err := p.Validate(); err != nil {
		t.Fatal(err)
	}
	for name, bad := range map[string]POI{
		"id":       {ID: "POI 1", Name: "x", Category: "c", Point: geo.Point{}},
		"nombre":   {ID: "p", Category: "c"},
		"category": {ID: "p", Name: "x"},
		"coords":   {ID: "p", Name: "x", Category: "c", Point: geo.Point{Lng: 200}},
	} {
		if err := bad.Validate(); err == nil {
			t.Errorf("%s: debería fallar", name)
		}
	}
	if err := ValidateAll([]POI{p, p}); err == nil {
		t.Fatal("duplicado")
	}
	fc := ToGeoJSON([]POI{p})
	feats := fc["features"].([]map[string]any)
	geom := feats[0]["geometry"].(map[string]any)
	coords := geom["coordinates"].([]float64)
	if fc["type"] != "FeatureCollection" || coords[0] != -3.705 || coords[1] != 40.418 {
		t.Fatalf("GeoJSON incorrecto: %v", fc)
	}
	if _, ok := FindByID([]POI{p}, "poi-school-001"); !ok {
		t.Fatal("FindByID")
	}
}
```

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `go test ./internal/domain/route/ ./internal/domain/poi/`
Expected: `undefined: Route` y `undefined: POI`.

- [ ] **Step 3: Implementar `route.go`**

```go
// Package route modela rutas con corredor: una polilínea y una anchura en
// metros. Un dispositivo asignado está on_route si su distancia a la
// polilínea no supera el corredor.
package route

import (
	"errors"
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Route es una ruta con corredor.
type Route struct {
	ID        string         `json:"id"`
	Name      string         `json:"name"`
	CorridorM float64        `json:"corridor_m"`
	Waypoints []geo.Point    `json:"waypoints"`
	DeviceIDs []string       `json:"device_ids"`
	Color     string         `json:"color,omitempty"`
	Actions   []fence.Action `json:"actions"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
}

// DistanceM es la distancia del punto a la polilínea.
func (r Route) DistanceM(p geo.Point) float64 {
	return geo.DistanceToPolylineM(p, r.Waypoints)
}

// Validate comprueba id, nombre, corredor, waypoints y acciones (solo on_exit).
func (r Route) Validate() error {
	if !fence.IDPattern.MatchString(r.ID) {
		return fmt.Errorf("id %q inválido", r.ID)
	}
	if r.Name == "" {
		return errors.New("nombre obligatorio")
	}
	if r.CorridorM <= 0 {
		return errors.New("corredor debe ser > 0")
	}
	if len(r.Waypoints) < 2 {
		return errors.New("una ruta necesita al menos 2 waypoints")
	}
	for i, w := range r.Waypoints {
		if err := w.Valid(); err != nil {
			return fmt.Errorf("waypoint %d: %w", i, err)
		}
	}
	for i, a := range r.Actions {
		if a.When != fence.OnExit {
			return fmt.Errorf("acción %d: las rutas solo admiten on_exit", i)
		}
	}
	return nil
}

// ValidateAll valida y exige ids únicos.
func ValidateAll(rs []Route) error {
	seen := map[string]bool{}
	for _, r := range rs {
		if err := r.Validate(); err != nil {
			return fmt.Errorf("ruta %q: %w", r.ID, err)
		}
		if seen[r.ID] {
			return fmt.Errorf("id duplicado %q", r.ID)
		}
		seen[r.ID] = true
	}
	return nil
}

// ForDevice devuelve la primera ruta asignada al dispositivo.
func ForDevice(rs []Route, deviceID string) (Route, bool) {
	for _, r := range rs {
		for _, id := range r.DeviceIDs {
			if id == deviceID {
				return r, true
			}
		}
	}
	return Route{}, false
}

// FindByID busca una ruta.
func FindByID(rs []Route, id string) (Route, bool) {
	for _, r := range rs {
		if r.ID == id {
			return r, true
		}
	}
	return Route{}, false
}
```

- [ ] **Step 4: Implementar `poi.go`**

```go
// Package poi modela puntos de interés que dan contexto al riesgo (colegios,
// hospitales, zonas restringidas). Se exportan como GeoJSON para el mapa.
package poi

import (
	"errors"
	"fmt"

	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// POI es un punto de interés.
type POI struct {
	ID       string            `json:"id"`
	Name     string            `json:"name"`
	Category string            `json:"category"`
	Tags     []string          `json:"tags,omitempty"`
	Point    geo.Point         `json:"point"`
	Metadata map[string]string `json:"metadata,omitempty"`
}

// Validate comprueba id, nombre, categoría y coordenadas.
func (p POI) Validate() error {
	if !fence.IDPattern.MatchString(p.ID) {
		return fmt.Errorf("id %q inválido", p.ID)
	}
	if p.Name == "" {
		return errors.New("nombre obligatorio")
	}
	if p.Category == "" {
		return errors.New("categoría obligatoria")
	}
	if err := p.Point.Valid(); err != nil {
		return err
	}
	return nil
}

// ValidateAll valida y exige ids únicos.
func ValidateAll(ps []POI) error {
	seen := map[string]bool{}
	for _, p := range ps {
		if err := p.Validate(); err != nil {
			return fmt.Errorf("poi %q: %w", p.ID, err)
		}
		if seen[p.ID] {
			return fmt.Errorf("id duplicado %q", p.ID)
		}
		seen[p.ID] = true
	}
	return nil
}

// FindByID busca un POI.
func FindByID(ps []POI, id string) (POI, bool) {
	for _, p := range ps {
		if p.ID == id {
			return p, true
		}
	}
	return POI{}, false
}

// ToGeoJSON construye una FeatureCollection (coordenadas [lng, lat]).
func ToGeoJSON(ps []POI) map[string]any {
	features := make([]map[string]any, 0, len(ps))
	for _, p := range ps {
		features = append(features, map[string]any{
			"type": "Feature",
			"properties": map[string]any{"id": p.ID, "name": p.Name, "category": p.Category, "tags": p.Tags, "metadata": p.Metadata},
			"geometry":   map[string]any{"type": "Point", "coordinates": []float64{p.Point.Lng, p.Point.Lat}},
		})
	}
	return map[string]any{"type": "FeatureCollection", "features": features}
}
```

- [ ] **Step 5: Tests (pasan), documentar, commit**

Run: `go test ./internal/domain/... -cover` → PASS.

`ARCHITECTURE.md`:
```
| `internal/domain/route` | Rutas con corredor: distancia a la polilínea, asignación por dispositivo. |
| `internal/domain/poi` | Puntos de interés y su exportación GeoJSON. |
```

```bash
git add internal/domain ARCHITECTURE.md
git commit -q -m "feat(domain): rutas con corredor y puntos de interés

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 4: Dispositivos y transiciones (`internal/domain/device`, `internal/domain/transition`)

**Files:**
- Create: `internal/domain/device/device.go` (+`device_test.go`), `internal/domain/transition/transition.go` (+`transition_test.go`)
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces (`device`):
  ```go
  type FenceState string   // Inside="inside" | Outside="outside" | Unknown="unknown"
  type RouteState string   // OnRoute="on_route" | OffRoute="off_route" | Unassigned="unassigned"
  type Location struct { Point *geo.Point `json:"point,omitempty"`; AccuracyM *float64 `json:"accuracy_m,omitempty"`; Source string `json:"source"`; ObservedAt time.Time `json:"observed_at"` }
  type Network struct { IP string `json:"ip,omitempty"`; SSID string `json:"ssid,omitempty"`; BSSID string `json:"bssid,omitempty"` }
  type App struct { Name string `json:"name"`; Version string `json:"version"` }
  type Inventory struct { OSVersion, Model, Manufacturer, SerialNumber, IMEI string; BatteryLevel *int; BatteryState string
                          StorageTotalGB, StorageFreeGB *float64; EncryptionEnabled *bool; Carrier, AssignedUser, Department, DeviceTag string
                          EnrolledAt, LastCheckin *time.Time; ManagementMode, Ownership string; Supervised, LockdownMode *bool; Apps []App }  // tags snake_case
  type Verdict struct { Score *float64 `json:"score"`; Severity string `json:"severity"`; Reasons []string `json:"reasons"`; MatchedPolicies []string `json:"matched_policies"`
                        EvaluatedAt *time.Time `json:"evaluated_at,omitempty"`; Provenance string `json:"provenance"`; Verified bool `json:"verified"` }
  type Device struct { ID, Name, Platform, Status string; Compliant *bool; Provider string; ProviderRefs map[string]string; Location Location; Network Network; Inventory Inventory
                       FenceState FenceState; InsideFence string; LastInsideFence string; RouteID string; RouteState RouteState; RouteDeviationM *float64
                       Risk Verdict; EvaluationError string; LastReportAt time.Time }   // tags snake_case (`id`, `name`, `fence_state`, `inside_fence`, ...)
  type TrailPoint struct { At time.Time `json:"at"`; Point geo.Point `json:"point"` }
  func (d Device) Validate() error
  func Index(ds []Device) map[string]Device
  ```
- Produces (`transition`):
  ```go
  type Transition struct { At time.Time `json:"at"`; DeviceID string `json:"device_id"`; DeviceName string `json:"device_name"`; From string `json:"from"`; To string `json:"to"` }
  func EvaluateFence(loc *geo.Point, fences []fence.Fence) (device.FenceState, string) // primera geocerca que contiene gana; sin loc → unknown
  func Key(insideID string, state device.FenceState) string                            // "none:unknown", "demo-hq:inside", "none:outside"
  func Evaluate(prev *device.Device, cur *device.Device, fences []fence.Fence, at time.Time) *Transition
      // rellena cur.FenceState, cur.InsideFence, cur.LastInsideFence; devuelve la transición si la clave cambia respecto a prev
  ```

- [ ] **Step 1: Tests (fallan)**

`internal/domain/device/device_test.go`:
```go
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
```

`internal/domain/transition/transition_test.go`:
```go
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

func TestEvaluateDetectaTransicionesYConservaLastInside(t *testing.T) {
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	cur := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 40.421, Lng: -3.708}}}
	tr := Evaluate(nil, &cur, fences, at)
	if tr == nil || tr.From != "none:unknown" || tr.To != "demo-hq:inside" || tr.DeviceID != "dev-1" || !tr.At.Equal(at) {
		t.Fatalf("primera evaluación: %+v", tr)
	}
	if cur.FenceState != device.Inside || cur.InsideFence != "demo-hq" || cur.LastInsideFence != "demo-hq" {
		t.Fatalf("estado: %+v", cur)
	}
	prev := cur
	same := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 40.4212, Lng: -3.708}}}
	if tr := Evaluate(&prev, &same, fences, at); tr != nil {
		t.Fatalf("sin cambio de clave no hay transición: %+v", tr)
	}
	prev = same
	unknown := device.Device{ID: "dev-1", Name: "Uno"}
	tr = Evaluate(&prev, &unknown, fences, at)
	if tr == nil || tr.To != "none:unknown" || unknown.LastInsideFence != "demo-hq" {
		t.Fatalf("a unknown conserva last_inside_fence: %+v %+v", tr, unknown)
	}
	prev = unknown
	out := device.Device{ID: "dev-1", Name: "Uno", Location: device.Location{Point: &geo.Point{Lat: 41, Lng: -3}}}
	tr = Evaluate(&prev, &out, fences, at)
	if tr == nil || tr.From != "none:unknown" || tr.To != "none:outside" || out.LastInsideFence != "" {
		t.Fatalf("a outside: %+v %+v", tr, out)
	}
}
```

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `go test ./internal/domain/device/ ./internal/domain/transition/`
Expected: `undefined: Device`, `undefined: EvaluateFence`.

- [ ] **Step 3: Implementar `device.go`**

```go
// Package device es el modelo normalizado de dispositivo que produce todo
// conector y consume el motor. Los campos que el UEM no informa son nil, no
// cero: el riesgo nunca penaliza lo desconocido.
package device

import (
	"errors"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// FenceState es la relación del dispositivo con las geocercas.
type FenceState string

// RouteState es la relación con su ruta asignada.
type RouteState string

const (
	Inside  FenceState = "inside"
	Outside FenceState = "outside"
	Unknown FenceState = "unknown"

	OnRoute    RouteState = "on_route"
	OffRoute   RouteState = "off_route"
	Unassigned RouteState = "unassigned"
)

// Location es la última ubicación conocida.
type Location struct {
	Point      *geo.Point `json:"point,omitempty"`
	AccuracyM  *float64   `json:"accuracy_m,omitempty"`
	Source     string     `json:"source"`
	ObservedAt time.Time  `json:"observed_at"`
}

// Network son las señales de red del dispositivo.
type Network struct {
	IP    string `json:"ip,omitempty"`
	SSID  string `json:"ssid,omitempty"`
	BSSID string `json:"bssid,omitempty"`
}

// App es una aplicación instalada.
type App struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// Inventory es la ficha de IT del dispositivo.
type Inventory struct {
	OSVersion         string     `json:"os_version,omitempty"`
	Model             string     `json:"model,omitempty"`
	Manufacturer      string     `json:"manufacturer,omitempty"`
	SerialNumber      string     `json:"serial_number,omitempty"`
	IMEI              string     `json:"imei,omitempty"`
	BatteryLevel      *int       `json:"battery_level,omitempty"`
	BatteryState      string     `json:"battery_state,omitempty"`
	StorageTotalGB    *float64   `json:"storage_total_gb,omitempty"`
	StorageFreeGB     *float64   `json:"storage_free_gb,omitempty"`
	EncryptionEnabled *bool      `json:"encryption_enabled,omitempty"`
	Carrier           string     `json:"carrier,omitempty"`
	AssignedUser      string     `json:"assigned_user,omitempty"`
	Department        string     `json:"department,omitempty"`
	DeviceTag         string     `json:"device_tag,omitempty"`
	EnrolledAt        *time.Time `json:"enrolled_at,omitempty"`
	LastCheckin       *time.Time `json:"last_checkin,omitempty"`
	ManagementMode    string     `json:"management_mode,omitempty"`
	Ownership         string     `json:"ownership,omitempty"`
	Supervised        *bool      `json:"supervised,omitempty"`
	LockdownMode      *bool      `json:"lockdown_mode,omitempty"`
	Apps              []App      `json:"apps,omitempty"`
}

// Verdict es el veredicto de riesgo explicable. Score nil = sin evaluar o
// evaluación fallida (nunca 0 por defecto).
type Verdict struct {
	Score           *float64   `json:"score"`
	Severity        string     `json:"severity"`
	Reasons         []string   `json:"reasons"`
	MatchedPolicies []string   `json:"matched_policies"`
	EvaluatedAt     *time.Time `json:"evaluated_at,omitempty"`
	Provenance      string     `json:"provenance"`
	Verified        bool       `json:"verified"`
}

// Device es el dispositivo normalizado.
type Device struct {
	ID              string            `json:"id"`
	Name            string            `json:"name"`
	Platform        string            `json:"platform"`
	Status          string            `json:"status,omitempty"`
	Compliant       *bool             `json:"compliant"`
	Provider        string            `json:"provider"`
	ProviderRefs    map[string]string `json:"provider_refs,omitempty"`
	Location        Location          `json:"location"`
	Network         Network           `json:"network"`
	Inventory       Inventory         `json:"inventory"`
	FenceState      FenceState        `json:"fence_state"`
	InsideFence     string            `json:"inside_fence"`
	LastInsideFence string            `json:"last_inside_fence"`
	RouteID         string            `json:"route_id,omitempty"`
	RouteState      RouteState        `json:"route_state"`
	RouteDeviationM *float64          `json:"route_deviation_m,omitempty"`
	Risk            Verdict           `json:"risk"`
	EvaluationError string            `json:"evaluation_error,omitempty"`
	LastReportAt    time.Time         `json:"last_report_at"`
}

// TrailPoint es una posición histórica.
type TrailPoint struct {
	At    time.Time `json:"at"`
	Point geo.Point `json:"point"`
}

// Validate exige id.
func (d Device) Validate() error {
	if d.ID == "" {
		return errors.New("dispositivo sin id")
	}
	return nil
}

// Index indexa por id.
func Index(ds []Device) map[string]Device {
	out := make(map[string]Device, len(ds))
	for _, d := range ds {
		out[d.ID] = d
	}
	return out
}
```

- [ ] **Step 4: Implementar `transition.go`**

```go
// Package transition evalúa la pertenencia a geocerca de un dispositivo y
// detecta cambios de estado entre ciclos. Semántica 1.x: la primera geocerca
// (en orden de lista) que contiene el punto gana; sin ubicación válida el
// estado es unknown, nunca outside.
package transition

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// Transition es un cambio de clave de estado.
type Transition struct {
	At         time.Time `json:"at"`
	DeviceID   string    `json:"device_id"`
	DeviceName string    `json:"device_name"`
	From       string    `json:"from"`
	To         string    `json:"to"`
}

// EvaluateFence devuelve el estado y la geocerca contenedora.
func EvaluateFence(loc *geo.Point, fences []fence.Fence) (device.FenceState, string) {
	if loc == nil || loc.Valid() != nil {
		return device.Unknown, ""
	}
	for _, f := range fences {
		if f.Contains(*loc) {
			return device.Inside, f.ID
		}
	}
	return device.Outside, ""
}

// Key compone la clave "<fence|none>:<estado>".
func Key(insideID string, state device.FenceState) string {
	if insideID == "" {
		insideID = "none"
	}
	return insideID + ":" + string(state)
}

// Evaluate rellena los campos de geocerca de cur a partir de prev y devuelve
// la transición si la clave cambia. prev puede ser nil (primer ciclo).
func Evaluate(prev *device.Device, cur *device.Device, fences []fence.Fence, at time.Time) *Transition {
	state, inside := EvaluateFence(cur.Location.Point, fences)
	cur.FenceState, cur.InsideFence = state, inside
	switch state {
	case device.Unknown:
		if prev != nil {
			cur.LastInsideFence = prev.InsideFence
			if cur.LastInsideFence == "" {
				cur.LastInsideFence = prev.LastInsideFence
			}
		}
	default:
		cur.LastInsideFence = inside
	}
	prevKey := "none:unknown"
	if prev != nil {
		prevKey = Key(prev.InsideFence, prev.FenceState)
	}
	curKey := Key(inside, state)
	if prevKey == curKey {
		return nil
	}
	return &Transition{At: at, DeviceID: cur.ID, DeviceName: cur.Name, From: prevKey, To: curKey}
}
```

- [ ] **Step 5: Tests (pasan), documentar, commit**

Run: `go test ./internal/domain/... -cover` → PASS ≥ 85 % en cada paquete.

`ARCHITECTURE.md`:
```
| `internal/domain/device` | Dispositivo normalizado, inventario, veredicto de riesgo, trail. |
| `internal/domain/transition` | Evaluación de geocerca por ciclo y detección de transiciones. |
```

```bash
git add internal/domain ARCHITECTURE.md
git commit -q -m "feat(domain): modelo de dispositivo y transiciones de geocerca

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 5: Persistencia (`internal/store`)

**Files:**
- Create: `internal/store/store.go`, `internal/store/jsonl.go`, `internal/store/orgstore.go`, `internal/store/store_test.go`, `internal/store/orgstore_test.go`
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces:
  ```go
  var ErrNotFound = errors.New("no existe")
  type Store struct{ root string }
  func Open(root string) (*Store, error)           // crea root/orgs, root/auth, root/secrets, root/cache con 0700
  func (s *Store) Root() string; AuthDir() string; CacheDir() string
  func (s *Store) Org(id string) (*OrgStore, error) // id ^[a-z0-9][a-z0-9-]{0,39}$; crea root/orgs/<id>
  func WriteJSON(path string, v any) error          // temporal + fsync + rename, 0600
  func ReadJSON(path string, v any) error           // ErrNotFound si falta
  func AppendJSONL(path string, v any) error        // O_APPEND, 0600, una línea
  func ReadJSONL(path string, limit int) ([]json.RawMessage, error) // últimas limit líneas en orden cronológico; limit<=0 → todas; falta → vacío
  type OrgStore struct{ ... }
  func (o *OrgStore) ID() string; Dir() string; Path(name string) string
  func (o *OrgStore) Fences() ([]fence.Fence, error); SaveFences([]fence.Fence) error
  func (o *OrgStore) Routes() ([]route.Route, error); SaveRoutes([]route.Route) error
  func (o *OrgStore) POIs() ([]poi.POI, error); SavePOIs([]poi.POI) error
  func (o *OrgStore) Devices() ([]device.Device, error); SaveDevices([]device.Device) error
  func (o *OrgStore) AppendEvent(transition.Transition) error; RecentEvents(limit int) ([]transition.Transition, error)
  func (o *OrgStore) AppendAction(action.Result) error; RecentActions(limit int) ([]action.Result, error)
  func (o *OrgStore) AppendTrail(deviceID string, p geo.Point, at time.Time) error; Trail(deviceID string, limit int) ([]device.TrailPoint, error)
  func (o *OrgStore) AppendStats(v any) error; RecentStats(limit int) ([]json.RawMessage, error)
  ```
  Ficheros: `fences.json`, `routes.json`, `pois.json`, `devices.json` con envoltorio `{"schema_version":1,"items":[...]}`; `events.jsonl`, `actions.jsonl`, `trail.jsonl`, `stats.jsonl`.

- [ ] **Step 1: Tests de primitivas (fallan)**

`internal/store/store_test.go`:
```go
package store

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestOpenCreaDirectorios0700(t *testing.T) {
	root := filepath.Join(t.TempDir(), "data")
	s, err := Open(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, d := range []string{"orgs", "auth", "secrets", "cache"} {
		info, err := os.Stat(filepath.Join(root, d))
		if err != nil {
			t.Fatal(err)
		}
		if runtime.GOOS != "windows" && info.Mode().Perm() != 0o700 {
			t.Fatalf("%s: permisos %o", d, info.Mode().Perm())
		}
	}
	if s.Root() != root || s.AuthDir() != filepath.Join(root, "auth") || s.CacheDir() != filepath.Join(root, "cache") {
		t.Fatal("rutas")
	}
}

func TestOrgValidaIDYCreaDir(t *testing.T) {
	s, _ := Open(t.TempDir())
	for _, bad := range []string{"", "Default", "a b", "../x", "x/y"} {
		if _, err := s.Org(bad); err == nil {
			t.Fatalf("org %q debería fallar", bad)
		}
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	if o.ID() != "default" || o.Dir() != filepath.Join(s.Root(), "orgs", "default") || o.Path("fences.json") != filepath.Join(o.Dir(), "fences.json") {
		t.Fatal("rutas de org")
	}
}

func TestWriteJSONAtomicoYReadJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "x.json")
	var got map[string]int
	if err := ReadJSON(path, &got); !errors.Is(err, ErrNotFound) {
		t.Fatalf("esperaba ErrNotFound, got %v", err)
	}
	if err := WriteJSON(path, map[string]int{"a": 1}); err != nil {
		t.Fatal(err)
	}
	if err := ReadJSON(path, &got); err != nil || got["a"] != 1 {
		t.Fatalf("round-trip: %v %v", err, got)
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 {
		t.Fatalf("no deben quedar temporales: %v", entries)
	}
	if runtime.GOOS != "windows" {
		info, _ := os.Stat(path)
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("permisos %o", info.Mode().Perm())
		}
	}
	// Un valor no serializable no debe tocar el fichero existente.
	if err := WriteJSON(path, make(chan int)); err == nil {
		t.Fatal("esperaba error de serialización")
	}
	if err := ReadJSON(path, &got); err != nil || got["a"] != 1 {
		t.Fatal("el fichero previo debe seguir intacto")
	}
}

func TestJSONLAppendYUltimasN(t *testing.T) {
	path := filepath.Join(t.TempDir(), "e.jsonl")
	if lines, err := ReadJSONL(path, 10); err != nil || len(lines) != 0 {
		t.Fatalf("fichero ausente: %v %v", err, lines)
	}
	for i := 1; i <= 5; i++ {
		if err := AppendJSONL(path, map[string]int{"n": i}); err != nil {
			t.Fatal(err)
		}
	}
	lines, err := ReadJSONL(path, 2)
	if err != nil || len(lines) != 2 || string(lines[0]) != `{"n":4}` || string(lines[1]) != `{"n":5}` {
		t.Fatalf("últimas 2: %v %s", err, lines)
	}
	all, _ := ReadJSONL(path, 0)
	if len(all) != 5 {
		t.Fatalf("todas: %d", len(all))
	}
}
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `go test ./internal/store/`
Expected: `undefined: Open`.

- [ ] **Step 3: Implementar `store.go` y `jsonl.go`**

`internal/store/store.go`:
```go
// Package store persiste el estado de LucidFence en JSON y JSONL en disco
// (ADR: sin base de datos). Escrituras atómicas (temporal + rename), permisos
// 0600/0700, un lock por organización.
package store

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
)

// ErrNotFound indica que el fichero o documento no existe.
var ErrNotFound = errors.New("no existe")

var orgIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,39}$`)

// Store es la raíz del directorio de datos.
type Store struct{ root string }

// Open crea la estructura de directorios si falta.
func Open(root string) (*Store, error) {
	for _, d := range []string{"", "orgs", "auth", "secrets", "cache"} {
		if err := os.MkdirAll(filepath.Join(root, d), 0o700); err != nil {
			return nil, fmt.Errorf("crear %s: %w", filepath.Join(root, d), err)
		}
	}
	return &Store{root: root}, nil
}

// Root devuelve el directorio de datos.
func (s *Store) Root() string { return s.root }

// AuthDir devuelve el directorio de usuarios y sesiones.
func (s *Store) AuthDir() string { return filepath.Join(s.root, "auth") }

// CacheDir devuelve el directorio de cachés (CVE).
func (s *Store) CacheDir() string { return filepath.Join(s.root, "cache") }

// Org abre (creando si falta) el almacén de una organización.
func (s *Store) Org(id string) (*OrgStore, error) {
	if !orgIDPattern.MatchString(id) {
		return nil, fmt.Errorf("id de organización %q inválido", id)
	}
	dir := filepath.Join(s.root, "orgs", id)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	return &OrgStore{id: id, dir: dir}, nil
}

// WriteJSON escribe v de forma atómica con permisos 0600.
func WriteJSON(path string, v any) error {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return fmt.Errorf("serializar %s: %w", filepath.Base(path), err)
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if err := tmp.Chmod(0o600); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(append(data, '\n')); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmp.Name(), path)
}

// ReadJSON lee un fichero JSON; ErrNotFound si falta.
func ReadJSON(path string, v any) error {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return ErrNotFound
	}
	if err != nil {
		return err
	}
	if err := json.Unmarshal(data, v); err != nil {
		return fmt.Errorf("leer %s: %w", filepath.Base(path), err)
	}
	return nil
}
```

`internal/store/jsonl.go`:
```go
package store

import (
	"bufio"
	"encoding/json"
	"errors"
	"os"
)

// AppendJSONL añade una línea JSON al final del fichero (solo append).
func AppendJSONL(path string, v any) error {
	line, err := json.Marshal(v)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(line, '\n'))
	return err
}

// ReadJSONL devuelve las últimas limit líneas (todas si limit <= 0) en orden
// cronológico. Un fichero ausente equivale a vacío. Lee el fichero completo:
// suficiente para volúmenes de flota; no es un log de big data.
func ReadJSONL(path string, limit int) ([]json.RawMessage, error) {
	f, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []json.RawMessage
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1024*1024), 8*1024*1024)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		out = append(out, json.RawMessage(append([]byte(nil), line...)))
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if limit > 0 && len(out) > limit {
		out = out[len(out)-limit:]
	}
	return out, nil
}
```

Run: `go test ./internal/store/ -run 'TestOpen|TestOrg|TestWriteJSON|TestJSONL' -v` → PASS.

- [ ] **Step 4: Tests del almacén de org (fallan)**

`internal/store/orgstore_test.go`:
```go
package store

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

func org(t *testing.T) *OrgStore {
	t.Helper()
	s, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	return o
}

func TestColeccionesVaciasYRoundTrip(t *testing.T) {
	o := org(t)
	fs, err := o.Fences()
	if err != nil || len(fs) != 0 {
		t.Fatalf("sin fichero → vacío: %v %v", err, fs)
	}
	want := []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500}}
	if err := o.SaveFences(want); err != nil {
		t.Fatal(err)
	}
	got, _ := o.Fences()
	if len(got) != 1 || got[0].ID != "demo-hq" || got[0].Center.Lat != 40.421 {
		t.Fatalf("fences: %+v", got)
	}
	if err := o.SaveRoutes([]route.Route{{ID: "r1", Name: "R", CorridorM: 10, Waypoints: []geo.Point{{}, {Lat: 1}}}}); err != nil {
		t.Fatal(err)
	}
	if rs, _ := o.Routes(); len(rs) != 1 || rs[0].ID != "r1" {
		t.Fatal("routes")
	}
	if err := o.SavePOIs([]poi.POI{{ID: "p1", Name: "P", Category: "c"}}); err != nil {
		t.Fatal(err)
	}
	if ps, _ := o.POIs(); len(ps) != 1 {
		t.Fatal("pois")
	}
	if err := o.SaveDevices([]device.Device{{ID: "dev-1", Name: "Uno"}}); err != nil {
		t.Fatal(err)
	}
	if ds, _ := o.Devices(); len(ds) != 1 || ds[0].Name != "Uno" {
		t.Fatal("devices")
	}
	var raw map[string]any
	if err := ReadJSON(o.Path("fences.json"), &raw); err != nil || raw["schema_version"].(float64) != 1 {
		t.Fatalf("envoltorio schema_version: %v %v", err, raw)
	}
}

func TestLogsAppendOnly(t *testing.T) {
	o := org(t)
	at := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		if err := o.AppendEvent(transition.Transition{At: at, DeviceID: "dev-1", From: "none:unknown", To: "demo-hq:inside"}); err != nil {
			t.Fatal(err)
		}
	}
	evs, err := o.RecentEvents(2)
	if err != nil || len(evs) != 2 || evs[0].To != "demo-hq:inside" || !evs[0].At.Equal(at) {
		t.Fatalf("events: %v %+v", err, evs)
	}
	if err := o.AppendAction(action.Result{Adapter: "simulation", OK: true, DeviceID: "dev-1", Action: action.Message, DryRun: true, At: at}); err != nil {
		t.Fatal(err)
	}
	acts, _ := o.RecentActions(10)
	if len(acts) != 1 || acts[0].Action != action.Message || !acts[0].DryRun {
		t.Fatalf("actions: %+v", acts)
	}
	for i := 0; i < 3; i++ {
		_ = o.AppendTrail("dev-1", geo.Point{Lat: float64(i)}, at.Add(time.Duration(i)*time.Minute))
	}
	_ = o.AppendTrail("dev-2", geo.Point{Lat: 9}, at)
	tr, _ := o.Trail("dev-1", 2)
	if len(tr) != 2 || tr[0].Point.Lat != 1 || tr[1].Point.Lat != 2 {
		t.Fatalf("trail: %+v", tr)
	}
	_ = o.AppendStats(map[string]int{"devices_total": 6})
	st, _ := o.RecentStats(5)
	if len(st) != 1 {
		t.Fatal("stats")
	}
}
```

- [ ] **Step 5: Implementar `orgstore.go`**

```go
package store

import (
	"encoding/json"
	"errors"
	"path/filepath"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

const schemaVersion = 1

// OrgStore es el almacén de una organización (tenant local).
type OrgStore struct {
	id  string
	dir string
	mu  sync.RWMutex
}

// ID devuelve el id de la organización.
func (o *OrgStore) ID() string { return o.id }

// Dir devuelve el directorio de la organización.
func (o *OrgStore) Dir() string { return o.dir }

// Path devuelve la ruta de un fichero dentro de la organización.
func (o *OrgStore) Path(name string) string { return filepath.Join(o.dir, name) }

type collection[T any] struct {
	SchemaVersion int `json:"schema_version"`
	Items         []T `json:"items"`
}

func readCollection[T any](o *OrgStore, name string) ([]T, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	var c collection[T]
	err := ReadJSON(o.Path(name), &c)
	if errors.Is(err, ErrNotFound) {
		return []T{}, nil
	}
	if err != nil {
		return nil, err
	}
	if c.Items == nil {
		c.Items = []T{}
	}
	return c.Items, nil
}

func writeCollection[T any](o *OrgStore, name string, items []T) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	if items == nil {
		items = []T{}
	}
	return WriteJSON(o.Path(name), collection[T]{SchemaVersion: schemaVersion, Items: items})
}

// Fences lee las geocercas.
func (o *OrgStore) Fences() ([]fence.Fence, error) { return readCollection[fence.Fence](o, "fences.json") }

// SaveFences escribe las geocercas.
func (o *OrgStore) SaveFences(fs []fence.Fence) error { return writeCollection(o, "fences.json", fs) }

// Routes lee las rutas.
func (o *OrgStore) Routes() ([]route.Route, error) { return readCollection[route.Route](o, "routes.json") }

// SaveRoutes escribe las rutas.
func (o *OrgStore) SaveRoutes(rs []route.Route) error { return writeCollection(o, "routes.json", rs) }

// POIs lee los puntos de interés.
func (o *OrgStore) POIs() ([]poi.POI, error) { return readCollection[poi.POI](o, "pois.json") }

// SavePOIs escribe los puntos de interés.
func (o *OrgStore) SavePOIs(ps []poi.POI) error { return writeCollection(o, "pois.json", ps) }

// Devices lee el último estado de los dispositivos.
func (o *OrgStore) Devices() ([]device.Device, error) { return readCollection[device.Device](o, "devices.json") }

// SaveDevices escribe el estado de los dispositivos.
func (o *OrgStore) SaveDevices(ds []device.Device) error { return writeCollection(o, "devices.json", ds) }

func appendLine(o *OrgStore, name string, v any) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	return AppendJSONL(o.Path(name), v)
}

func readLines[T any](o *OrgStore, name string, limit int) ([]T, error) {
	o.mu.RLock()
	raws, err := ReadJSONL(o.Path(name), limit)
	o.mu.RUnlock()
	if err != nil {
		return nil, err
	}
	out := make([]T, 0, len(raws))
	for _, r := range raws {
		var v T
		if err := json.Unmarshal(r, &v); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, nil
}

// AppendEvent registra una transición.
func (o *OrgStore) AppendEvent(t transition.Transition) error { return appendLine(o, "events.jsonl", t) }

// RecentEvents devuelve las últimas transiciones.
func (o *OrgStore) RecentEvents(limit int) ([]transition.Transition, error) {
	return readLines[transition.Transition](o, "events.jsonl", limit)
}

// AppendAction registra el resultado de una acción.
func (o *OrgStore) AppendAction(r action.Result) error { return appendLine(o, "actions.jsonl", r) }

// RecentActions devuelve los últimos resultados de acciones.
func (o *OrgStore) RecentActions(limit int) ([]action.Result, error) {
	return readLines[action.Result](o, "actions.jsonl", limit)
}

type trailLine struct {
	DeviceID string    `json:"device_id"`
	At       time.Time `json:"at"`
	Point    geo.Point `json:"point"`
}

// AppendTrail registra una posición.
func (o *OrgStore) AppendTrail(deviceID string, p geo.Point, at time.Time) error {
	return appendLine(o, "trail.jsonl", trailLine{DeviceID: deviceID, At: at, Point: p})
}

// Trail devuelve las últimas posiciones de un dispositivo.
func (o *OrgStore) Trail(deviceID string, limit int) ([]device.TrailPoint, error) {
	all, err := readLines[trailLine](o, "trail.jsonl", 0)
	if err != nil {
		return nil, err
	}
	var out []device.TrailPoint
	for _, l := range all {
		if l.DeviceID == deviceID {
			out = append(out, device.TrailPoint{At: l.At, Point: l.Point})
		}
	}
	if limit > 0 && len(out) > limit {
		out = out[len(out)-limit:]
	}
	if out == nil {
		out = []device.TrailPoint{}
	}
	return out, nil
}

// AppendStats registra las estadísticas de un ciclo.
func (o *OrgStore) AppendStats(v any) error { return appendLine(o, "stats.jsonl", v) }

// RecentStats devuelve las últimas estadísticas sin decodificar.
func (o *OrgStore) RecentStats(limit int) ([]json.RawMessage, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return ReadJSONL(o.Path("stats.jsonl"), limit)
}
```

- [ ] **Step 6: Tests (pasan), documentar, commit**

Run: `go test ./internal/store/ -race -cover` → PASS ≥ 70 %.

`ARCHITECTURE.md`:
```
| `internal/store` | Persistencia JSON/JSONL atómica por organización; ficheros 0600, directorios 0700. |
```

```bash
git add internal/store ARCHITECTURE.md
git commit -q -m "feat(store): persistencia atómica JSON/JSONL por organización

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 6: Contrato de conector y simulación (`internal/uem`, `internal/uem/simulation`)

**Files:**
- Create: `internal/uem/adapter.go`, `internal/uem/registry.go`, `internal/uem/uem_test.go`
- Create: `internal/uem/simulation/seed.go`, `internal/uem/simulation/default_seed.json`, `internal/uem/simulation/simulation.go`, `internal/uem/simulation/simulation_test.go`
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces (`uem`):
  ```go
  type Capabilities struct { Actions []action.Action `json:"actions"`; Inventory bool `json:"inventory"`; Location bool `json:"location"`; Posture bool `json:"posture"` }
  func (c Capabilities) Supports(a action.Action) bool
  type ConnectionResult struct { OK bool `json:"ok"`; Verified string `json:"verified"`; ErrorType string `json:"error_type,omitempty"`; Error string `json:"error,omitempty"`; HTTPStatus int `json:"http_status,omitempty"` }
  type Adapter interface {
      Name() string
      Capabilities() Capabilities
      FetchDevices(ctx context.Context) ([]device.Device, error)
      Execute(ctx context.Context, dev device.Device, a action.Action, params map[string]any, dryRun bool) action.Result
      TestConnection(ctx context.Context) ConnectionResult
  }
  type Factory func(cfg map[string]any, secrets map[string]string) (Adapter, error)
  var ErrUnknownProvider = errors.New("proveedor desconocido")
  type Registry struct{ ... }
  func NewRegistry() *Registry
  func (r *Registry) Register(name string, f Factory)   // panic si duplicado
  func (r *Registry) New(name string, cfg map[string]any, secrets map[string]string) (Adapter, error)
  func (r *Registry) Names() []string                    // ordenados
  ```
- Produces (`simulation`):
  ```go
  const Name = "simulation"
  type SeedDevice struct { ID, Name, Platform, Status string; Compliant *bool; Country, City, IP string; Waypoints []geo.Point; Inventory device.Inventory }  // tags snake_case
  type Seed struct { SchemaVersion int `json:"schema_version"`; Devices []SeedDevice `json:"devices"` }
  func DefaultSeed() Seed                        // 6 dispositivos en Madrid, embebida
  func (s Seed) Validate() error
  func LoadSeed(path string) (Seed, error); func SaveSeed(path string, s Seed) error
  func Position(waypoints []geo.Point, tick int) geo.Point   // segmento cada 3 ticks, interpolación lineal; vacío → Madrid
  type Adapter struct{ ... }
  func New(seed Seed, now func() time.Time) *Adapter
  func NewFromConfig(cfg map[string]any, secrets map[string]string) (uem.Adapter, error)  // cfg["seed_path"] opcional
  func (a *Adapter) Tick() int
  ```

- [ ] **Step 1: Tests de `uem` (fallan)**

`internal/uem/uem_test.go`:
```go
package uem

import (
	"context"
	"errors"
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

type fake struct{ name string }

func (f fake) Name() string                                 { return f.name }
func (f fake) Capabilities() Capabilities                    { return Capabilities{Actions: []action.Action{action.Message}} }
func (f fake) FetchDevices(context.Context) ([]device.Device, error) { return nil, nil }
func (f fake) Execute(_ context.Context, d device.Device, a action.Action, _ map[string]any, dry bool) action.Result {
	return action.Result{Adapter: f.name, OK: true, DeviceID: d.ID, Action: a, DryRun: dry}
}
func (f fake) TestConnection(context.Context) ConnectionResult { return ConnectionResult{OK: true, Verified: "fake"} }

func TestCapabilitiesSupports(t *testing.T) {
	c := Capabilities{Actions: []action.Action{action.Lock, action.Message}}
	if !c.Supports(action.Lock) || c.Supports(action.Wipe) {
		t.Fatal("Supports")
	}
}

func TestRegistry(t *testing.T) {
	r := NewRegistry()
	r.Register("zeta", func(map[string]any, map[string]string) (Adapter, error) { return fake{"zeta"}, nil })
	r.Register("alpha", func(map[string]any, map[string]string) (Adapter, error) { return fake{"alpha"}, nil })
	if names := r.Names(); len(names) != 2 || names[0] != "alpha" || names[1] != "zeta" {
		t.Fatalf("Names=%v", names)
	}
	a, err := r.New("alpha", nil, nil)
	if err != nil || a.Name() != "alpha" {
		t.Fatal(err)
	}
	if _, err := r.New("nope", nil, nil); !errors.Is(err, ErrUnknownProvider) {
		t.Fatalf("esperaba ErrUnknownProvider, got %v", err)
	}
	defer func() {
		if recover() == nil {
			t.Fatal("registrar dos veces debe hacer panic")
		}
	}()
	r.Register("alpha", nil)
}
```

- [ ] **Step 2: Implementar `adapter.go` y `registry.go`**

`internal/uem/adapter.go`:
```go
// Package uem define el contrato que implementa todo conector UEM (spec §5.7).
// Un conector nunca hace panic ni tumba el ciclo: Execute devuelve siempre un
// Result; los errores de inventario se reportan como salud del proveedor.
package uem

import (
	"context"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// Capabilities declara lo que el conector sabe hacer.
type Capabilities struct {
	Actions   []action.Action `json:"actions"`
	Inventory bool            `json:"inventory"`
	Location  bool            `json:"location"`
	Posture   bool            `json:"posture"`
}

// Supports indica si la acción está soportada.
func (c Capabilities) Supports(a action.Action) bool {
	for _, x := range c.Actions {
		if x == a {
			return true
		}
	}
	return false
}

// ConnectionResult es el resultado de "Probar conexión".
type ConnectionResult struct {
	OK         bool   `json:"ok"`
	Verified   string `json:"verified"`
	ErrorType  string `json:"error_type,omitempty"`
	Error      string `json:"error,omitempty"`
	HTTPStatus int    `json:"http_status,omitempty"`
}

// Adapter es el contrato congelado de conector.
type Adapter interface {
	Name() string
	Capabilities() Capabilities
	FetchDevices(ctx context.Context) ([]device.Device, error)
	Execute(ctx context.Context, dev device.Device, a action.Action, params map[string]any, dryRun bool) action.Result
	TestConnection(ctx context.Context) ConnectionResult
}
```

`internal/uem/registry.go`:
```go
package uem

import (
	"errors"
	"fmt"
	"sort"
	"sync"
)

// Factory construye un conector a partir de su configuración no secreta y sus secretos.
type Factory func(cfg map[string]any, secrets map[string]string) (Adapter, error)

// ErrUnknownProvider indica un nombre no registrado.
var ErrUnknownProvider = errors.New("proveedor desconocido")

// Registry es la tabla nombre → fábrica. Añadir un conector = una línea aquí.
type Registry struct {
	mu        sync.RWMutex
	factories map[string]Factory
}

// NewRegistry crea un registro vacío.
func NewRegistry() *Registry { return &Registry{factories: map[string]Factory{}} }

// Register añade una fábrica; registrar dos veces el mismo nombre es un error de programación.
func (r *Registry) Register(name string, f Factory) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, dup := r.factories[name]; dup {
		panic(fmt.Sprintf("uem: proveedor %q registrado dos veces", name))
	}
	r.factories[name] = f
}

// New construye un conector por nombre.
func (r *Registry) New(name string, cfg map[string]any, secrets map[string]string) (Adapter, error) {
	r.mu.RLock()
	f, ok := r.factories[name]
	r.mu.RUnlock()
	if !ok {
		return nil, fmt.Errorf("%w: %q", ErrUnknownProvider, name)
	}
	return f(cfg, secrets)
}

// Names lista los proveedores registrados en orden estable.
func (r *Registry) Names() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	names := make([]string, 0, len(r.factories))
	for n := range r.factories {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}
```

Run: `go test ./internal/uem/ -v` → PASS.

- [ ] **Step 3: Seed por defecto**

`internal/uem/simulation/default_seed.json` (flota demo de Madrid; HQ en 40.421,-3.708 con radio 500 m; almacén polígono al sur):
```json
{
  "schema_version": 1,
  "devices": [
    {"id": "dev-001", "name": "Tablet Campo A1", "platform": "android", "status": "active", "compliant": true, "country": "ES", "city": "Madrid", "ip": "10.0.0.21",
     "waypoints": [{"lat": 40.4205, "lng": -3.7085}, {"lat": 40.4215, "lng": -3.7075}, {"lat": 40.4210, "lng": -3.7090}],
     "inventory": {"os_version": "Android 14", "model": "Samsung Galaxy Tab Active5", "manufacturer": "Samsung", "serial_number": "RZ8T40EMBPD", "imei": "354679110234567", "battery_level": 87, "battery_state": "discharging", "storage_total_gb": 128, "storage_free_gb": 64.5, "encryption_enabled": true, "carrier": "Movistar", "assigned_user": "Lucía Fernández", "department": "Operaciones", "device_tag": "OPS-TAB-001", "management_mode": "device_owner", "ownership": "company", "apps": [{"name": "Chrome", "version": "120.0.0"}, {"name": "Slack", "version": "4.30"}]}},
    {"id": "dev-002", "name": "Móvil Reparto B7", "platform": "android", "status": "active", "compliant": true, "country": "ES", "city": "Madrid", "ip": "10.0.0.22",
     "waypoints": [{"lat": 40.4300, "lng": -3.6900}, {"lat": 40.4250, "lng": -3.7000}, {"lat": 40.4210, "lng": -3.7080}],
     "inventory": {"os_version": "Android 13", "model": "Zebra TC22", "manufacturer": "Zebra", "serial_number": "ZTC22-00913", "imei": "356789012345678", "battery_level": 54, "battery_state": "discharging", "storage_total_gb": 64, "storage_free_gb": 21, "encryption_enabled": true, "carrier": "Vodafone", "assigned_user": "Marcos Gil", "department": "Logística", "device_tag": "LOG-MOV-007", "management_mode": "device_owner", "ownership": "company", "apps": [{"name": "Maps", "version": "11.2"}]}},
    {"id": "dev-003", "name": "iPad Recepción", "platform": "ios", "status": "active", "compliant": true, "country": "ES", "city": "Madrid", "ip": "10.0.0.23",
     "waypoints": [{"lat": 40.4212, "lng": -3.7078}],
     "inventory": {"os_version": "iOS 18.6", "model": "iPad Air", "manufacturer": "Apple", "serial_number": "DMPX2K3LHG7F", "battery_level": 100, "battery_state": "full", "storage_total_gb": 256, "storage_free_gb": 180, "encryption_enabled": true, "assigned_user": "Recepción", "department": "Oficina", "device_tag": "OFI-IPAD-001", "management_mode": "mdm", "ownership": "company", "supervised": true, "lockdown_mode": false, "apps": [{"name": "Safari", "version": "18.6"}]}},
    {"id": "dev-004", "name": "Portátil Ventas", "platform": "macos", "status": "active", "compliant": false, "country": "ES", "city": "Madrid", "ip": "10.0.0.24",
     "waypoints": [{"lat": 40.4500, "lng": -3.6500}],
     "inventory": {"os_version": "macOS 15.6", "model": "MacBook Air M3", "manufacturer": "Apple", "serial_number": "C02XL9ZQMD6T", "battery_level": 32, "battery_state": "discharging", "storage_total_gb": 512, "storage_free_gb": 120, "encryption_enabled": false, "assigned_user": "Sara López", "department": "Ventas", "device_tag": "VEN-MAC-004", "management_mode": "mdm", "ownership": "company", "apps": [{"name": "Zoom", "version": "6.1.0"}]}},
    {"id": "dev-005", "name": "Escáner Almacén", "platform": "android", "status": "active", "compliant": true, "country": "ES", "city": "Madrid", "ip": "10.0.1.5",
     "waypoints": [{"lat": 40.4050, "lng": -3.7100}, {"lat": 40.4060, "lng": -3.7120}],
     "inventory": {"os_version": "Android 12", "model": "Honeywell CT45", "manufacturer": "Honeywell", "serial_number": "HW-CT45-2210", "battery_level": 71, "battery_state": "charging", "storage_total_gb": 64, "storage_free_gb": 40, "encryption_enabled": true, "assigned_user": "Almacén turno A", "department": "Logística", "device_tag": "LOG-SCN-005", "management_mode": "device_owner", "ownership": "company", "apps": [{"name": "WMS", "version": "3.4"}]}},
    {"id": "dev-006", "name": "Portátil Soporte", "platform": "windows", "status": "active", "compliant": true, "country": "ES", "city": "Madrid", "ip": "10.0.0.26",
     "waypoints": [{"lat": 40.4210, "lng": -3.7080}, {"lat": 40.4350, "lng": -3.7000}],
     "inventory": {"os_version": "Windows 11 24H2", "model": "Dell Latitude 5450", "manufacturer": "Dell", "serial_number": "7Q2M3X4", "battery_level": 95, "battery_state": "charging", "storage_total_gb": 512, "storage_free_gb": 300, "encryption_enabled": true, "assigned_user": "Diego Ruiz", "department": "IT", "device_tag": "IT-WIN-006", "management_mode": "mdm", "ownership": "company", "apps": [{"name": "Teams", "version": "24.1"}]}}
  ]
}
```

- [ ] **Step 4: Tests de simulación (fallan)**

`internal/uem/simulation/simulation_test.go`:
```go
package simulation

import (
	"context"
	"math"
	"path/filepath"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

func TestDefaultSeedValida(t *testing.T) {
	s := DefaultSeed()
	if err := s.Validate(); err != nil {
		t.Fatal(err)
	}
	if len(s.Devices) != 6 || s.Devices[0].ID != "dev-001" || s.Devices[0].Inventory.Model == "" {
		t.Fatalf("seed: %+v", s.Devices)
	}
}

func TestSeedValidateRechazaDuplicadosYSinWaypoints(t *testing.T) {
	s := Seed{Devices: []SeedDevice{{ID: "a", Name: "A", Platform: "android", Waypoints: []geo.Point{{}}}, {ID: "a", Name: "B", Platform: "ios", Waypoints: []geo.Point{{}}}}}
	if err := s.Validate(); err == nil {
		t.Fatal("id duplicado")
	}
	s = Seed{Devices: []SeedDevice{{ID: "a", Name: "A", Platform: "android"}}}
	if err := s.Validate(); err == nil {
		t.Fatal("sin waypoints")
	}
}

func TestPosition(t *testing.T) {
	wps := []geo.Point{{Lat: 0, Lng: 0}, {Lat: 3, Lng: 3}}
	if p := Position(wps, 0); p != wps[0] {
		t.Fatalf("tick 0: %v", p)
	}
	if p := Position(wps, 1); math.Abs(p.Lat-1) > 1e-9 || math.Abs(p.Lng-1) > 1e-9 {
		t.Fatalf("tick 1 = 1/3 del segmento: %v", p)
	}
	if p := Position(wps, 3); p != wps[1] {
		t.Fatalf("tick 3 = segundo waypoint: %v", p)
	}
	if p := Position(wps, 6); p != wps[0] {
		t.Fatalf("tick 6 vuelve al inicio: %v", p)
	}
	if p := Position(nil, 5); p.Lat != 40.4168 {
		t.Fatalf("sin waypoints → Madrid: %v", p)
	}
}

func TestFetchDevicesMueveYRellena(t *testing.T) {
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	a := New(DefaultSeed(), func() time.Time { return now })
	ds, err := a.FetchDevices(context.Background())
	if err != nil || len(ds) != 6 {
		t.Fatalf("%v %d", err, len(ds))
	}
	d := ds[0]
	if d.Provider != "simulation" || d.Location.Source != "simulation" || d.Location.Point == nil || *d.Location.AccuracyM != 12 || !d.LastReportAt.Equal(now) || d.ProviderRefs["simulation"] != "dev-001" {
		t.Fatalf("campos: %+v", d)
	}
	if d.Inventory.Model != "Samsung Galaxy Tab Active5" || d.Inventory.BatteryLevel == nil {
		t.Fatalf("inventario: %+v", d.Inventory)
	}
	first := *ds[1].Location.Point
	ds2, _ := a.FetchDevices(context.Background())
	if *ds2[1].Location.Point == first {
		t.Fatal("dev-002 debe moverse entre ticks")
	}
	if a.Tick() != 2 {
		t.Fatalf("tick=%d", a.Tick())
	}
}

func TestExecuteSimulaSinErrores(t *testing.T) {
	a := New(DefaultSeed(), time.Now)
	ds, _ := a.FetchDevices(context.Background())
	for _, act := range action.All {
		r := a.Execute(context.Background(), ds[0], act, map[string]any{"text": "hola"}, true)
		if !r.OK || !r.Simulated || !r.DryRun || r.Adapter != "simulation" || r.DeviceID != "dev-001" || r.CommandID == "" || r.At.IsZero() {
			t.Fatalf("%s: %+v", act, r)
		}
	}
	if !a.Capabilities().Supports(action.Wipe) || !a.Capabilities().Location {
		t.Fatal("capacidades")
	}
	if c := a.TestConnection(context.Background()); !c.OK || c.Verified != "simulated" {
		t.Fatalf("%+v", c)
	}
}

func TestLoadSaveSeedYNewFromConfig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "seed.json")
	if _, err := LoadSeed(path); err == nil {
		t.Fatal("fichero ausente debe fallar")
	}
	if err := SaveSeed(path, DefaultSeed()); err != nil {
		t.Fatal(err)
	}
	s, err := LoadSeed(path)
	if err != nil || len(s.Devices) != 6 {
		t.Fatal(err)
	}
	ad, err := NewFromConfig(map[string]any{"seed_path": path}, nil)
	if err != nil || ad.Name() != Name {
		t.Fatal(err)
	}
	if _, err := NewFromConfig(map[string]any{"seed_path": filepath.Join(t.TempDir(), "nope.json")}, nil); err == nil {
		t.Fatal("seed_path inexistente debe fallar")
	}
	if ad, err := NewFromConfig(nil, nil); err != nil || ad == nil {
		t.Fatal("sin seed_path usa la seed por defecto")
	}
}
```

- [ ] **Step 5: Implementar `seed.go` y `simulation.go`**

`internal/uem/simulation/seed.go`:
```go
// Package simulation es el conector de flota simulada: sin red, sin
// dispositivos reales. Mueve cada dispositivo por sus waypoints (un segmento
// cada 3 ciclos, semántica 1.x) y simula toda acción.
package simulation

import (
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

//go:embed default_seed.json
var defaultSeedJSON []byte

// SeedDevice es un dispositivo de la seed.
type SeedDevice struct {
	ID        string           `json:"id"`
	Name      string           `json:"name"`
	Platform  string           `json:"platform"`
	Status    string           `json:"status,omitempty"`
	Compliant *bool            `json:"compliant,omitempty"`
	Country   string           `json:"country,omitempty"`
	City      string           `json:"city,omitempty"`
	IP        string           `json:"ip,omitempty"`
	Waypoints []geo.Point      `json:"waypoints"`
	Inventory device.Inventory `json:"inventory"`
}

// Seed es la flota simulada.
type Seed struct {
	SchemaVersion int          `json:"schema_version"`
	Devices       []SeedDevice `json:"devices"`
}

// DefaultSeed devuelve la flota demo embebida (6 dispositivos en Madrid).
func DefaultSeed() Seed {
	var s Seed
	if err := json.Unmarshal(defaultSeedJSON, &s); err != nil {
		panic("default_seed.json inválida: " + err.Error())
	}
	return s
}

// Validate exige ids únicos, nombre, plataforma y al menos un waypoint válido.
func (s Seed) Validate() error {
	seen := map[string]bool{}
	for i, d := range s.Devices {
		if d.ID == "" || d.Name == "" || d.Platform == "" {
			return fmt.Errorf("dispositivo %d: id, nombre y plataforma obligatorios", i)
		}
		if seen[d.ID] {
			return fmt.Errorf("id duplicado %q", d.ID)
		}
		seen[d.ID] = true
		if len(d.Waypoints) == 0 {
			return fmt.Errorf("dispositivo %q sin waypoints", d.ID)
		}
		for j, w := range d.Waypoints {
			if err := w.Valid(); err != nil {
				return fmt.Errorf("dispositivo %q waypoint %d: %w", d.ID, j, err)
			}
		}
	}
	return nil
}

// LoadSeed lee una seed de disco.
func LoadSeed(path string) (Seed, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Seed{}, err
	}
	var s Seed
	if err := json.Unmarshal(data, &s); err != nil {
		return Seed{}, fmt.Errorf("seed %s: %w", path, err)
	}
	if err := s.Validate(); err != nil {
		return Seed{}, err
	}
	return s, nil
}

// SaveSeed escribe una seed (0600).
func SaveSeed(path string, s Seed) error {
	if err := s.Validate(); err != nil {
		return err
	}
	if s.SchemaVersion == 0 {
		s.SchemaVersion = 1
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}

var errNoSeed = errors.New("seed vacía")
```

`internal/uem/simulation/simulation.go`:
```go
package simulation

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// Name es el identificador del conector.
const Name = "simulation"

const accuracyM = 12.0

var madrid = geo.Point{Lat: 40.4168, Lng: -3.7038}

// Adapter simula una flota.
type Adapter struct {
	mu   sync.Mutex
	seed Seed
	tick int
	now  func() time.Time
}

// New crea el conector con una seed y un reloj.
func New(seed Seed, now func() time.Time) *Adapter {
	if now == nil {
		now = time.Now
	}
	return &Adapter{seed: seed, now: now}
}

// NewFromConfig construye el conector desde cfg["seed_path"] (opcional).
func NewFromConfig(cfg map[string]any, _ map[string]string) (uem.Adapter, error) {
	if path, ok := cfg["seed_path"].(string); ok && path != "" {
		seed, err := LoadSeed(path)
		if err != nil {
			return nil, err
		}
		return New(seed, time.Now), nil
	}
	return New(DefaultSeed(), time.Now), nil
}

// Tick devuelve cuántas veces se ha pedido la flota.
func (a *Adapter) Tick() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.tick
}

// Name implementa uem.Adapter.
func (a *Adapter) Name() string { return Name }

// Capabilities implementa uem.Adapter: la simulación lo soporta todo salvo postura.
func (a *Adapter) Capabilities() uem.Capabilities {
	return uem.Capabilities{Actions: action.All, Inventory: true, Location: true, Posture: false}
}

// Position calcula la posición en un tick: un segmento cada 3 ticks con
// interpolación lineal, para que una flota se mueva visiblemente entre ciclos.
func Position(waypoints []geo.Point, tick int) geo.Point {
	n := len(waypoints)
	if n == 0 {
		return madrid
	}
	seg := (tick / 3) % n
	a, b := waypoints[seg], waypoints[(seg+1)%n]
	frac := float64(tick%3) / 3.0
	return geo.Point{Lat: a.Lat + (b.Lat-a.Lat)*frac, Lng: a.Lng + (b.Lng-a.Lng)*frac}
}

// FetchDevices implementa uem.Adapter.
func (a *Adapter) FetchDevices(_ context.Context) ([]device.Device, error) {
	a.mu.Lock()
	tick := a.tick
	a.tick++
	seed := a.seed
	a.mu.Unlock()
	if len(seed.Devices) == 0 {
		return nil, errNoSeed
	}
	now := a.now().UTC()
	out := make([]device.Device, 0, len(seed.Devices))
	for _, sd := range seed.Devices {
		p := Position(sd.Waypoints, tick)
		acc := accuracyM
		status := sd.Status
		if status == "" {
			status = "active"
		}
		out = append(out, device.Device{
			ID: sd.ID, Name: sd.Name, Platform: sd.Platform, Status: status, Compliant: sd.Compliant,
			Provider: Name, ProviderRefs: map[string]string{Name: sd.ID},
			Location:  device.Location{Point: &p, AccuracyM: &acc, Source: Name, ObservedAt: now},
			Network:   device.Network{IP: sd.IP},
			Inventory: sd.Inventory, FenceState: device.Unknown, RouteState: device.Unassigned,
			Risk:      device.Verdict{Reasons: []string{}, MatchedPolicies: []string{}},
			LastReportAt: now,
		})
	}
	return out, nil
}

// Execute implementa uem.Adapter: nunca contacta un dispositivo real.
func (a *Adapter) Execute(_ context.Context, dev device.Device, act action.Action, params map[string]any, dryRun bool) action.Result {
	sum := sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%d", dev.ID, act, a.Tick())))
	return action.Result{
		Adapter: Name, OK: true, DeviceID: dev.ID, DeviceName: dev.Name, Action: act, Params: params,
		DryRun: dryRun, Simulated: true, CommandID: "sim-" + hex.EncodeToString(sum[:6]),
		Note: "Acción simulada (ningún dispositivo real contactado)", At: a.now().UTC(),
	}
}

// TestConnection implementa uem.Adapter.
func (a *Adapter) TestConnection(context.Context) uem.ConnectionResult {
	return uem.ConnectionResult{OK: true, Verified: "simulated"}
}
```

- [ ] **Step 6: Tests (pasan), documentar, commit**

Run: `go test ./internal/uem/... -race -cover` → PASS ≥ 70 %.

`ARCHITECTURE.md`:
```
| `internal/uem` | Contrato `Adapter`, capacidades, resultado de conexión y registro de conectores. |
| `internal/uem/simulation` | Flota simulada con seed embebida; mueve dispositivos por waypoints y simula acciones. |
```

```bash
git add internal/uem ARCHITECTURE.md
git commit -q -m "feat(uem): contrato de conector, registro y simulación con seed demo

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 7: Configuración (`internal/config`)

**Files:**
- Create: `internal/config/config.go`, `internal/config/config_test.go`
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces:
  ```go
  type MapConfig struct { Enabled bool `json:"enabled"`; TilesURL string `json:"tiles_url"` }
  type EgressConfig struct { Hosts []string `json:"hosts"`; AllowPrivate bool `json:"allow_private"` }
  type Config struct { DataDir string `json:"data_dir"`; Listen string `json:"listen"`; IntervalSeconds int `json:"interval_seconds"`; Mode string `json:"mode"`
                       Org string `json:"org"`; Map MapConfig `json:"map"`; Egress EgressConfig `json:"egress"`; LogLevel string `json:"log_level"` }
  func Default() Config   // data, 127.0.0.1:8765, 900, simulation, default, map on OSM, log info
  func Load(path string) (Config, error)  // ausente → Default(); campos desconocidos → error; ceros → defaults
  func (c Config) Validate() error
  func (c Config) Save(path string) error // 0600
  func (c Config) Interval() time.Duration
  const DefaultTilesURL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
  ```

- [ ] **Step 1: Tests (fallan)**

`internal/config/config_test.go`:
```go
package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestDefaultEsValido(t *testing.T) {
	c := Default()
	if err := c.Validate(); err != nil {
		t.Fatal(err)
	}
	if c.Listen != "127.0.0.1:8765" || c.IntervalSeconds != 900 || c.Mode != "simulation" || c.Org != "default" || !c.Map.Enabled || c.Map.TilesURL != DefaultTilesURL || c.Interval() != 15*time.Minute {
		t.Fatalf("%+v", c)
	}
}

func TestLoadAusenteYParcial(t *testing.T) {
	c, err := Load(filepath.Join(t.TempDir(), "nope.json"))
	if err != nil || c.Listen != "127.0.0.1:8765" {
		t.Fatalf("ausente → defaults: %v %+v", err, c)
	}
	path := filepath.Join(t.TempDir(), "config.json")
	os.WriteFile(path, []byte(`{"listen":"127.0.0.1:9000","interval_seconds":60}`), 0o600)
	c, err = Load(path)
	if err != nil || c.Listen != "127.0.0.1:9000" || c.IntervalSeconds != 60 || c.Mode != "simulation" || c.Map.TilesURL != DefaultTilesURL {
		t.Fatalf("parcial rellena defaults: %v %+v", err, c)
	}
	os.WriteFile(path, []byte(`{"listen":"127.0.0.1:9000","modo":"live"}`), 0o600)
	if _, err := Load(path); err == nil || !strings.Contains(err.Error(), "modo") {
		t.Fatalf("campo desconocido debe fallar nombrándolo: %v", err)
	}
}

func TestValidateErroresConCampo(t *testing.T) {
	cases := map[string]func(*Config){
		"mode":        func(c *Config) { c.Mode = "demo" },
		"interval":    func(c *Config) { c.IntervalSeconds = 5 },
		"listen":      func(c *Config) { c.Listen = "no-es-host-port" },
		"org":         func(c *Config) { c.Org = "Default Org" },
		"log_level":   func(c *Config) { c.LogLevel = "loud" },
		"tiles_url":   func(c *Config) { c.Map.TilesURL = "https://tiles.example/{z}/{x}.png" },
		"data_dir":    func(c *Config) { c.DataDir = "" },
	}
	for name, mut := range cases {
		c := Default()
		mut(&c)
		err := c.Validate()
		if err == nil || !strings.Contains(err.Error(), name) {
			t.Errorf("%s: esperaba error que nombre el campo, got %v", name, err)
		}
	}
	c := Default()
	c.Map.Enabled = false
	c.Map.TilesURL = ""
	if err := c.Validate(); err != nil {
		t.Fatal("mapa desactivado no exige tiles_url")
	}
}

func TestSaveRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.json")
	c := Default()
	c.Listen = "127.0.0.1:1234"
	if err := c.Save(path); err != nil {
		t.Fatal(err)
	}
	got, err := Load(path)
	if err != nil || got.Listen != "127.0.0.1:1234" {
		t.Fatal(err)
	}
}
```

- [ ] **Step 2: Implementar `config.go`**

```go
// Package config carga y valida config.json (lo no secreto). Los secretos van
// en variables LUCIDFENCE_* o en <data>/secrets/ (spec §5.8).
package config

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"regexp"
	"strings"
	"time"
)

// DefaultTilesURL es el proveedor de tiles por defecto (OSM público).
const DefaultTilesURL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

var orgIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,39}$`)

// MapConfig configura el mapa del dashboard.
type MapConfig struct {
	Enabled  bool   `json:"enabled"`
	TilesURL string `json:"tiles_url"`
}

// EgressConfig es la allowlist de salida (M2 la aplica).
type EgressConfig struct {
	Hosts        []string `json:"hosts"`
	AllowPrivate bool     `json:"allow_private"`
}

// Config es la configuración del binario.
type Config struct {
	DataDir         string       `json:"data_dir"`
	Listen          string       `json:"listen"`
	IntervalSeconds int          `json:"interval_seconds"`
	Mode            string       `json:"mode"`
	Org             string       `json:"org"`
	Map             MapConfig    `json:"map"`
	Egress          EgressConfig `json:"egress"`
	LogLevel        string       `json:"log_level"`
}

// Default devuelve la configuración segura de fábrica.
func Default() Config {
	return Config{
		DataDir: "data", Listen: "127.0.0.1:8765", IntervalSeconds: 900, Mode: "simulation", Org: "default",
		Map: MapConfig{Enabled: true, TilesURL: DefaultTilesURL}, Egress: EgressConfig{Hosts: []string{}}, LogLevel: "info",
	}
}

// Load lee config.json; si no existe devuelve Default(). Rechaza campos desconocidos.
func Load(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return Default(), nil
	}
	if err != nil {
		return Config{}, err
	}
	c := Default()
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&c); err != nil {
		return Config{}, fmt.Errorf("config %s: %w", path, err)
	}
	c.fillDefaults()
	return c, c.Validate()
}

func (c *Config) fillDefaults() {
	d := Default()
	if c.DataDir == "" {
		c.DataDir = d.DataDir
	}
	if c.Listen == "" {
		c.Listen = d.Listen
	}
	if c.IntervalSeconds == 0 {
		c.IntervalSeconds = d.IntervalSeconds
	}
	if c.Mode == "" {
		c.Mode = d.Mode
	}
	if c.Org == "" {
		c.Org = d.Org
	}
	if c.Map.Enabled && c.Map.TilesURL == "" {
		c.Map.TilesURL = d.Map.TilesURL
	}
	if c.LogLevel == "" {
		c.LogLevel = d.LogLevel
	}
	if c.Egress.Hosts == nil {
		c.Egress.Hosts = []string{}
	}
}

// Validate comprueba cada campo y nombra el que falla.
func (c Config) Validate() error {
	if c.DataDir == "" {
		return errors.New("data_dir: obligatorio")
	}
	if c.Mode != "simulation" && c.Mode != "live" {
		return fmt.Errorf("mode: %q no es simulation|live", c.Mode)
	}
	if c.IntervalSeconds < 10 || c.IntervalSeconds > 86400 {
		return fmt.Errorf("interval_seconds: %d fuera de [10, 86400]", c.IntervalSeconds)
	}
	if _, _, err := net.SplitHostPort(c.Listen); err != nil {
		return fmt.Errorf("listen: %q no es host:puerto", c.Listen)
	}
	if !orgIDPattern.MatchString(c.Org) {
		return fmt.Errorf("org: %q inválido (minúsculas, dígitos, guiones)", c.Org)
	}
	switch c.LogLevel {
	case "debug", "info", "warn", "error":
	default:
		return fmt.Errorf("log_level: %q no es debug|info|warn|error", c.LogLevel)
	}
	if c.Map.Enabled {
		for _, ph := range []string{"{z}", "{x}", "{y}"} {
			if !strings.Contains(c.Map.TilesURL, ph) {
				return fmt.Errorf("map.tiles_url: falta %s", ph)
			}
		}
	}
	return nil
}

// Save escribe la configuración con permisos 0600.
func (c Config) Save(path string) error {
	if err := c.Validate(); err != nil {
		return err
	}
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}

// Interval devuelve el intervalo del ciclo.
func (c Config) Interval() time.Duration { return time.Duration(c.IntervalSeconds) * time.Second }
```

- [ ] **Step 3: Tests (pasan), documentar, commit**

Run: `go test ./internal/config/ -cover` → PASS.

`ARCHITECTURE.md`:
```
| `internal/config` | `config.json`: defaults seguros, validación con nombre de campo, guardado 0600. |
```

```bash
git add internal/config ARCHITECTURE.md
git commit -q -m "feat(config): carga y validación de config.json con defaults seguros

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 8: Motor (`internal/engine`)

**Files:**
- Create: `internal/engine/guardrails.go`, `internal/engine/actions.go`, `internal/engine/cycle.go`, `internal/engine/engine.go`, `internal/engine/demo.go`
- Create: `internal/engine/guardrails_test.go`, `internal/engine/actions_test.go`, `internal/engine/engine_test.go`, `internal/engine/demo_test.go`
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces:
  ```go
  const ( EnforcementObserve = "observe"; EnforcementEnforce = "enforce" )
  type Guardrails struct { Enforcement string }
  func (g Guardrails) DryRun(a action.Action) bool   // M1: true salvo Enforcement == enforce (nadie puede activarlo aún)
  type Planned struct { Device device.Device; Action fence.Action; FenceID string; Trigger string }
  func PlanTransition(cur device.Device, tr *transition.Transition, fences []fence.Fence) []Planned
  type Options struct { Mode string; Interval time.Duration; Now func() time.Time; Logger *slog.Logger }
  type ProviderHealth struct { OK bool `json:"ok"`; Error string `json:"error,omitempty"`; Devices int `json:"devices"`; LatencyMS int64 `json:"latency_ms"`; LastOK *time.Time `json:"last_ok,omitempty"` }
  type CycleStats struct { At time.Time `json:"at"`; DurationMS int64 `json:"duration_ms"`; Mode string `json:"mode"`; DevicesTotal int `json:"devices_total"`; Inside int `json:"inside"`; Outside int `json:"outside"`; Unknown int `json:"unknown"`
                           Transitions int `json:"transitions"`; ActionsPlanned int `json:"actions_planned"`; ActionsExecuted int `json:"actions_executed"`; EvaluationErrors int `json:"evaluation_errors"`; Providers map[string]ProviderHealth `json:"providers"` }
  type Status struct { Mode string `json:"mode"`; Enforcement string `json:"enforcement"`; IntervalSeconds int `json:"interval_seconds"`; Running bool `json:"running"`; Cycles int `json:"cycles"`
                       LastCycle *CycleStats `json:"last_cycle,omitempty"`; NextCycleAt *time.Time `json:"next_cycle_at,omitempty"`; Providers map[string]ProviderHealth `json:"providers"` }
  var ErrCycleInProgress = errors.New("ciclo en curso")
  type Engine struct{ ... }
  func New(org *store.OrgStore, adapters []uem.Adapter, opts Options) *Engine
  func (e *Engine) RunOnce(ctx context.Context) (CycleStats, error)
  func (e *Engine) Start(ctx context.Context)   // ciclo inmediato + ticker; termina con ctx
  func (e *Engine) Stop()                        // espera al goroutine
  func (e *Engine) Status() Status
  func (e *Engine) Guardrails() Guardrails
  func SeedDemo(org *store.OrgStore, now time.Time) error  // geocercas demo-hq y warehouse-poly, ruta route-centro, 2 POIs, seed.json; idempotente
  ```

- [ ] **Step 1: Tests de guardarraíles y planificación (fallan)**

`internal/engine/guardrails_test.go`:
```go
package engine

import (
	"testing"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

func TestObserveSiempreDryRun(t *testing.T) {
	g := Guardrails{Enforcement: EnforcementObserve}
	for _, a := range action.All {
		if !g.DryRun(a) {
			t.Fatalf("%s en observe debe ser dry-run", a)
		}
	}
	if g.Enforcement != "observe" {
		t.Fatal("literal")
	}
}

func TestEnforcementVacioEquivaleAObserve(t *testing.T) {
	if !(Guardrails{}).DryRun(action.Wipe) {
		t.Fatal("sin configurar = observe")
	}
}
```

`internal/engine/actions_test.go`:
```go
package engine

import (
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

func demoFences() []fence.Fence {
	return []fence.Fence{{ID: "demo-hq", Name: "HQ", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
		Actions: []fence.Action{
			{Action: action.Message, When: fence.OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido"}},
			{Action: action.Notify, When: fence.OnExit, Enabled: true},
			{Action: action.Locate, When: fence.OnUnknown, Enabled: true},
			{Action: action.Lock, When: fence.OnViolation, Enabled: true},
			{Action: action.Wipe, When: fence.OnEnter, Enabled: false},
		}}}
}

func TestPlanTransition(t *testing.T) {
	fs := demoFences()
	cur := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	enter := &transition.Transition{From: "none:outside", To: "demo-hq:inside"}
	got := PlanTransition(cur, enter, fs)
	if len(got) != 1 || got[0].Action.Action != action.Message || got[0].FenceID != "demo-hq" || got[0].Trigger != "on_enter" {
		t.Fatalf("on_enter: %+v", got)
	}
	cur = device.Device{ID: "d", FenceState: device.Outside}
	exit := &transition.Transition{From: "demo-hq:inside", To: "none:outside"}
	got = PlanTransition(cur, exit, fs)
	if len(got) != 1 || got[0].Action.Action != action.Notify || got[0].Trigger != "on_exit" {
		t.Fatalf("on_exit: %+v", got)
	}
	cur = device.Device{ID: "d", FenceState: device.Unknown, LastInsideFence: "demo-hq"}
	unk := &transition.Transition{From: "demo-hq:inside", To: "none:unknown"}
	got = PlanTransition(cur, unk, fs)
	if len(got) != 2 {
		t.Fatalf("a unknown: on_exit de la geocerca previa + on_unknown: %+v", got)
	}
	if PlanTransition(cur, nil, fs) != nil {
		t.Fatal("sin transición no hay plan")
	}
}

func TestStandingViolationCadaNCiclos(t *testing.T) {
	fs := demoFences()
	fs[0].Rules.ViolationIntervalCycles = 2
	e := &Engine{violations: map[string]int{}}
	out := device.Device{ID: "d", FenceState: device.Outside}
	if got := e.planStanding(out, fs); len(got) != 0 {
		t.Fatalf("ciclo 1 de 2: nada, got %+v", got)
	}
	if got := e.planStanding(out, fs); len(got) != 1 || got[0].Action.Action != action.Lock || got[0].Trigger != "on_violation" {
		t.Fatalf("ciclo 2: dispara, got %+v", got)
	}
	in := device.Device{ID: "d", FenceState: device.Inside, InsideFence: "demo-hq"}
	e.planStanding(in, fs)
	if e.violations["d|demo-hq"] != 0 {
		t.Fatal("dentro resetea el contador")
	}
}

func TestDedupePorCiclo(t *testing.T) {
	e := &Engine{fired: map[string]bool{}}
	p := Planned{Device: device.Device{ID: "d"}, Action: fence.Action{Action: action.Message}, FenceID: "f", Trigger: "on_enter"}
	if e.alreadyFired(p) || !e.alreadyFired(p) {
		t.Fatal("la segunda vez debe estar deduplicada")
	}
	_ = time.Now
}
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `go test ./internal/engine/`
Expected: `undefined: Guardrails`.

- [ ] **Step 3: Implementar `guardrails.go` y `actions.go`**

`internal/engine/guardrails.go`:
```go
package engine

import "github.com/adrimg3196/lucidfence/internal/domain/action"

// Modos de enforcement (spec §3 y §5.4). observe = todo dry-run.
const (
	EnforcementObserve = "observe"
	EnforcementEnforce = "enforce"
)

// Guardrails es el ÚNICO sitio que decide si una acción sale en vivo. Este
// fichero está protegido por CODEOWNERS. M1 solo conoce observe; M2 añade
// live_actions, allow_wipe y wipe_allowlist sin mover la decisión de aquí.
type Guardrails struct {
	Enforcement string
}

// DryRun devuelve true si la acción NO debe llegar al dispositivo real.
func (g Guardrails) DryRun(_ action.Action) bool {
	return g.Enforcement != EnforcementEnforce
}
```

`internal/engine/actions.go`:
```go
package engine

import (
	"context"
	"fmt"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
)

// Planned es una acción decidida pero aún no ejecutada.
type Planned struct {
	Device  device.Device
	Action  fence.Action
	FenceID string
	Trigger string
}

func fenceOfKey(key string) string {
	id := strings.SplitN(key, ":", 2)[0]
	if id == "none" {
		return ""
	}
	return id
}

// PlanTransition decide las acciones de geocerca para una transición:
// on_enter de la geocerca destino, on_exit de la de origen y on_unknown al
// perder la ubicación.
func PlanTransition(cur device.Device, tr *transition.Transition, fences []fence.Fence) []Planned {
	if tr == nil {
		return nil
	}
	var out []Planned
	if from := fenceOfKey(tr.From); from != "" {
		if f, ok := fence.FindByID(fences, from); ok {
			for _, a := range f.ActionsFor(fence.OnExit) {
				out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnExit)})
			}
		}
	}
	if to := fenceOfKey(tr.To); to != "" {
		if f, ok := fence.FindByID(fences, to); ok {
			for _, a := range f.ActionsFor(fence.OnEnter) {
				out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnEnter)})
			}
		}
	}
	if cur.FenceState == device.Unknown {
		for _, f := range fences {
			for _, a := range f.ActionsFor(fence.OnUnknown) {
				out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnUnknown)})
			}
		}
	}
	return out
}

// planStanding dispara on_violation cada N ciclos mientras el dispositivo
// siga fuera; estar dentro resetea el contador de esa geocerca.
func (e *Engine) planStanding(cur device.Device, fences []fence.Fence) []Planned {
	var out []Planned
	for _, f := range fences {
		acts := f.ActionsFor(fence.OnViolation)
		key := cur.ID + "|" + f.ID
		if cur.FenceState != device.Outside || len(acts) == 0 {
			e.violations[key] = 0
			continue
		}
		e.violations[key]++
		interval := f.Rules.ViolationIntervalCycles
		if interval < 1 {
			interval = 1
		}
		if e.violations[key]%interval != 0 {
			continue
		}
		for _, a := range acts {
			out = append(out, Planned{Device: cur, Action: a, FenceID: f.ID, Trigger: string(fence.OnViolation)})
		}
	}
	return out
}

// alreadyFired deduplica por ciclo (dispositivo, acción, geocerca, trigger).
func (e *Engine) alreadyFired(p Planned) bool {
	key := fmt.Sprintf("%s|%s|%s|%s", p.Device.ID, p.Action.Action, p.FenceID, p.Trigger)
	if e.fired[key] {
		return true
	}
	e.fired[key] = true
	return false
}

// execute pasa por los guardarraíles y llama al conector del dispositivo.
func (e *Engine) execute(ctx context.Context, p Planned) action.Result {
	dryRun := e.guard.DryRun(p.Action.Action)
	ad, ok := e.adapters[p.Device.Provider]
	if !ok {
		return action.Result{Adapter: p.Device.Provider, OK: false, DeviceID: p.Device.ID, DeviceName: p.Device.Name, Action: p.Action.Action,
			DryRun: dryRun, Error: "sin conector para el proveedor", At: e.opts.Now().UTC(), FenceID: p.FenceID, Trigger: p.Trigger}
	}
	res := ad.Execute(ctx, p.Device, p.Action.Action, p.Action.Params, dryRun)
	res.FenceID, res.Trigger = p.FenceID, p.Trigger
	if res.At.IsZero() {
		res.At = e.opts.Now().UTC()
	}
	return res
}
```

- [ ] **Step 4: Tests del motor (fallan)**

`internal/engine/engine_test.go`:
```go
package engine

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
)

func newEngine(t *testing.T, adapters ...uem.Adapter) (*Engine, *store.OrgStore) {
	t.Helper()
	s, _ := store.Open(t.TempDir())
	org, _ := s.Org("default")
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	if err := SeedDemo(org, now); err != nil {
		t.Fatal(err)
	}
	if len(adapters) == 0 {
		adapters = []uem.Adapter{simulation.New(simulation.DefaultSeed(), func() time.Time { return now })}
	}
	return New(org, adapters, Options{Mode: "simulation", Interval: 50 * time.Millisecond, Now: func() time.Time { return now }}), org
}

func TestRunOnceEvaluaFlotaDemo(t *testing.T) {
	e, org := newEngine(t)
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.DevicesTotal != 6 || st.Inside < 2 || st.Transitions != 6 || st.Providers["simulation"].Devices != 6 || !st.Providers["simulation"].OK {
		t.Fatalf("stats: %+v", st)
	}
	ds, _ := org.Devices()
	idx := device.Index(ds)
	if idx["dev-001"].FenceState != device.Inside || idx["dev-001"].InsideFence != "demo-hq" {
		t.Fatalf("dev-001 debe estar en demo-hq: %+v", idx["dev-001"])
	}
	if idx["dev-004"].FenceState != device.Outside || idx["dev-005"].InsideFence != "warehouse-poly" {
		t.Fatalf("dev-004 fuera, dev-005 en almacén: %+v %+v", idx["dev-004"], idx["dev-005"])
	}
	if idx["dev-002"].RouteState != device.OnRoute || idx["dev-002"].RouteID != "route-centro" {
		t.Fatalf("dev-002 en ruta: %+v", idx["dev-002"])
	}
	evs, _ := org.RecentEvents(100)
	found := false
	for _, ev := range evs {
		if ev.DeviceID == "dev-001" && ev.From == "none:unknown" && ev.To == "demo-hq:inside" {
			found = true
		}
	}
	if !found {
		t.Fatalf("falta la transición de dev-001: %+v", evs)
	}
	acts, _ := org.RecentActions(100)
	if len(acts) == 0 || st.ActionsExecuted != len(acts) {
		t.Fatalf("acciones: %d vs %d", len(acts), st.ActionsExecuted)
	}
	for _, a := range acts {
		if !a.DryRun || !a.Simulated || a.Trigger == "" {
			t.Fatalf("en observe todo es dry-run: %+v", a)
		}
	}
	tr, _ := org.Trail("dev-001", 10)
	if len(tr) != 1 {
		t.Fatalf("trail: %d", len(tr))
	}
	st2, _ := e.RunOnce(context.Background())
	if st2.Transitions >= 6 {
		t.Fatalf("segundo ciclo no repite las transiciones iniciales: %+v", st2)
	}
	if e.Status().Cycles != 2 || e.Status().Enforcement != "observe" || e.Status().LastCycle == nil {
		t.Fatalf("status: %+v", e.Status())
	}
}

type slowAdapter struct {
	uem.Adapter
	release chan struct{}
	started chan struct{}
	once    sync.Once
}

func (s *slowAdapter) FetchDevices(ctx context.Context) ([]device.Device, error) {
	s.once.Do(func() { close(s.started) })
	<-s.release
	return s.Adapter.FetchDevices(ctx)
}

func TestRunOnceNoSolapaCiclos(t *testing.T) {
	slow := &slowAdapter{Adapter: simulation.New(simulation.DefaultSeed(), time.Now), release: make(chan struct{}), started: make(chan struct{})}
	e, _ := newEngine(t, slow)
	done := make(chan struct{})
	go func() { e.RunOnce(context.Background()); close(done) }()
	<-slow.started
	if _, err := e.RunOnce(context.Background()); !errors.Is(err, ErrCycleInProgress) {
		t.Fatalf("esperaba ErrCycleInProgress, got %v", err)
	}
	close(slow.release)
	<-done
}

type failing struct{ uem.Adapter }

func (failing) Name() string                                        { return "broken" }
func (failing) FetchDevices(context.Context) ([]device.Device, error) { return nil, errors.New("HTTP 401") }

type panicking struct{ uem.Adapter }

func (panicking) Name() string                                        { return "panicky" }
func (panicking) FetchDevices(context.Context) ([]device.Device, error) { panic("boom") }

func TestProveedorRotoNoTumbaElCiclo(t *testing.T) {
	sim := simulation.New(simulation.DefaultSeed(), time.Now)
	e, _ := newEngine(t, failing{sim}, panicking{sim}, sim)
	st, err := e.RunOnce(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if st.DevicesTotal != 6 || st.Providers["broken"].OK || st.Providers["broken"].Error != "HTTP 401" || st.Providers["panicky"].OK {
		t.Fatalf("%+v", st.Providers)
	}
}

func TestStartStopEjecutaCiclosPeriodicos(t *testing.T) {
	e, _ := newEngine(t)
	ctx, cancel := context.WithCancel(context.Background())
	e.Start(ctx)
	deadline := time.Now().Add(2 * time.Second)
	for e.Status().Cycles < 2 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if !e.Status().Running || e.Status().NextCycleAt == nil {
		t.Fatalf("status en marcha: %+v", e.Status())
	}
	cancel()
	e.Stop()
	if e.Status().Running || e.Status().Cycles < 2 {
		t.Fatalf("tras Stop: %+v", e.Status())
	}
	_ = action.All
}
```

`internal/engine/demo_test.go`:
```go
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
```

- [ ] **Step 5: Implementar `engine.go`, `cycle.go` y `demo.go`**

`internal/engine/engine.go`:
```go
// Package engine ejecuta el ciclo de evaluación (spec §5.4): pide la flota a
// cada conector, evalúa geocercas y rutas, detecta transiciones, decide
// acciones bajo guardarraíles y persiste. Un solo ciclo a la vez.
package engine

import (
	"context"
	"errors"
	"log/slog"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// ErrCycleInProgress se devuelve si RunOnce se solapa con otro ciclo.
var ErrCycleInProgress = errors.New("ciclo en curso")

// Options configura el motor.
type Options struct {
	Mode     string
	Interval time.Duration
	Now      func() time.Time
	Logger   *slog.Logger
}

// ProviderHealth es la salud de un conector.
type ProviderHealth struct {
	OK        bool       `json:"ok"`
	Error     string     `json:"error,omitempty"`
	Devices   int        `json:"devices"`
	LatencyMS int64      `json:"latency_ms"`
	LastOK    *time.Time `json:"last_ok,omitempty"`
}

// CycleStats resume un ciclo.
type CycleStats struct {
	At               time.Time                 `json:"at"`
	DurationMS       int64                     `json:"duration_ms"`
	Mode             string                    `json:"mode"`
	DevicesTotal     int                       `json:"devices_total"`
	Inside           int                       `json:"inside"`
	Outside          int                       `json:"outside"`
	Unknown          int                       `json:"unknown"`
	Transitions      int                       `json:"transitions"`
	ActionsPlanned   int                       `json:"actions_planned"`
	ActionsExecuted  int                       `json:"actions_executed"`
	EvaluationErrors int                       `json:"evaluation_errors"`
	Providers        map[string]ProviderHealth `json:"providers"`
}

// Status es lo que expone /api/v1/engine/status.
type Status struct {
	Mode            string                    `json:"mode"`
	Enforcement     string                    `json:"enforcement"`
	IntervalSeconds int                       `json:"interval_seconds"`
	Running         bool                      `json:"running"`
	Cycles          int                       `json:"cycles"`
	LastCycle       *CycleStats               `json:"last_cycle,omitempty"`
	NextCycleAt     *time.Time                `json:"next_cycle_at,omitempty"`
	Providers       map[string]ProviderHealth `json:"providers"`
}

// Engine es el motor de una organización.
type Engine struct {
	org      *store.OrgStore
	adapters map[string]uem.Adapter
	order    []string
	opts     Options
	guard    Guardrails

	cycleMu    sync.Mutex
	stateMu    sync.RWMutex
	running    bool
	cycles     int
	last       *CycleStats
	nextAt     *time.Time
	providers  map[string]ProviderHealth
	violations map[string]int
	fired      map[string]bool
	wg         sync.WaitGroup
}

// New crea el motor. El enforcement nace en observe y M1 no ofrece forma de cambiarlo.
func New(org *store.OrgStore, adapters []uem.Adapter, opts Options) *Engine {
	if opts.Now == nil {
		opts.Now = time.Now
	}
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	if opts.Interval <= 0 {
		opts.Interval = 15 * time.Minute
	}
	e := &Engine{org: org, adapters: map[string]uem.Adapter{}, opts: opts, guard: Guardrails{Enforcement: EnforcementObserve},
		providers: map[string]ProviderHealth{}, violations: map[string]int{}, fired: map[string]bool{}}
	for _, a := range adapters {
		e.adapters[a.Name()] = a
		e.order = append(e.order, a.Name())
	}
	return e
}

// Guardrails expone la configuración de enforcement vigente.
func (e *Engine) Guardrails() Guardrails { return e.guard }

// RunOnce ejecuta un ciclo si no hay otro en curso.
func (e *Engine) RunOnce(ctx context.Context) (CycleStats, error) {
	if !e.cycleMu.TryLock() {
		return CycleStats{}, ErrCycleInProgress
	}
	defer e.cycleMu.Unlock()
	e.fired = map[string]bool{}
	st, err := e.runCycle(ctx)
	e.stateMu.Lock()
	e.cycles++
	e.last = &st
	e.providers = st.Providers
	e.stateMu.Unlock()
	return st, err
}

// Start lanza el bucle periódico: un ciclo inmediato y luego cada Interval.
func (e *Engine) Start(ctx context.Context) {
	e.stateMu.Lock()
	e.running = true
	e.stateMu.Unlock()
	e.wg.Add(1)
	go func() {
		defer e.wg.Done()
		defer func() {
			e.stateMu.Lock()
			e.running, e.nextAt = false, nil
			e.stateMu.Unlock()
		}()
		t := time.NewTicker(e.opts.Interval)
		defer t.Stop()
		for {
			if _, err := e.RunOnce(ctx); err != nil && !errors.Is(err, ErrCycleInProgress) {
				e.opts.Logger.Error("ciclo", "error", err)
			}
			next := e.opts.Now().Add(e.opts.Interval)
			e.stateMu.Lock()
			e.nextAt = &next
			e.stateMu.Unlock()
			select {
			case <-ctx.Done():
				return
			case <-t.C:
			}
		}
	}()
}

// Stop espera a que el bucle termine (tras cancelar el contexto de Start).
func (e *Engine) Stop() { e.wg.Wait() }

// Status devuelve el estado actual.
func (e *Engine) Status() Status {
	e.stateMu.RLock()
	defer e.stateMu.RUnlock()
	return Status{Mode: e.opts.Mode, Enforcement: e.guard.Enforcement, IntervalSeconds: int(e.opts.Interval / time.Second),
		Running: e.running, Cycles: e.cycles, LastCycle: e.last, NextCycleAt: e.nextAt, Providers: e.providers}
}
```

`internal/engine/cycle.go`:
```go
package engine

import (
	"context"
	"fmt"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/domain/transition"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

type cycleInput struct {
	fences []fence.Fence
	routes []route.Route
	prev   map[string]device.Device
}

func (e *Engine) loadInput() (cycleInput, error) {
	fs, err := e.org.Fences()
	if err != nil {
		return cycleInput{}, err
	}
	rs, err := e.org.Routes()
	if err != nil {
		return cycleInput{}, err
	}
	ds, err := e.org.Devices()
	if err != nil {
		return cycleInput{}, err
	}
	return cycleInput{fences: fs, routes: rs, prev: device.Index(ds)}, nil
}

func fetchSafe(ctx context.Context, ad uem.Adapter) (ds []device.Device, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("pánico en el conector: %v", r)
		}
	}()
	return ad.FetchDevices(ctx)
}

func (e *Engine) fetchAll(ctx context.Context, st *CycleStats) []device.Device {
	var all []device.Device
	for _, name := range e.order {
		start := time.Now()
		ds, err := fetchSafe(ctx, e.adapters[name])
		h := ProviderHealth{LatencyMS: time.Since(start).Milliseconds(), Devices: len(ds)}
		if err != nil {
			h.Error = err.Error()
			if prev, ok := e.providers[name]; ok {
				h.LastOK = prev.LastOK
			}
			e.opts.Logger.Warn("proveedor", "name", name, "error", err)
		} else {
			now := e.opts.Now().UTC()
			h.OK, h.LastOK = true, &now
			all = append(all, ds...)
		}
		st.Providers[name] = h
	}
	return all
}

// evaluateDevice evalúa un dispositivo con recover: un fallo deja el
// dispositivo en evaluation_error con riesgo nulo y el ciclo sigue.
func (e *Engine) evaluateDevice(in cycleInput, cur *device.Device, now time.Time) (tr *transition.Transition, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("%v", r)
			cur.EvaluationError = err.Error()
			cur.Risk.Score = nil
		}
	}()
	var prev *device.Device
	if p, ok := in.prev[cur.ID]; ok {
		prev = &p
	}
	tr = transition.Evaluate(prev, cur, in.fences, now)
	cur.RouteState, cur.RouteID, cur.RouteDeviationM = device.Unassigned, "", nil
	if r, ok := route.ForDevice(in.routes, cur.ID); ok && cur.Location.Point != nil {
		d := r.DistanceM(*cur.Location.Point)
		cur.RouteID, cur.RouteDeviationM = r.ID, &d
		cur.RouteState = device.OnRoute
		if d > r.CorridorM {
			cur.RouteState = device.OffRoute
		}
	}
	return tr, nil
}

func (e *Engine) runCycle(ctx context.Context) (CycleStats, error) {
	start := time.Now()
	now := e.opts.Now().UTC()
	st := CycleStats{At: now, Mode: e.opts.Mode, Providers: map[string]ProviderHealth{}}
	in, err := e.loadInput()
	if err != nil {
		return st, err
	}
	devices := e.fetchAll(ctx, &st)
	var results []action.Result
	for i := range devices {
		cur := &devices[i]
		tr, evalErr := e.evaluateDevice(in, cur, now)
		if evalErr != nil {
			st.EvaluationErrors++
		}
		switch cur.FenceState {
		case device.Inside:
			st.Inside++
		case device.Outside:
			st.Outside++
		default:
			st.Unknown++
		}
		if cur.Location.Point != nil {
			_ = e.org.AppendTrail(cur.ID, *cur.Location.Point, now)
		}
		if tr != nil {
			st.Transitions++
			_ = e.org.AppendEvent(*tr)
		}
		planned := append(PlanTransition(*cur, tr, in.fences), e.planStanding(*cur, in.fences)...)
		for _, p := range planned {
			if e.alreadyFired(p) {
				continue
			}
			st.ActionsPlanned++
			res := e.execute(ctx, p)
			results = append(results, res)
		}
	}
	st.DevicesTotal = len(devices)
	if err := e.org.SaveDevices(devices); err != nil {
		return st, err
	}
	for _, r := range results {
		if err := e.org.AppendAction(r); err == nil {
			st.ActionsExecuted++
		}
	}
	st.DurationMS = time.Since(start).Milliseconds()
	_ = e.org.AppendStats(st)
	return st, nil
}
```

`internal/engine/demo.go`:
```go
package engine

import (
	"errors"
	"os"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
)

// SeedDemo escribe los datos demo (geocercas, ruta, POIs y seed) solo donde
// no exista nada; es idempotente y nunca sobrescribe.
func SeedDemo(org *store.OrgStore, now time.Time) error {
	if fs, err := org.Fences(); err != nil {
		return err
	} else if len(fs) == 0 {
		if err := org.SaveFences(demoFences(now)); err != nil {
			return err
		}
	}
	if rs, err := org.Routes(); err != nil {
		return err
	} else if len(rs) == 0 {
		if err := org.SaveRoutes(demoRoutes(now)); err != nil {
			return err
		}
	}
	if ps, err := org.POIs(); err != nil {
		return err
	} else if len(ps) == 0 {
		if err := org.SavePOIs(demoPOIs()); err != nil {
			return err
		}
	}
	if _, err := os.Stat(org.Path("seed.json")); errors.Is(err, os.ErrNotExist) {
		return simulation.SaveSeed(org.Path("seed.json"), simulation.DefaultSeed())
	}
	return nil
}

func demoFences(now time.Time) []fence.Fence {
	return []fence.Fence{
		{ID: "demo-hq", Name: "Demo HQ · Madrid", Kind: fence.Circle, Center: &geo.Point{Lat: 40.421, Lng: -3.708}, RadiusM: 500,
			Actions: []fence.Action{
				{Action: action.Message, When: fence.OnEnter, Enabled: true, Params: map[string]any{"text": "Bienvenido a la Oficina HQ."}},
				{Action: action.Notify, When: fence.OnExit, Enabled: true, Params: map[string]any{"channel": "security", "msg": "Dispositivo ha salido de HQ"}},
			}, CreatedAt: now, UpdatedAt: now},
		{ID: "warehouse-poly", Name: "Almacén Sur", Kind: fence.Polygon,
			Polygon: []geo.Point{{Lat: 40.4030, Lng: -3.7140}, {Lat: 40.4030, Lng: -3.7080}, {Lat: 40.4080, Lng: -3.7080}, {Lat: 40.4080, Lng: -3.7140}},
			Actions: []fence.Action{{Action: action.Locate, When: fence.OnExit, Enabled: true}}, CreatedAt: now, UpdatedAt: now},
	}
}

func demoRoutes(now time.Time) []route.Route {
	return []route.Route{{ID: "route-centro", Name: "Ruta Comercial Centro", CorridorM: 300, DeviceIDs: []string{"dev-002"}, Color: "#3E7A5E",
		Waypoints: []geo.Point{{Lat: 40.4300, Lng: -3.6900}, {Lat: 40.4250, Lng: -3.7000}, {Lat: 40.4210, Lng: -3.7080}},
		Actions:   []fence.Action{{Action: action.Notify, When: fence.OnExit, Enabled: true, Params: map[string]any{"channel": "security", "msg": "Comercial fuera de la ruta asignada"}}},
		CreatedAt: now, UpdatedAt: now}}
}

func demoPOIs() []poi.POI {
	return []poi.POI{
		{ID: "poi-school-001", Name: "Colegio Público", Category: "school", Tags: []string{"education"}, Point: geo.Point{Lat: 40.418, Lng: -3.705}},
		{ID: "poi-hospital-001", Name: "Hospital Central", Category: "hospital", Tags: []string{"health"}, Point: geo.Point{Lat: 40.425, Lng: -3.700}},
	}
}
```

- [ ] **Step 6: Tests (pasan) con carrera y cobertura, lint, documentar, commit**

Run: `go test ./internal/engine/ -race -cover -v && golangci-lint run ./internal/engine/`
Expected: PASS, cobertura ≥ 85 %. Si `funlen` señala `runCycle`, extraer el bucle por dispositivo a `func (e *Engine) processDevice(ctx, in, cur, now, st *CycleStats) []action.Result`.

`ARCHITECTURE.md`:
```
| `internal/engine` | Ciclo de evaluación bajo TryLock, planificación de acciones, guardarraíles (observe por defecto), datos demo. |
```

```bash
git add internal/engine ARCHITECTURE.md
git commit -q -m "feat(engine): ciclo de evaluación con transiciones, acciones dry-run y guardarraíles observe

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 9: Autenticación y roles (`internal/auth`)

**Files:**
- Create: `internal/auth/rbac.go`, `internal/auth/password.go`, `internal/auth/store.go`, `internal/auth/rbac_test.go`, `internal/auth/password_test.go`, `internal/auth/store_test.go`
- Modify: `go.mod`, `go.sum` (añade `golang.org/x/crypto v0.56.0`), `ARCHITECTURE.md`

**Interfaces:**
- Produces:
  ```go
  type Role string        // Owner "owner" | Admin "admin" | Operator "operator" | Viewer "viewer" | Auditor "auditor"
  type Capability string  // constantes de spec §6.3: OrgRead "org:read", OrgUpdate, OrgDelete, UserInvite, UserRemove, UserRole, APIKeyManage "apikey:manage",
                          // DeviceRead, DeviceWrite, DeviceAction, FenceRead, FenceWrite, FenceDelete, RouteRead, RouteWrite, RouteDelete, PolicyRead, PolicyWrite,
                          // EngineRun "engine:run", EngineConfig "engine:config", IncidentRead, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove "handoff:approve",
                          // ReportRead, ReportExport, AuditRead
  func Can(role Role, c Capability) bool
  func ParseRole(s string) (Role, error)
  func Capabilities(role Role) []Capability   // ordenadas
  func HashPassword(pw string) (string, error) // argon2id$v=19$m=65536,t=3,p=2$<salt>$<hash> (base64 raw)
  func VerifyPassword(pw, encoded string) bool
  const MinPasswordLength = 10
  type User struct { ID, Email, Name, PasswordHash string; OrgRoles map[string]Role; CreatedAt time.Time }  // json snake_case; password_hash nunca sale por la API
  type Session struct { Token, UserID, OrgID, CSRF string; CreatedAt, ExpiresAt time.Time }
  type Principal struct { UserID, Email, Name, OrgID string; Role Role; Via string; CSRF string }         // Via: "session" | "local-token"
  var ErrAlreadySetUp, ErrInvalidCredentials, ErrThrottled, ErrUnauthenticated, ErrWeakPassword error
  const SessionTTL = 12 * time.Hour
  type Store struct{ ... }
  func Open(dir string, now func() time.Time) (*Store, error)  // users.json, sessions.json, local-token (0600)
  func (s *Store) HasUsers() bool
  func (s *Store) Setup(email, name, password, orgID string) (User, error)
  func (s *Store) Login(email, password, orgID string) (Session, error)
  func (s *Store) Logout(token string) error
  func (s *Store) Resolve(token string) (*Principal, error)
  func (s *Store) LocalToken() string
  func (s *Store) ResolveLocal(token, orgID string) (*Principal, error)
  func (s *Store) UserByID(id string) (User, bool)
  ```

- [ ] **Step 1: Añadir la dependencia permitida**

```bash
go get golang.org/x/crypto@v0.56.0
go test ./internal/arch/ -run TestGoDependencyAllowlist
```

Expected: PASS (la allowlist ya la contiene).

- [ ] **Step 2: Tests de RBAC y contraseñas (fallan)**

`internal/auth/rbac_test.go`:
```go
package auth

import "testing"

func TestMatrizDeRoles(t *testing.T) {
	cases := []struct {
		role Role
		cap  Capability
		want bool
	}{
		{Owner, OrgDelete, true}, {Admin, OrgDelete, false}, {Owner, UserRole, true}, {Admin, UserRole, false},
		{Admin, APIKeyManage, true}, {Operator, APIKeyManage, false},
		{Operator, DeviceAction, true}, {Operator, DeviceWrite, false}, {Viewer, DeviceRead, true}, {Viewer, DeviceAction, false},
		{Operator, FenceWrite, true}, {Operator, FenceDelete, false}, {Admin, FenceDelete, true},
		{Operator, EngineRun, true}, {Viewer, EngineRun, false}, {Operator, EngineConfig, false}, {Admin, EngineConfig, true},
		{Operator, HandoffApprove, true}, {Auditor, HandoffApprove, false},
		{Auditor, ReportExport, true}, {Viewer, ReportExport, false}, {Auditor, AuditRead, true}, {Operator, AuditRead, false},
		{Auditor, FenceWrite, false}, {Auditor, OrgRead, true},
		{Role("god"), OrgRead, false},
	}
	for _, c := range cases {
		if got := Can(c.role, c.cap); got != c.want {
			t.Errorf("Can(%s, %s)=%v want %v", c.role, c.cap, got, c.want)
		}
	}
}

func TestParseRoleYCapabilities(t *testing.T) {
	if r, err := ParseRole("admin"); err != nil || r != Admin {
		t.Fatal(err)
	}
	if _, err := ParseRole("root"); err == nil {
		t.Fatal("rol desconocido")
	}
	caps := Capabilities(Viewer)
	if len(caps) == 0 || caps[0] != DeviceRead {
		t.Fatalf("Capabilities(viewer) ordenadas: %v", caps)
	}
}
```

`internal/auth/password_test.go`:
```go
package auth

import (
	"strings"
	"testing"
)

func TestHashYVerify(t *testing.T) {
	h, err := HashPassword("correcto-caballo-bateria")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(h, "argon2id$v=19$m=65536,t=3,p=2$") {
		t.Fatalf("formato: %s", h)
	}
	if !VerifyPassword("correcto-caballo-bateria", h) || VerifyPassword("otra", h) || VerifyPassword("x", "basura") {
		t.Fatal("verify")
	}
	h2, _ := HashPassword("correcto-caballo-bateria")
	if h == h2 {
		t.Fatal("la sal debe ser aleatoria")
	}
	if _, err := HashPassword("corta"); err != ErrWeakPassword {
		t.Fatalf("esperaba ErrWeakPassword, got %v", err)
	}
}
```

- [ ] **Step 3: Implementar `rbac.go` y `password.go`**

`internal/auth/rbac.go`:
```go
// Package auth cubre usuarios locales, sesiones con CSRF, token local para
// CLI/MCP y la matriz de roles y capacidades (spec §6.2-§6.3).
package auth

import (
	"fmt"
	"sort"
)

// Role es un rol dentro de una organización.
type Role string

// Capability es un permiso grueso que cada ruta declara.
type Capability string

const (
	Owner    Role = "owner"
	Admin    Role = "admin"
	Operator Role = "operator"
	Viewer   Role = "viewer"
	Auditor  Role = "auditor"
)

const (
	OrgRead        Capability = "org:read"
	OrgUpdate      Capability = "org:update"
	OrgDelete      Capability = "org:delete"
	UserInvite     Capability = "user:invite"
	UserRemove     Capability = "user:remove"
	UserRole       Capability = "user:role"
	APIKeyManage   Capability = "apikey:manage"
	DeviceRead     Capability = "device:read"
	DeviceWrite    Capability = "device:write"
	DeviceAction   Capability = "device:action"
	FenceRead      Capability = "fence:read"
	FenceWrite     Capability = "fence:write"
	FenceDelete    Capability = "fence:delete"
	RouteRead      Capability = "route:read"
	RouteWrite     Capability = "route:write"
	RouteDelete    Capability = "route:delete"
	PolicyRead     Capability = "policy:read"
	PolicyWrite    Capability = "policy:write"
	EngineRun      Capability = "engine:run"
	EngineConfig   Capability = "engine:config"
	IncidentRead   Capability = "incident:read"
	IncidentWrite  Capability = "incident:write"
	AlertWrite     Capability = "alert:write"
	PlaybookWrite  Capability = "playbook:write"
	HandoffApprove Capability = "handoff:approve"
	ReportRead     Capability = "report:read"
	ReportExport   Capability = "report:export"
	AuditRead      Capability = "audit:read"
)

var readCaps = []Capability{OrgRead, DeviceRead, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead}

func set(caps ...Capability) map[Capability]bool {
	m := map[Capability]bool{}
	for _, c := range caps {
		m[c] = true
	}
	return m
}

var roleCaps = map[Role]map[Capability]bool{
	Viewer:  set(readCaps...),
	Auditor: set(append(readCaps, ReportExport, AuditRead)...),
	Operator: set(append(readCaps, DeviceAction, FenceWrite, RouteWrite, EngineRun, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove)...),
	Admin: set(append(readCaps, OrgUpdate, UserInvite, UserRemove, APIKeyManage, DeviceWrite, DeviceAction, FenceWrite, FenceDelete, RouteWrite, RouteDelete,
		PolicyWrite, EngineRun, EngineConfig, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove, ReportExport, AuditRead)...),
	Owner: set(append(readCaps, OrgUpdate, OrgDelete, UserInvite, UserRemove, UserRole, APIKeyManage, DeviceWrite, DeviceAction, FenceWrite, FenceDelete, RouteWrite,
		RouteDelete, PolicyWrite, EngineRun, EngineConfig, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove, ReportExport, AuditRead)...),
}

// Can indica si el rol tiene la capacidad.
func Can(role Role, c Capability) bool { return roleCaps[role][c] }

// ParseRole valida un rol.
func ParseRole(s string) (Role, error) {
	r := Role(s)
	if _, ok := roleCaps[r]; !ok {
		return "", fmt.Errorf("rol desconocido %q", s)
	}
	return r, nil
}

// Capabilities lista las capacidades de un rol en orden estable.
func Capabilities(role Role) []Capability {
	out := make([]Capability, 0, len(roleCaps[role]))
	for c := range roleCaps[role] {
		out = append(out, c)
	}
	sort.Slice(out, func(i, j int) bool { return out[i] < out[j] })
	return out
}
```

`internal/auth/password.go`:
```go
package auth

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"errors"
	"fmt"
	"strings"

	"golang.org/x/crypto/argon2"
)

// MinPasswordLength es la longitud mínima aceptada.
const MinPasswordLength = 10

// ErrWeakPassword indica una contraseña demasiado corta.
var ErrWeakPassword = errors.New("la contraseña debe tener al menos 10 caracteres")

const (
	argonTime    = 3
	argonMemory  = 64 * 1024
	argonThreads = 2
	argonKeyLen  = 32
)

// HashPassword deriva la contraseña con argon2id y sal aleatoria.
func HashPassword(pw string) (string, error) {
	if len(pw) < MinPasswordLength {
		return "", ErrWeakPassword
	}
	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return "", err
	}
	key := argon2.IDKey([]byte(pw), salt, argonTime, argonMemory, argonThreads, argonKeyLen)
	enc := base64.RawStdEncoding
	return fmt.Sprintf("argon2id$v=19$m=%d,t=%d,p=%d$%s$%s", argonMemory, argonTime, argonThreads, enc.EncodeToString(salt), enc.EncodeToString(key)), nil
}

// VerifyPassword compara en tiempo constante.
func VerifyPassword(pw, encoded string) bool {
	parts := strings.Split(encoded, "$")
	if len(parts) != 5 || parts[0] != "argon2id" {
		return false
	}
	var mem, t uint32
	var p uint8
	if _, err := fmt.Sscanf(parts[2], "m=%d,t=%d,p=%d", &mem, &t, &p); err != nil {
		return false
	}
	enc := base64.RawStdEncoding
	salt, err := enc.DecodeString(parts[3])
	if err != nil {
		return false
	}
	want, err := enc.DecodeString(parts[4])
	if err != nil {
		return false
	}
	got := argon2.IDKey([]byte(pw), salt, t, mem, p, uint32(len(want)))
	return subtle.ConstantTimeCompare(got, want) == 1
}
```

Run: `go test ./internal/auth/ -run 'TestMatriz|TestParseRole|TestHash' -v` → PASS.

- [ ] **Step 4: Tests del almacén de auth (fallan)**

`internal/auth/store_test.go`:
```go
package auth

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

func openStore(t *testing.T) (*Store, *time.Time) {
	t.Helper()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	s, err := Open(t.TempDir(), func() time.Time { return now })
	if err != nil {
		t.Fatal(err)
	}
	return s, &now
}

func TestSetupLoginResolveLogout(t *testing.T) {
	s, _ := openStore(t)
	if s.HasUsers() {
		t.Fatal("vacío al abrir")
	}
	u, err := s.Setup("Adri@Example.com", "Adri", "contraseña-larga-1", "default")
	if err != nil || u.Email != "adri@example.com" || u.OrgRoles["default"] != Owner || u.PasswordHash == "" || u.ID == "" {
		t.Fatalf("setup: %v %+v", err, u)
	}
	if _, err := s.Setup("otro@example.com", "Otro", "contraseña-larga-1", "default"); !errors.Is(err, ErrAlreadySetUp) {
		t.Fatalf("segundo setup: %v", err)
	}
	if _, err := s.Login("adri@example.com", "mal", "default"); !errors.Is(err, ErrInvalidCredentials) {
		t.Fatalf("login mal: %v", err)
	}
	sess, err := s.Login("adri@example.com", "contraseña-larga-1", "default")
	if err != nil || sess.Token == "" || sess.CSRF == "" || sess.OrgID != "default" || !sess.ExpiresAt.After(sess.CreatedAt) {
		t.Fatalf("login: %v %+v", err, sess)
	}
	p, err := s.Resolve(sess.Token)
	if err != nil || p.Role != Owner || p.Email != "adri@example.com" || p.Via != "session" || p.CSRF != sess.CSRF {
		t.Fatalf("resolve: %v %+v", err, p)
	}
	if err := s.Logout(sess.Token); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Resolve(sess.Token); !errors.Is(err, ErrUnauthenticated) {
		t.Fatalf("tras logout: %v", err)
	}
	if _, err := s.Resolve("token-inventado"); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("token inventado")
	}
}

func TestThrottleTrasCincoFallos(t *testing.T) {
	s, _ := openStore(t)
	_, _ = s.Setup("a@x.com", "A", "contraseña-larga-1", "default")
	for i := 0; i < 5; i++ {
		if _, err := s.Login("a@x.com", "mal", "default"); !errors.Is(err, ErrInvalidCredentials) {
			t.Fatalf("intento %d: %v", i, err)
		}
	}
	if _, err := s.Login("a@x.com", "contraseña-larga-1", "default"); !errors.Is(err, ErrThrottled) {
		t.Fatalf("sexto intento bloqueado aunque sea correcto: %v", err)
	}
}

func TestSesionCaducaYPersiste(t *testing.T) {
	dir := t.TempDir()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	s, _ := Open(dir, func() time.Time { return now })
	_, _ = s.Setup("a@x.com", "A", "contraseña-larga-1", "default")
	sess, _ := s.Login("a@x.com", "contraseña-larga-1", "default")
	s2, err := Open(dir, func() time.Time { return now.Add(time.Hour) })
	if err != nil {
		t.Fatal(err)
	}
	if !s2.HasUsers() {
		t.Fatal("usuarios persistidos")
	}
	if _, err := s2.Resolve(sess.Token); err != nil {
		t.Fatalf("sesión persistida: %v", err)
	}
	s3, _ := Open(dir, func() time.Time { return now.Add(SessionTTL + time.Minute) })
	if _, err := s3.Resolve(sess.Token); !errors.Is(err, ErrUnauthenticated) {
		t.Fatalf("caducada: %v", err)
	}
	if u, ok := s3.UserByID(sess.UserID); !ok || u.Name != "A" {
		t.Fatal("UserByID")
	}
}

func TestTokenLocal(t *testing.T) {
	dir := t.TempDir()
	s, _ := openStoreIn(t, dir)
	tok := s.LocalToken()
	if len(tok) != 64 {
		t.Fatalf("token hex de 32 bytes: %q", tok)
	}
	info, err := os.Stat(filepath.Join(dir, "local-token"))
	if err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS != "windows" && info.Mode().Perm() != 0o600 {
		t.Fatalf("permisos %o", info.Mode().Perm())
	}
	p, err := s.ResolveLocal(tok, "default")
	if err != nil || p.Role != Admin || p.Via != "local-token" || p.OrgID != "default" {
		t.Fatalf("%v %+v", err, p)
	}
	if _, err := s.ResolveLocal("x", "default"); !errors.Is(err, ErrUnauthenticated) {
		t.Fatal("token incorrecto")
	}
	s2, _ := openStoreIn(t, dir)
	if s2.LocalToken() != tok {
		t.Fatal("el token local se reutiliza entre arranques")
	}
}

func openStoreIn(t *testing.T, dir string) (*Store, error) {
	t.Helper()
	return Open(dir, time.Now)
}
```

- [ ] **Step 5: Implementar `store.go`**

```go
package auth

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/adrimg3196/lucidfence/internal/store"
)

// Errores de autenticación.
var (
	ErrAlreadySetUp       = errors.New("la instalación ya tiene usuarios")
	ErrInvalidCredentials = errors.New("credenciales incorrectas")
	ErrThrottled          = errors.New("demasiados intentos; espera un minuto")
	ErrUnauthenticated    = errors.New("no autenticado")
)

// SessionTTL es la vida de una sesión.
const SessionTTL = 12 * time.Hour

const (
	maxFails   = 5
	failWindow = time.Minute
)

// User es un usuario local. password_hash nunca se serializa hacia la API.
type User struct {
	ID           string          `json:"id"`
	Email        string          `json:"email"`
	Name         string          `json:"name"`
	PasswordHash string          `json:"password_hash"`
	OrgRoles     map[string]Role `json:"org_roles"`
	CreatedAt    time.Time       `json:"created_at"`
}

// Session es una sesión de cookie.
type Session struct {
	Token     string    `json:"token"`
	UserID    string    `json:"user_id"`
	OrgID     string    `json:"org_id"`
	CSRF      string    `json:"csrf"`
	CreatedAt time.Time `json:"created_at"`
	ExpiresAt time.Time `json:"expires_at"`
}

// Principal es la identidad resuelta de una petición.
type Principal struct {
	UserID string `json:"user_id"`
	Email  string `json:"email"`
	Name   string `json:"name"`
	OrgID  string `json:"org_id"`
	Role   Role   `json:"role"`
	Via    string `json:"via"`
	CSRF   string `json:"-"`
}

type collection[T any] struct {
	SchemaVersion int `json:"schema_version"`
	Items         []T `json:"items"`
}

// Store persiste usuarios y sesiones en <data>/auth.
type Store struct {
	dir        string
	now        func() time.Time
	mu         sync.Mutex
	users      []User
	sessions   map[string]Session
	localToken string
	fails      map[string][]time.Time
}

// Open carga usuarios y sesiones y garantiza el token local.
func Open(dir string, now func() time.Time) (*Store, error) {
	if now == nil {
		now = time.Now
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	s := &Store{dir: dir, now: now, sessions: map[string]Session{}, fails: map[string][]time.Time{}}
	var users collection[User]
	if err := store.ReadJSON(filepath.Join(dir, "users.json"), &users); err != nil && !errors.Is(err, store.ErrNotFound) {
		return nil, err
	}
	s.users = users.Items
	var sessions collection[Session]
	if err := store.ReadJSON(filepath.Join(dir, "sessions.json"), &sessions); err != nil && !errors.Is(err, store.ErrNotFound) {
		return nil, err
	}
	for _, sess := range sessions.Items {
		if sess.ExpiresAt.After(now()) {
			s.sessions[sess.Token] = sess
		}
	}
	tok, err := ensureLocalToken(filepath.Join(dir, "local-token"))
	if err != nil {
		return nil, err
	}
	s.localToken = tok
	return s, nil
}

func ensureLocalToken(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err == nil && len(strings.TrimSpace(string(data))) == 64 {
		return strings.TrimSpace(string(data)), nil
	}
	tok := randomHex(32)
	if err := os.WriteFile(path, []byte(tok+"\n"), 0o600); err != nil {
		return "", err
	}
	return tok, nil
}

func randomHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic("sin entropía: " + err.Error())
	}
	return hex.EncodeToString(b)
}

func normalizeEmail(e string) string { return strings.ToLower(strings.TrimSpace(e)) }

func (s *Store) persistUsers() error {
	return store.WriteJSON(filepath.Join(s.dir, "users.json"), collection[User]{SchemaVersion: 1, Items: s.users})
}

func (s *Store) persistSessions() error {
	items := make([]Session, 0, len(s.sessions))
	for _, sess := range s.sessions {
		items = append(items, sess)
	}
	return store.WriteJSON(filepath.Join(s.dir, "sessions.json"), collection[Session]{SchemaVersion: 1, Items: items})
}

// HasUsers indica si la instalación ya tiene un owner.
func (s *Store) HasUsers() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.users) > 0
}

// Setup crea el primer usuario como owner de la organización.
func (s *Store) Setup(email, name, password, orgID string) (User, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.users) > 0 {
		return User{}, ErrAlreadySetUp
	}
	email = normalizeEmail(email)
	if email == "" || !strings.Contains(email, "@") || strings.TrimSpace(name) == "" {
		return User{}, errors.New("email y nombre obligatorios")
	}
	hash, err := HashPassword(password)
	if err != nil {
		return User{}, err
	}
	u := User{ID: "usr_" + randomHex(8), Email: email, Name: strings.TrimSpace(name), PasswordHash: hash,
		OrgRoles: map[string]Role{orgID: Owner}, CreatedAt: s.now().UTC()}
	s.users = append(s.users, u)
	return u, s.persistUsers()
}

func (s *Store) throttled(email string) bool {
	cutoff := s.now().Add(-failWindow)
	var recent []time.Time
	for _, t := range s.fails[email] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	s.fails[email] = recent
	return len(recent) >= maxFails
}

// Login valida credenciales y abre una sesión.
func (s *Store) Login(email, password, orgID string) (Session, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	email = normalizeEmail(email)
	if s.throttled(email) {
		return Session{}, ErrThrottled
	}
	for _, u := range s.users {
		if u.Email == email && VerifyPassword(password, u.PasswordHash) {
			if _, ok := u.OrgRoles[orgID]; !ok {
				break
			}
			now := s.now().UTC()
			sess := Session{Token: randomHex(32), UserID: u.ID, OrgID: orgID, CSRF: randomHex(16), CreatedAt: now, ExpiresAt: now.Add(SessionTTL)}
			s.sessions[sess.Token] = sess
			return sess, s.persistSessions()
		}
	}
	s.fails[email] = append(s.fails[email], s.now())
	return Session{}, ErrInvalidCredentials
}

// Logout cierra la sesión.
func (s *Store) Logout(token string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.sessions, token)
	return s.persistSessions()
}

// Resolve devuelve el principal de una sesión vigente.
func (s *Store) Resolve(token string) (*Principal, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	sess, ok := s.sessions[token]
	if !ok {
		return nil, ErrUnauthenticated
	}
	if !sess.ExpiresAt.After(s.now()) {
		delete(s.sessions, token)
		_ = s.persistSessions()
		return nil, ErrUnauthenticated
	}
	u, ok := s.userByIDLocked(sess.UserID)
	if !ok {
		return nil, ErrUnauthenticated
	}
	return &Principal{UserID: u.ID, Email: u.Email, Name: u.Name, OrgID: sess.OrgID, Role: u.OrgRoles[sess.OrgID], Via: "session", CSRF: sess.CSRF}, nil
}

// LocalToken devuelve el token de CLI/MCP.
func (s *Store) LocalToken() string { return s.localToken }

// ResolveLocal acepta el token local como admin de la organización.
func (s *Store) ResolveLocal(token, orgID string) (*Principal, error) {
	if subtle.ConstantTimeCompare([]byte(token), []byte(s.localToken)) != 1 {
		return nil, ErrUnauthenticated
	}
	return &Principal{UserID: "local", Email: "local@lucidfence", Name: "Token local", OrgID: orgID, Role: Admin, Via: "local-token"}, nil
}

func (s *Store) userByIDLocked(id string) (User, bool) {
	for _, u := range s.users {
		if u.ID == id {
			return u, true
		}
	}
	return User{}, false
}

// UserByID busca un usuario.
func (s *Store) UserByID(id string) (User, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.userByIDLocked(id)
}

var _ = fmt.Sprintf
```

- [ ] **Step 6: Tests (pasan), lint, documentar, commit**

Run: `go test ./internal/auth/ -race -cover && golangci-lint run ./internal/auth/`
Expected: PASS ≥ 70 %. Si `unused` señala `var _ = fmt.Sprintf`, eliminar esa línea y el import.

`ARCHITECTURE.md`:
```
| `internal/auth` | Usuarios locales (argon2id), sesiones con CSRF y caducidad, token local para CLI/MCP, matriz de roles y capacidades. |
```

```bash
git add go.mod go.sum internal/auth ARCHITECTURE.md
git commit -q -m "feat(auth): usuarios argon2id, sesiones con CSRF, token local y matriz RBAC

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 10: Núcleo de la API (`internal/api`: respuestas, registro, middleware, servidor, health y auth)

**Files:**
- Create: `internal/api/respond.go`, `internal/api/registry.go`, `internal/api/middleware.go`, `internal/api/server.go`, `internal/api/handlers_health.go`, `internal/api/handlers_auth.go`
- Create: `internal/api/testutil_test.go`, `internal/api/registry_test.go`, `internal/api/server_test.go`, `internal/api/handlers_auth_test.go`
- Modify: `ARCHITECTURE.md`

**Interfaces:**
- Produces:
  ```go
  type HandlerFunc func(w http.ResponseWriter, r *http.Request, p *auth.Principal)
  type Route struct { Method string; Path string; Cap auth.Capability; Public bool; Handler HandlerFunc }
  type Registry struct{ ... }
  func NewRegistry() *Registry
  func (reg *Registry) Add(r Route)       // panic si Path no empieza por /api/v1/, si !Public && Cap == "", o si (Method, Path) se repite
  func (reg *Registry) Routes() []Route
  type Deps struct { Engine *engine.Engine; Org *store.OrgStore; Auth *auth.Store; Web http.Handler; WebBuilt bool; Config config.Config; Logger *slog.Logger; Now func() time.Time }
  func New(d Deps) (http.Handler, *Registry)
  const CookieName = "lf_session"; const CSRFHeader = "X-LucidFence-CSRF"
  // helpers internos: writeJSON(w, status, v), writeError(w, status, code, msg), writeErrorDetail(w, status, code, msg, detail), decodeJSON(r, v) error, queryInt(r, name, def, max) int
  ```
  Errores: `{"error": msg, "code": code, "detail": ...}` con códigos `unauthenticated` (401), `forbidden` (403), `csrf` (403), `not_found` (404), `invalid` (400), `conflict` (409), `throttled` (429), `cycle_in_progress` (409), `internal` (500).

- [ ] **Step 1: Test del registro (falla)**

`internal/api/registry_test.go`:
```go
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
```

- [ ] **Step 2: Implementar `respond.go` y `registry.go`**

`internal/api/respond.go`:
```go
// Package api monta la API HTTP /api/v1 (spec §6.1): un fichero por recurso,
// registro de rutas con capacidad obligatoria, errores con forma única y el
// dashboard embebido en /.
package api

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
)

type errorBody struct {
	Error  string `json:"error"`
	Code   string `json:"code"`
	Detail any    `json:"detail,omitempty"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, errorBody{Error: msg, Code: code})
}

func writeErrorDetail(w http.ResponseWriter, status int, code, msg string, detail any) {
	writeJSON(w, status, errorBody{Error: msg, Code: code, Detail: detail})
}

const maxBody = 1 << 20

var errBadJSON = errors.New("cuerpo JSON inválido")

// decodeJSON lee hasta 1 MiB, rechaza campos desconocidos.
func decodeJSON(r *http.Request, v any) error {
	dec := json.NewDecoder(io.LimitReader(r.Body, maxBody))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return fmt.Errorf("%w: %v", errBadJSON, err)
	}
	return nil
}

func queryInt(r *http.Request, name string, def, max int) int {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return def
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n < 1 {
		return def
	}
	if n > max {
		return max
	}
	return n
}
```

`internal/api/registry.go`:
```go
package api

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// HandlerFunc recibe el principal ya autenticado (nil en rutas públicas).
type HandlerFunc func(w http.ResponseWriter, r *http.Request, p *auth.Principal)

// Route es una ruta declarada con su capacidad.
type Route struct {
	Method  string
	Path    string
	Cap     auth.Capability
	Public  bool
	Handler HandlerFunc
}

// Registry es la tabla de rutas. Los invariantes se comprueban al registrar
// (arranque del proceso), nunca se descubren en producción.
type Registry struct {
	routes []Route
	seen   map[string]bool
}

// NewRegistry crea un registro vacío.
func NewRegistry() *Registry { return &Registry{seen: map[string]bool{}} }

// Add registra una ruta o hace panic si viola un invariante.
func (reg *Registry) Add(r Route) {
	if !strings.HasPrefix(r.Path, "/api/v1/") {
		panic(fmt.Sprintf("ruta %s fuera de /api/v1/", r.Path))
	}
	if !r.Public && r.Cap == "" {
		panic(fmt.Sprintf("ruta %s %s sin capacidad (spec §6.1)", r.Method, r.Path))
	}
	key := r.Method + " " + r.Path
	if reg.seen[key] {
		panic("ruta duplicada: " + key)
	}
	reg.seen[key] = true
	reg.routes = append(reg.routes, r)
}

// Routes devuelve una copia de las rutas.
func (reg *Registry) Routes() []Route { return append([]Route(nil), reg.routes...) }
```

Run: `go test ./internal/api/ -run TestRegistry -v` → PASS.

- [ ] **Step 3: Utilidades de test y tests del servidor (fallan)**

`internal/api/testutil_test.go`:
```go
package api

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
)

type testEnv struct {
	t      *testing.T
	srv    *httptest.Server
	auth   *auth.Store
	org    *store.OrgStore
	cookie *http.Cookie
	csrf   string
}

func newTestEnv(t *testing.T) *testEnv {
	t.Helper()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	clock := func() time.Time { return now }
	st, _ := store.Open(t.TempDir())
	org, _ := st.Org("default")
	as, err := auth.Open(st.AuthDir(), clock)
	if err != nil {
		t.Fatal(err)
	}
	eng := engine.New(org, []uem.Adapter{simulation.New(simulation.DefaultSeed(), clock)}, engine.Options{Mode: "simulation", Interval: time.Hour, Now: clock})
	h, _ := New(Deps{Engine: eng, Org: org, Auth: as, Web: http.NotFoundHandler(), Config: config.Default(), Now: clock})
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	return &testEnv{t: t, srv: srv, auth: as, org: org}
}

func (e *testEnv) do(method, path string, body any, authed bool) (*http.Response, map[string]any) {
	e.t.Helper()
	var buf bytes.Buffer
	if body != nil {
		_ = json.NewEncoder(&buf).Encode(body)
	}
	req, _ := http.NewRequest(method, e.srv.URL+path, &buf)
	req.Header.Set("Content-Type", "application/json")
	if authed && e.cookie != nil {
		req.AddCookie(e.cookie)
		req.Header.Set(CSRFHeader, e.csrf)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	res.Body.Close()
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	return res, out
}

func (e *testEnv) setup(mode string) map[string]any {
	e.t.Helper()
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "adri@example.com", "name": "Adri", "password": "contraseña-larga-1", "mode": mode}, false)
	if res.StatusCode != 201 {
		e.t.Fatalf("setup: %d %v", res.StatusCode, out)
	}
	for _, c := range res.Cookies() {
		if c.Name == CookieName {
			e.cookie = c
		}
	}
	e.csrf, _ = out["csrf"].(string)
	if e.cookie == nil || e.csrf == "" {
		e.t.Fatalf("setup sin cookie/csrf: %v", out)
	}
	return out
}
```

`internal/api/server_test.go`:
```go
package api

import "testing"

func TestHealthEsPublicoYNoFiltraSecretos(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("GET", "/api/v1/health", nil, false)
	if res.StatusCode != 200 || out["status"] != "ok" || out["setup_required"] != true || out["mode"] != "simulation" || out["enforcement"] != "observe" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	if _, has := out["local_token"]; has {
		t.Fatal("health nunca expone secretos")
	}
	if res.Header.Get("X-Content-Type-Options") != "nosniff" || res.Header.Get("X-Request-ID") == "" {
		t.Fatal("cabeceras de seguridad y request id")
	}
	res, out = e.do("GET", "/api/v1/readyz", nil, false)
	if res.StatusCode != 200 || out["ready"] != true {
		t.Fatalf("readyz: %d %v", res.StatusCode, out)
	}
}

func TestRutaProtegidaSinSesion401YDesconocida404(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("GET", "/api/v1/devices", nil, false)
	if res.StatusCode != 401 || out["code"] != "unauthenticated" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/nada", nil, false)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
}

func TestTokenLocalPorBearerDesdeLoopback(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	req, _ := newRequest(e, "GET", "/api/v1/auth/me")
	req.Header.Set("Authorization", "Bearer "+e.auth.LocalToken())
	res, out := send(e, req)
	if res.StatusCode != 200 || out["user"].(map[string]any)["via"] != "local-token" || out["user"].(map[string]any)["role"] != "admin" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	req, _ = newRequest(e, "GET", "/api/v1/auth/me")
	req.Header.Set("Authorization", "Bearer incorrecto")
	if res, _ := send(e, req); res.StatusCode != 401 {
		t.Fatal("bearer incorrecto → 401")
	}
}
```

Añadir a `testutil_test.go`:
```go
func newRequest(e *testEnv, method, path string) (*http.Request, error) {
	return http.NewRequest(method, e.srv.URL+path, nil)
}

func send(e *testEnv, req *http.Request) (*http.Response, map[string]any) {
	e.t.Helper()
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		e.t.Fatal(err)
	}
	raw, _ := io.ReadAll(res.Body)
	res.Body.Close()
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	return res, out
}
```

`internal/api/handlers_auth_test.go`:
```go
package api

import "testing"

func TestSetupLoginMeLogout(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("GET", "/api/v1/auth/status", nil, false)
	if res.StatusCode != 200 || out["setup_required"] != true {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	out = e.setup("demo")
	user := out["user"].(map[string]any)
	if user["role"] != "owner" || user["email"] != "adri@example.com" || user["org"] != "default" {
		t.Fatalf("user: %v", user)
	}
	if _, has := user["password_hash"]; has {
		t.Fatal("nunca se devuelve el hash")
	}
	fs, _ := e.org.Fences()
	if len(fs) != 2 {
		t.Fatal("modo demo siembra geocercas")
	}
	res, out = e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "x@x.com", "name": "X", "password": "contraseña-larga-1", "mode": "empty"}, false)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("segundo setup: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/auth/me", nil, true)
	if res.StatusCode != 200 || out["user"].(map[string]any)["via"] != "session" || len(out["capabilities"].([]any)) == 0 {
		t.Fatalf("me: %d %v", res.StatusCode, out)
	}
	res, out = e.do("POST", "/api/v1/auth/login", map[string]any{"email": "adri@example.com", "password": "mal"}, false)
	if res.StatusCode != 401 || out["code"] != "invalid_credentials" {
		t.Fatalf("login mal: %d %v", res.StatusCode, out)
	}
	res, _ = e.do("POST", "/api/v1/auth/login", map[string]any{"email": "adri@example.com", "password": "contraseña-larga-1"}, false)
	if res.StatusCode != 200 {
		t.Fatalf("login: %d", res.StatusCode)
	}
	res, _ = e.do("POST", "/api/v1/auth/logout", nil, true)
	if res.StatusCode != 204 {
		t.Fatalf("logout: %d", res.StatusCode)
	}
	res, _ = e.do("GET", "/api/v1/auth/me", nil, true)
	if res.StatusCode != 401 {
		t.Fatal("tras logout la cookie no vale")
	}
}

func TestSetupValidaYCSRF(t *testing.T) {
	e := newTestEnv(t)
	res, out := e.do("POST", "/api/v1/auth/setup", map[string]any{"email": "sin-arroba", "name": "", "password": "corta", "mode": "demo"}, false)
	if res.StatusCode != 400 || out["code"] != "invalid" {
		t.Fatalf("%d %v", res.StatusCode, out)
	}
	e.setup("empty")
	req, _ := newRequest(e, "POST", "/api/v1/auth/logout")
	req.AddCookie(e.cookie)
	if res, out := send(e, req); res.StatusCode != 403 || out["code"] != "csrf" {
		t.Fatalf("mutación con cookie sin cabecera CSRF: %d %v", res.StatusCode, out)
	}
}
```

- [ ] **Step 4: Implementar `middleware.go`, `server.go`, `handlers_health.go`, `handlers_auth.go`**

`internal/api/middleware.go`:
```go
package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"net"
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// CookieName es la cookie de sesión del dashboard.
const CookieName = "lf_session"

// CSRFHeader es la cabecera obligatoria en mutaciones con cookie.
const CSRFHeader = "X-LucidFence-CSRF"

func requestID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func isLoopback(remoteAddr string) bool {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func (s *server) authenticate(r *http.Request) (*auth.Principal, error) {
	if c, err := r.Cookie(CookieName); err == nil && c.Value != "" {
		return s.d.Auth.Resolve(c.Value)
	}
	if h := r.Header.Get("Authorization"); strings.HasPrefix(h, "Bearer ") && isLoopback(r.RemoteAddr) {
		return s.d.Auth.ResolveLocal(strings.TrimPrefix(h, "Bearer "), s.d.Config.Org)
	}
	return nil, auth.ErrUnauthenticated
}

func mutating(method string) bool {
	return method != http.MethodGet && method != http.MethodHead && method != http.MethodOptions
}

func (s *server) wrap(rt Route) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				s.d.Logger.Error("panic en handler", "path", r.URL.Path, "panic", rec, "request_id", w.Header().Get("X-Request-ID"))
				writeError(w, http.StatusInternalServerError, "internal", "error interno")
			}
		}()
		var p *auth.Principal
		if !rt.Public {
			var err error
			p, err = s.authenticate(r)
			if err != nil {
				if errors.Is(err, auth.ErrUnauthenticated) {
					writeError(w, http.StatusUnauthorized, "unauthenticated", "inicia sesión")
					return
				}
				writeError(w, http.StatusInternalServerError, "internal", "error de autenticación")
				return
			}
			if !auth.Can(p.Role, rt.Cap) {
				writeError(w, http.StatusForbidden, "forbidden", "sin permiso")
				return
			}
			if p.Via == "session" && mutating(r.Method) && r.Header.Get(CSRFHeader) != p.CSRF {
				writeError(w, http.StatusForbidden, "csrf", "falta o no coincide la cabecera "+CSRFHeader)
				return
			}
		}
		rt.Handler(w, r, p)
	})
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("X-Request-ID", requestID())
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "no-referrer")
		h.Set("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob: https:; connect-src 'self' https:; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'")
		next.ServeHTTP(w, r)
	})
}

type ctxKey int

const principalKey ctxKey = 1

func withPrincipal(ctx context.Context, p *auth.Principal) context.Context {
	return context.WithValue(ctx, principalKey, p)
}
```

`internal/api/server.go`:
```go
package api

import (
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
)

// Deps son las dependencias del servidor.
type Deps struct {
	Engine   *engine.Engine
	Org      *store.OrgStore
	Auth     *auth.Store
	Web      http.Handler
	WebBuilt bool
	Config   config.Config
	Logger   *slog.Logger
	Now      func() time.Time
}

type server struct {
	d   Deps
	reg *Registry
}

// New construye el handler raíz: /api/v1/* con auth y capacidades, / el dashboard.
func New(d Deps) (http.Handler, *Registry) {
	if d.Logger == nil {
		d.Logger = slog.Default()
	}
	if d.Now == nil {
		d.Now = time.Now
	}
	s := &server{d: d, reg: NewRegistry()}
	s.registerHealth()
	s.registerAuth()
	s.registerDevices()
	s.registerFences()
	s.registerRoutes()
	s.registerPOIs()
	s.registerEngine()
	mux := http.NewServeMux()
	for _, rt := range s.reg.Routes() {
		mux.Handle(rt.Method+" "+rt.Path, s.wrap(rt))
	}
	mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) {
		writeError(w, http.StatusNotFound, "not_found", "ruta no encontrada")
	})
	mux.Handle("/", d.Web)
	return securityHeaders(mux), s.reg
}

func (s *server) org() *store.OrgStore { return s.d.Org }

func pathID(r *http.Request) string { return strings.TrimSpace(r.PathValue("id")) }
```

`internal/api/handlers_health.go`:
```go
package api

import (
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/version"
)

func (s *server) registerHealth() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/health", Public: true, Handler: s.health})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/readyz", Public: true, Handler: s.readyz})
}

func (s *server) health(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	st := s.d.Engine.Status()
	var lastAt *time.Time
	if st.LastCycle != nil {
		lastAt = &st.LastCycle.At
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok", "version": version.Version, "mode": st.Mode, "enforcement": st.Enforcement, "web_built": s.d.WebBuilt,
		"setup_required": !s.d.Auth.HasUsers(),
		"engine":         map[string]any{"running": st.Running, "cycles": st.Cycles, "last_cycle_at": lastAt, "interval_seconds": st.IntervalSeconds},
		"map":            map[string]any{"enabled": s.d.Config.Map.Enabled, "tiles_url": s.d.Config.Map.TilesURL},
	})
}

func (s *server) readyz(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	probe := filepath.Join(s.org().Dir(), ".ready-probe")
	if err := os.WriteFile(probe, []byte("ok"), 0o600); err != nil {
		writeErrorDetail(w, http.StatusServiceUnavailable, "not_ready", "el directorio de datos no es escribible", err.Error())
		return
	}
	_ = os.Remove(probe)
	writeJSON(w, http.StatusOK, map[string]any{"ready": true})
}
```

`internal/api/handlers_auth.go`:
```go
package api

import (
	"errors"
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

func (s *server) registerAuth() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/auth/status", Public: true, Handler: s.authStatus})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/auth/setup", Public: true, Handler: s.authSetup})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/auth/login", Public: true, Handler: s.authLogin})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/auth/logout", Cap: auth.OrgRead, Handler: s.authLogout})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/auth/me", Cap: auth.OrgRead, Handler: s.authMe})
}

type setupBody struct {
	Email    string `json:"email"`
	Name     string `json:"name"`
	Password string `json:"password"`
	Mode     string `json:"mode"`
}

type loginBody struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func userView(p *auth.Principal) map[string]any {
	return map[string]any{"id": p.UserID, "email": p.Email, "name": p.Name, "org": p.OrgID, "role": p.Role, "via": p.Via}
}

func (s *server) setCookie(w http.ResponseWriter, r *http.Request, token string, maxAge int) {
	http.SetCookie(w, &http.Cookie{Name: CookieName, Value: token, Path: "/", HttpOnly: true, Secure: r.TLS != nil,
		SameSite: http.SameSiteStrictMode, MaxAge: maxAge})
}

func (s *server) authStatus(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	writeJSON(w, http.StatusOK, map[string]any{"setup_required": !s.d.Auth.HasUsers()})
}

func (s *server) authSetup(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	var b setupBody
	if err := decodeJSON(r, &b); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if b.Mode != "demo" && b.Mode != "empty" {
		writeError(w, http.StatusBadRequest, "invalid", "mode debe ser demo o empty")
		return
	}
	if _, err := s.d.Auth.Setup(b.Email, b.Name, b.Password, s.d.Config.Org); err != nil {
		switch {
		case errors.Is(err, auth.ErrAlreadySetUp):
			writeError(w, http.StatusConflict, "conflict", err.Error())
		default:
			writeError(w, http.StatusBadRequest, "invalid", err.Error())
		}
		return
	}
	if b.Mode == "demo" {
		if err := engine.SeedDemo(s.org(), s.d.Now()); err != nil {
			writeError(w, http.StatusInternalServerError, "internal", "no se pudieron escribir los datos demo: "+err.Error())
			return
		}
	}
	s.openSession(w, r, b.Email, b.Password, http.StatusCreated)
}

func (s *server) authLogin(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	var b loginBody
	if err := decodeJSON(r, &b); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	s.openSession(w, r, b.Email, b.Password, http.StatusOK)
}

func (s *server) openSession(w http.ResponseWriter, r *http.Request, email, password string, status int) {
	sess, err := s.d.Auth.Login(email, password, s.d.Config.Org)
	switch {
	case errors.Is(err, auth.ErrThrottled):
		writeError(w, http.StatusTooManyRequests, "throttled", err.Error())
		return
	case err != nil:
		writeError(w, http.StatusUnauthorized, "invalid_credentials", "email o contraseña incorrectos")
		return
	}
	p, err := s.d.Auth.Resolve(sess.Token)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", "sesión no resoluble")
		return
	}
	s.setCookie(w, r, sess.Token, int(auth.SessionTTL.Seconds()))
	writeJSON(w, status, map[string]any{"user": userView(p), "csrf": sess.CSRF, "capabilities": auth.Capabilities(p.Role)})
}

func (s *server) authLogout(w http.ResponseWriter, r *http.Request, p *auth.Principal) {
	if c, err := r.Cookie(CookieName); err == nil {
		_ = s.d.Auth.Logout(c.Value)
	}
	s.setCookie(w, r, "", -1)
	_ = p
	w.WriteHeader(http.StatusNoContent)
}

func (s *server) authMe(w http.ResponseWriter, _ *http.Request, p *auth.Principal) {
	writeJSON(w, http.StatusOK, map[string]any{"user": userView(p), "csrf": p.CSRF, "capabilities": auth.Capabilities(p.Role)})
}

var _ = strings.TrimSpace
```

Los métodos `registerDevices`, `registerFences`, `registerRoutes`, `registerPOIs` y `registerEngine` se implementan en la Task 11; para compilar esta tarea, crear temporalmente `internal/api/handlers_stub.go`:
```go
package api

func (s *server) registerDevices() {}
func (s *server) registerFences()  {}
func (s *server) registerRoutes()  {}
func (s *server) registerPOIs()    {}
func (s *server) registerEngine()  {}
```
El test `TestRutaProtegidaSinSesion401YDesconocida404` espera 401 en `/api/v1/devices`: hasta la Task 11 devolverá 404. Ejecutar ese test con `-run 'TestHealth|TestSetup|TestTokenLocal'` en esta tarea y el completo en la siguiente.

- [ ] **Step 5: Tests (pasan), commit**

Run: `go test ./internal/api/ -run 'TestRegistry|TestHealth|TestSetup|TestTokenLocal' -race -v`
Expected: PASS. Si `unused` se queja de `withPrincipal`/`principalKey` o de `var _ = strings.TrimSpace`, eliminarlos.

`ARCHITECTURE.md`:
```
| `internal/api` | API HTTP `/api/v1`: registro con capacidad obligatoria, auth por cookie/bearer local, CSRF, errores uniformes, dashboard en `/`. |
```

```bash
git add internal/api ARCHITECTURE.md
git commit -q -m "feat(api): núcleo HTTP con registro de rutas, auth, CSRF, health y setup

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 11: Recursos de la API (dispositivos, geocercas, rutas, POIs, motor, eventos, acciones)

**Files:**
- Create: `internal/api/crud.go`, `internal/api/handlers_devices.go`, `internal/api/handlers_fences.go`, `internal/api/handlers_routes.go`, `internal/api/handlers_pois.go`, `internal/api/handlers_engine.go`
- Create: `internal/api/handlers_devices_test.go`, `internal/api/handlers_fences_test.go`, `internal/api/handlers_engine_test.go`
- Delete: `internal/api/handlers_stub.go`

**Interfaces:**
- Produces (rutas; cap entre paréntesis):
  - `GET /api/v1/devices?state=&q=` (device:read) → `{items: Device[], total}`; `GET /api/v1/devices/{id}` (device:read) → Device; `GET /api/v1/devices/{id}/trail?limit=` (device:read) → `{items: TrailPoint[]}`
  - `GET /api/v1/fences` (fence:read) → `{items}`; `POST` (fence:write) 201; `GET /api/v1/fences/{id}` (fence:read); `PUT` (fence:write); `DELETE` (fence:delete) 204
  - `GET/POST /api/v1/routes`, `GET/PUT/DELETE /api/v1/routes/{id}` (route:read / route:write / route:delete)
  - `GET/POST /api/v1/pois`, `GET/PUT/DELETE /api/v1/pois/{id}` (fence:read / fence:write / fence:delete); `GET /api/v1/pois/geojson` (fence:read)
  - `GET /api/v1/engine/status` (device:read) → engine.Status; `POST /api/v1/engine/run-once` (engine:run) → CycleStats o 409 `cycle_in_progress`
  - `GET /api/v1/events?limit=` (device:read) → `{items: Transition[]}`; `GET /api/v1/actions?limit=` (device:read) → `{items: ActionResult[]}`
- Produces (interno): `crud[T]` genérico con `list`, `get`, `create`, `update`, `remove`.

- [ ] **Step 1: Tests (fallan)**

`internal/api/handlers_devices_test.go`:
```go
package api

import "testing"

func TestDevicesListaDetalleYTrail(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	res, out := e.do("POST", "/api/v1/engine/run-once", nil, true)
	if res.StatusCode != 200 || out["devices_total"].(float64) != 6 {
		t.Fatalf("run-once: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/devices", nil, true)
	if res.StatusCode != 200 || out["total"].(float64) != 6 || len(out["items"].([]any)) != 6 {
		t.Fatalf("lista: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/devices?state=inside", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || len(items) == 0 || items[0].(map[string]any)["fence_state"] != "inside" {
		t.Fatalf("filtro inside: %v", out)
	}
	res, out = e.do("GET", "/api/v1/devices?q=recep", nil, true)
	if len(out["items"].([]any)) != 1 {
		t.Fatalf("búsqueda por nombre: %v", out)
	}
	res, out = e.do("GET", "/api/v1/devices/dev-001", nil, true)
	if res.StatusCode != 200 || out["id"] != "dev-001" || out["inside_fence"] != "demo-hq" || out["inventory"].(map[string]any)["model"] == "" {
		t.Fatalf("detalle: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/devices/nope", nil, true)
	if res.StatusCode != 404 || out["code"] != "not_found" {
		t.Fatalf("404: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/devices/dev-001/trail?limit=5", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 1 {
		t.Fatalf("trail: %d %v", res.StatusCode, out)
	}
}
```

`internal/api/handlers_fences_test.go`:
```go
package api

import "testing"

func TestFencesCRUDYValidacion(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	body := map[string]any{"id": "hq", "name": "HQ", "kind": "circle", "center": map[string]float64{"lat": 40.42, "lng": -3.71}, "radius_m": 300,
		"actions": []map[string]any{{"action": "message", "when": "on_enter", "enabled": true, "params": map[string]any{"text": "hola"}}}}
	res, out := e.do("POST", "/api/v1/fences", body, true)
	if res.StatusCode != 201 || out["id"] != "hq" || out["created_at"] == "" {
		t.Fatalf("create: %d %v", res.StatusCode, out)
	}
	res, out = e.do("POST", "/api/v1/fences", body, true)
	if res.StatusCode != 409 || out["code"] != "conflict" {
		t.Fatalf("duplicado: %d %v", res.StatusCode, out)
	}
	bad := map[string]any{"id": "HQ 2", "name": "", "kind": "circle", "radius_m": 0}
	res, out = e.do("POST", "/api/v1/fences", bad, true)
	if res.StatusCode != 400 || out["code"] != "invalid" || out["error"] == "" {
		t.Fatalf("inválida: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/fences", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 1 {
		t.Fatalf("lista: %v", out)
	}
	body["name"] = "HQ renombrada"
	res, out = e.do("PUT", "/api/v1/fences/hq", body, true)
	if res.StatusCode != 200 || out["name"] != "HQ renombrada" {
		t.Fatalf("update: %d %v", res.StatusCode, out)
	}
	res, out = e.do("PUT", "/api/v1/fences/otra", body, true)
	if res.StatusCode != 404 {
		t.Fatalf("update inexistente: %d %v", res.StatusCode, out)
	}
	res, _ = e.do("DELETE", "/api/v1/fences/hq", nil, true)
	if res.StatusCode != 204 {
		t.Fatalf("delete: %d", res.StatusCode)
	}
	res, _ = e.do("GET", "/api/v1/fences/hq", nil, true)
	if res.StatusCode != 404 {
		t.Fatal("borrada")
	}
	res, out = e.do("POST", "/api/v1/routes", map[string]any{"id": "r1", "name": "R", "corridor_m": 100, "waypoints": []map[string]float64{{"lat": 40.42, "lng": -3.7}, {"lat": 40.43, "lng": -3.7}}, "device_ids": []string{"dev-001"}}, true)
	if res.StatusCode != 201 {
		t.Fatalf("route: %d %v", res.StatusCode, out)
	}
	res, out = e.do("POST", "/api/v1/pois", map[string]any{"id": "p1", "name": "P", "category": "school", "point": map[string]float64{"lat": 40.42, "lng": -3.7}}, true)
	if res.StatusCode != 201 {
		t.Fatalf("poi: %d %v", res.StatusCode, out)
	}
	res, out = e.do("GET", "/api/v1/pois/geojson", nil, true)
	if res.StatusCode != 200 || out["type"] != "FeatureCollection" {
		t.Fatalf("geojson: %v", out)
	}
}

func TestFencesRequierenPermisoYCSRF(t *testing.T) {
	e := newTestEnv(t)
	e.setup("empty")
	req, _ := newRequest(e, "POST", "/api/v1/fences")
	req.AddCookie(e.cookie)
	if res, out := send(e, req); res.StatusCode != 403 || out["code"] != "csrf" {
		t.Fatalf("sin CSRF: %d %v", res.StatusCode, out)
	}
}
```

`internal/api/handlers_engine_test.go`:
```go
package api

import "testing"

func TestEngineStatusEventosYAcciones(t *testing.T) {
	e := newTestEnv(t)
	e.setup("demo")
	res, out := e.do("GET", "/api/v1/engine/status", nil, true)
	if res.StatusCode != 200 || out["enforcement"] != "observe" || out["cycles"].(float64) != 0 {
		t.Fatalf("status: %d %v", res.StatusCode, out)
	}
	if res, _ := e.do("POST", "/api/v1/engine/run-once", nil, true); res.StatusCode != 200 {
		t.Fatal("run-once")
	}
	res, out = e.do("GET", "/api/v1/events?limit=3", nil, true)
	if res.StatusCode != 200 || len(out["items"].([]any)) != 3 {
		t.Fatalf("events: %v", out)
	}
	res, out = e.do("GET", "/api/v1/actions", nil, true)
	items := out["items"].([]any)
	if res.StatusCode != 200 || len(items) == 0 || items[0].(map[string]any)["dry_run"] != true {
		t.Fatalf("actions: %v", out)
	}
}
```

- [ ] **Step 2: Implementar `crud.go`**

```go
package api

import (
	"errors"
	"net/http"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// crud monta GET/POST /coleccion y GET/PUT/DELETE /coleccion/{id} sobre una
// colección JSON del store. T debe serializar snake_case.
type crud[T any] struct {
	path      string
	readCap   auth.Capability
	writeCap  auth.Capability
	deleteCap auth.Capability
	load      func() ([]T, error)
	save      func([]T) error
	id        func(T) string
	stamp     func(*T, time.Time, bool)
	validate  func([]T) error
}

var errConflict = errors.New("ya existe")

func (c crud[T]) register(s *server) {
	s.reg.Add(Route{Method: "GET", Path: c.path, Cap: c.readCap, Handler: c.list})
	s.reg.Add(Route{Method: "POST", Path: c.path, Cap: c.writeCap, Handler: s.withNow(c.create)})
	s.reg.Add(Route{Method: "GET", Path: c.path + "/{id}", Cap: c.readCap, Handler: c.get})
	s.reg.Add(Route{Method: "PUT", Path: c.path + "/{id}", Cap: c.writeCap, Handler: s.withNow(c.update)})
	s.reg.Add(Route{Method: "DELETE", Path: c.path + "/{id}", Cap: c.deleteCap, Handler: c.remove})
}

type nowHandler func(w http.ResponseWriter, r *http.Request, now time.Time)

func (s *server) withNow(h nowHandler) HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request, _ *auth.Principal) { h(w, r, s.d.Now().UTC()) }
}

func (c crud[T]) list(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": items, "total": len(items)})
}

func (c crud[T]) find(items []T, id string) int {
	for i, it := range items {
		if c.id(it) == id {
			return i
		}
	}
	return -1
}

func (c crud[T]) get(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	writeJSON(w, http.StatusOK, items[i])
}

func (c crud[T]) create(w http.ResponseWriter, r *http.Request, now time.Time) {
	var item T
	if err := decodeJSON(r, &item); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	if c.find(items, c.id(item)) >= 0 {
		writeError(w, http.StatusConflict, "conflict", errConflict.Error())
		return
	}
	c.stamp(&item, now, true)
	items = append(items, item)
	if err := c.validate(items); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := c.save(items); err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, item)
}

func (c crud[T]) update(w http.ResponseWriter, r *http.Request, now time.Time) {
	var item T
	if err := decodeJSON(r, &item); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	if c.id(item) != pathID(r) {
		writeError(w, http.StatusBadRequest, "invalid", "el id del cuerpo no coincide con la ruta")
		return
	}
	c.stamp(&item, now, false)
	items[i] = item
	if err := c.validate(items); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := c.save(items); err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, item)
}

func (c crud[T]) remove(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	items, err := c.load()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	i := c.find(items, pathID(r))
	if i < 0 {
		writeError(w, http.StatusNotFound, "not_found", "no existe")
		return
	}
	items = append(items[:i], items[i+1:]...)
	if err := c.save(items); err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
```

- [ ] **Step 3: Implementar los ficheros de recurso**

`internal/api/handlers_fences.go`:
```go
package api

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
)

func (s *server) registerFences() {
	crud[fence.Fence]{
		path: "/api/v1/fences", readCap: auth.FenceRead, writeCap: auth.FenceWrite, deleteCap: auth.FenceDelete,
		load: s.org().Fences, save: s.org().SaveFences,
		id: func(f fence.Fence) string { return f.ID },
		stamp: func(f *fence.Fence, now time.Time, created bool) {
			if created {
				f.CreatedAt = now
			}
			f.UpdatedAt = now
			if f.Actions == nil {
				f.Actions = []fence.Action{}
			}
		},
		validate: fence.ValidateAll,
	}.register(s)
}
```

`internal/api/handlers_routes.go`:
```go
package api

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/fence"
	"github.com/adrimg3196/lucidfence/internal/domain/route"
)

func (s *server) registerRoutes() {
	crud[route.Route]{
		path: "/api/v1/routes", readCap: auth.RouteRead, writeCap: auth.RouteWrite, deleteCap: auth.RouteDelete,
		load: s.org().Routes, save: s.org().SaveRoutes,
		id: func(r route.Route) string { return r.ID },
		stamp: func(r *route.Route, now time.Time, created bool) {
			if created {
				r.CreatedAt = now
			}
			r.UpdatedAt = now
			if r.Actions == nil {
				r.Actions = []fence.Action{}
			}
			if r.DeviceIDs == nil {
				r.DeviceIDs = []string{}
			}
		},
		validate: route.ValidateAll,
	}.register(s)
}
```

`internal/api/handlers_pois.go`:
```go
package api

import (
	"net/http"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/poi"
)

func (s *server) registerPOIs() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/pois/geojson", Cap: auth.FenceRead, Handler: s.poisGeoJSON})
	crud[poi.POI]{
		path: "/api/v1/pois", readCap: auth.FenceRead, writeCap: auth.FenceWrite, deleteCap: auth.FenceDelete,
		load: s.org().POIs, save: s.org().SavePOIs,
		id:       func(p poi.POI) string { return p.ID },
		stamp:    func(*poi.POI, time.Time, bool) {},
		validate: poi.ValidateAll,
	}.register(s)
}

func (s *server) poisGeoJSON(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	ps, err := s.org().POIs()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, poi.ToGeoJSON(ps))
}
```

Nota: `GET /api/v1/pois/geojson` se registra antes que `GET /api/v1/pois/{id}`; con `net/http` el patrón literal gana sobre el comodín, así que el orden no importa, pero se deja explícito.

`internal/api/handlers_devices.go`:
```go
package api

import (
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

func (s *server) registerDevices() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices", Cap: auth.DeviceRead, Handler: s.devicesList})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices/{id}", Cap: auth.DeviceRead, Handler: s.deviceGet})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/devices/{id}/trail", Cap: auth.DeviceRead, Handler: s.deviceTrail})
}

func matchDevice(d device.Device, state, q string) bool {
	if state != "" && string(d.FenceState) != state {
		return false
	}
	if q == "" {
		return true
	}
	q = strings.ToLower(q)
	for _, field := range []string{d.ID, d.Name, d.Platform, d.Inventory.AssignedUser, d.Inventory.Department, d.Inventory.Model, d.Inventory.SerialNumber} {
		if strings.Contains(strings.ToLower(field), q) {
			return true
		}
	}
	return false
}

func (s *server) devicesList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	ds, err := s.org().Devices()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	state, q := r.URL.Query().Get("state"), r.URL.Query().Get("q")
	out := make([]device.Device, 0, len(ds))
	for _, d := range ds {
		if matchDevice(d, state, q) {
			out = append(out, d)
		}
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": out, "total": len(out)})
}

func (s *server) deviceGet(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	ds, err := s.org().Devices()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	if d, ok := device.Index(ds)[pathID(r)]; ok {
		writeJSON(w, http.StatusOK, d)
		return
	}
	writeError(w, http.StatusNotFound, "not_found", "dispositivo no encontrado")
}

func (s *server) deviceTrail(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	tr, err := s.org().Trail(pathID(r), queryInt(r, "limit", 200, 2000))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": tr})
}
```

`internal/api/handlers_engine.go`:
```go
package api

import (
	"errors"
	"net/http"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

func (s *server) registerEngine() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/engine/status", Cap: auth.DeviceRead, Handler: s.engineStatus})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/engine/run-once", Cap: auth.EngineRun, Handler: s.engineRunOnce})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/events", Cap: auth.DeviceRead, Handler: s.eventsList})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/actions", Cap: auth.DeviceRead, Handler: s.actionsList})
}

func (s *server) engineStatus(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	writeJSON(w, http.StatusOK, s.d.Engine.Status())
}

func (s *server) engineRunOnce(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	st, err := s.d.Engine.RunOnce(r.Context())
	switch {
	case errors.Is(err, engine.ErrCycleInProgress):
		writeError(w, http.StatusConflict, "cycle_in_progress", err.Error())
	case err != nil:
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
	default:
		writeJSON(w, http.StatusOK, st)
	}
}

func (s *server) eventsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	evs, err := s.org().RecentEvents(queryInt(r, "limit", 100, 1000))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": evs})
}

func (s *server) actionsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	acts, err := s.org().RecentActions(queryInt(r, "limit", 100, 1000))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": acts})
}
```

- [ ] **Step 4: Borrar el stub, tests completos, lint, commit**

```bash
rm internal/api/handlers_stub.go
go test ./internal/api/ -race -cover -v
golangci-lint run ./internal/api/
```

Expected: todos los tests PASS (incluido `TestRutaProtegidaSinSesion401YDesconocida404`), cobertura ≥ 70 %.

```bash
git add internal/api
git commit -q -m "feat(api): dispositivos, geocercas, rutas, POIs, motor, eventos y acciones

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 12: Contrato OpenAPI y test de paridad

**Files:**
- Create: `docs/openapi.yaml`, `internal/api/openapi_test.go`

**Interfaces:**
- Produces: `docs/openapi.yaml` en estilo restringido (2 espacios; `paths:` en columna 0; cada ruta en columna 2; cada método en columna 4; `x-capability:` en columna 6 con valor `public` o la capacidad). El test lo parsea línea a línea (la stdlib no tiene YAML) y exige igualdad exacta con el registro. `openapi-typescript` (Task 16) genera los tipos del frontend desde este fichero.

- [ ] **Step 1: Test de paridad (falla)**

`internal/api/openapi_test.go`:
```go
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
	defer f.Close()
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
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `go test ./internal/api/ -run TestRutasYOpenAPICoinciden`
Expected: FAIL `docs/openapi.yaml obligatorio`.

- [ ] **Step 3: Escribir `docs/openapi.yaml`**

```yaml
# Contrato de la API de LucidFence 2.0. Estilo restringido: 2 espacios de
# indentación, rutas en columna 2, métodos en columna 4 y x-capability en
# columna 6. internal/api/openapi_test.go exige paridad con el registro;
# web/ genera sus tipos desde aquí (npm run gen:api).
openapi: 3.1.0
info:
  title: LucidFence API
  version: 2.0.0-dev
  description: Geofencing multi-UEM local-first. Toda ruta declara x-capability (public o la capacidad RBAC exigida).
servers:
  - url: http://127.0.0.1:8765
paths:
  /api/v1/health:
    get:
      x-capability: public
      summary: Estado del servicio, sin secretos
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Health"
  /api/v1/readyz:
    get:
      x-capability: public
      summary: Disponibilidad (directorio de datos escribible)
      responses:
        "200":
          description: Listo
          content:
            application/json:
              schema:
                type: object
                properties:
                  ready:
                    type: boolean
                required: [ready]
        "503":
          $ref: "#/components/responses/Error"
  /api/v1/auth/status:
    get:
      x-capability: public
      summary: Indica si falta el asistente inicial
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  setup_required:
                    type: boolean
                required: [setup_required]
  /api/v1/auth/setup:
    post:
      x-capability: public
      summary: Crea el owner (solo si no hay usuarios) y abre sesión
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SetupRequest"
      responses:
        "201":
          description: Sesión abierta
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SessionResponse"
        "400":
          $ref: "#/components/responses/Error"
        "409":
          $ref: "#/components/responses/Error"
  /api/v1/auth/login:
    post:
      x-capability: public
      summary: Abre sesión con cookie
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/LoginRequest"
      responses:
        "200":
          description: Sesión abierta
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SessionResponse"
        "401":
          $ref: "#/components/responses/Error"
        "429":
          $ref: "#/components/responses/Error"
  /api/v1/auth/logout:
    post:
      x-capability: org:read
      summary: Cierra la sesión
      responses:
        "204":
          description: Cerrada
  /api/v1/auth/me:
    get:
      x-capability: org:read
      summary: Usuario, org, rol, csrf y capacidades
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SessionResponse"
  /api/v1/devices:
    get:
      x-capability: device:read
      summary: Lista de dispositivos
      parameters:
        - name: state
          in: query
          schema:
            type: string
            enum: [inside, outside, unknown]
        - name: q
          in: query
          schema:
            type: string
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/DeviceList"
  /api/v1/devices/{id}:
    get:
      x-capability: device:read
      summary: Detalle de dispositivo
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Device"
        "404":
          $ref: "#/components/responses/Error"
  /api/v1/devices/{id}/trail:
    get:
      x-capability: device:read
      summary: Últimas posiciones
      parameters:
        - $ref: "#/components/parameters/ID"
        - $ref: "#/components/parameters/Limit"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: "#/components/schemas/TrailPoint"
                required: [items]
  /api/v1/fences:
    get:
      x-capability: fence:read
      summary: Lista de geocercas
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/FenceList"
    post:
      x-capability: fence:write
      summary: Crea una geocerca
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Fence"
      responses:
        "201":
          description: Creada
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Fence"
        "400":
          $ref: "#/components/responses/Error"
        "409":
          $ref: "#/components/responses/Error"
  /api/v1/fences/{id}:
    get:
      x-capability: fence:read
      summary: Detalle de geocerca
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Fence"
        "404":
          $ref: "#/components/responses/Error"
    put:
      x-capability: fence:write
      summary: Sustituye una geocerca
      parameters:
        - $ref: "#/components/parameters/ID"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Fence"
      responses:
        "200":
          description: Actualizada
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Fence"
        "400":
          $ref: "#/components/responses/Error"
        "404":
          $ref: "#/components/responses/Error"
    delete:
      x-capability: fence:delete
      summary: Elimina una geocerca
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "204":
          description: Eliminada
        "404":
          $ref: "#/components/responses/Error"
  /api/v1/routes:
    get:
      x-capability: route:read
      summary: Lista de rutas
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/RouteList"
    post:
      x-capability: route:write
      summary: Crea una ruta
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Route"
      responses:
        "201":
          description: Creada
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Route"
        "400":
          $ref: "#/components/responses/Error"
        "409":
          $ref: "#/components/responses/Error"
  /api/v1/routes/{id}:
    get:
      x-capability: route:read
      summary: Detalle de ruta
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Route"
        "404":
          $ref: "#/components/responses/Error"
    put:
      x-capability: route:write
      summary: Sustituye una ruta
      parameters:
        - $ref: "#/components/parameters/ID"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Route"
      responses:
        "200":
          description: Actualizada
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Route"
        "400":
          $ref: "#/components/responses/Error"
        "404":
          $ref: "#/components/responses/Error"
    delete:
      x-capability: route:delete
      summary: Elimina una ruta
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "204":
          description: Eliminada
  /api/v1/pois:
    get:
      x-capability: fence:read
      summary: Lista de puntos de interés
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/POIList"
    post:
      x-capability: fence:write
      summary: Crea un POI
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/POI"
      responses:
        "201":
          description: Creado
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/POI"
        "400":
          $ref: "#/components/responses/Error"
  /api/v1/pois/geojson:
    get:
      x-capability: fence:read
      summary: POIs como FeatureCollection
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                additionalProperties: true
  /api/v1/pois/{id}:
    get:
      x-capability: fence:read
      summary: Detalle de POI
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/POI"
        "404":
          $ref: "#/components/responses/Error"
    put:
      x-capability: fence:write
      summary: Sustituye un POI
      parameters:
        - $ref: "#/components/parameters/ID"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/POI"
      responses:
        "200":
          description: Actualizado
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/POI"
    delete:
      x-capability: fence:delete
      summary: Elimina un POI
      parameters:
        - $ref: "#/components/parameters/ID"
      responses:
        "204":
          description: Eliminado
  /api/v1/engine/status:
    get:
      x-capability: device:read
      summary: Estado del motor
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/EngineStatus"
  /api/v1/engine/run-once:
    post:
      x-capability: engine:run
      summary: Ejecuta un ciclo ahora
      responses:
        "200":
          description: Ciclo ejecutado
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/CycleStats"
        "409":
          $ref: "#/components/responses/Error"
  /api/v1/events:
    get:
      x-capability: device:read
      summary: Últimas transiciones
      parameters:
        - $ref: "#/components/parameters/Limit"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: "#/components/schemas/Transition"
                required: [items]
  /api/v1/actions:
    get:
      x-capability: device:read
      summary: Últimas acciones ejecutadas
      parameters:
        - $ref: "#/components/parameters/Limit"
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: "#/components/schemas/ActionResult"
                required: [items]
components:
  parameters:
    ID:
      name: id
      in: path
      required: true
      schema:
        type: string
    Limit:
      name: limit
      in: query
      schema:
        type: integer
        minimum: 1
  responses:
    Error:
      description: Error con forma única
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
  schemas:
    Error:
      type: object
      properties:
        error:
          type: string
        code:
          type: string
        detail: {}
      required: [error, code]
    Point:
      type: object
      properties:
        lat:
          type: number
        lng:
          type: number
      required: [lat, lng]
    Health:
      type: object
      properties:
        status:
          type: string
        version:
          type: string
        mode:
          type: string
        enforcement:
          type: string
        web_built:
          type: boolean
        setup_required:
          type: boolean
        engine:
          type: object
          properties:
            running:
              type: boolean
            cycles:
              type: integer
            last_cycle_at:
              type: [string, "null"]
              format: date-time
            interval_seconds:
              type: integer
          required: [running, cycles, interval_seconds]
        map:
          type: object
          properties:
            enabled:
              type: boolean
            tiles_url:
              type: string
          required: [enabled, tiles_url]
      required: [status, version, mode, enforcement, web_built, setup_required, engine, map]
    SetupRequest:
      type: object
      properties:
        email:
          type: string
        name:
          type: string
        password:
          type: string
        mode:
          type: string
          enum: [demo, empty]
      required: [email, name, password, mode]
    LoginRequest:
      type: object
      properties:
        email:
          type: string
        password:
          type: string
      required: [email, password]
    User:
      type: object
      properties:
        id:
          type: string
        email:
          type: string
        name:
          type: string
        org:
          type: string
        role:
          type: string
          enum: [owner, admin, operator, viewer, auditor]
        via:
          type: string
      required: [id, email, name, org, role, via]
    SessionResponse:
      type: object
      properties:
        user:
          $ref: "#/components/schemas/User"
        csrf:
          type: string
        capabilities:
          type: array
          items:
            type: string
      required: [user, csrf, capabilities]
    Inventory:
      type: object
      properties:
        os_version:
          type: string
        model:
          type: string
        manufacturer:
          type: string
        serial_number:
          type: string
        imei:
          type: string
        battery_level:
          type: integer
        battery_state:
          type: string
        storage_total_gb:
          type: number
        storage_free_gb:
          type: number
        encryption_enabled:
          type: boolean
        carrier:
          type: string
        assigned_user:
          type: string
        department:
          type: string
        device_tag:
          type: string
        enrolled_at:
          type: string
          format: date-time
        last_checkin:
          type: string
          format: date-time
        management_mode:
          type: string
        ownership:
          type: string
        supervised:
          type: boolean
        lockdown_mode:
          type: boolean
        apps:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
              version:
                type: string
            required: [name, version]
    Verdict:
      type: object
      properties:
        score:
          type: [number, "null"]
        severity:
          type: string
        reasons:
          type: array
          items:
            type: string
        matched_policies:
          type: array
          items:
            type: string
        evaluated_at:
          type: string
          format: date-time
        provenance:
          type: string
        verified:
          type: boolean
      required: [score, severity, reasons, matched_policies, provenance, verified]
    Device:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        platform:
          type: string
        status:
          type: string
        compliant:
          type: [boolean, "null"]
        provider:
          type: string
        provider_refs:
          type: object
          additionalProperties:
            type: string
        location:
          type: object
          properties:
            point:
              $ref: "#/components/schemas/Point"
            accuracy_m:
              type: number
            source:
              type: string
            observed_at:
              type: string
              format: date-time
          required: [source, observed_at]
        network:
          type: object
          properties:
            ip:
              type: string
            ssid:
              type: string
            bssid:
              type: string
        inventory:
          $ref: "#/components/schemas/Inventory"
        fence_state:
          type: string
          enum: [inside, outside, unknown]
        inside_fence:
          type: string
        last_inside_fence:
          type: string
        route_id:
          type: string
        route_state:
          type: string
          enum: [on_route, off_route, unassigned]
        route_deviation_m:
          type: number
        risk:
          $ref: "#/components/schemas/Verdict"
        evaluation_error:
          type: string
        last_report_at:
          type: string
          format: date-time
      required: [id, name, platform, compliant, provider, location, network, inventory, fence_state, inside_fence, last_inside_fence, route_state, risk, last_report_at]
    DeviceList:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/Device"
        total:
          type: integer
      required: [items, total]
    TrailPoint:
      type: object
      properties:
        at:
          type: string
          format: date-time
        point:
          $ref: "#/components/schemas/Point"
      required: [at, point]
    FenceAction:
      type: object
      properties:
        action:
          type: string
          enum: [lock, wipe, message, locate, reboot, clear_passcode, set_compliance, custom, notify]
        when:
          type: string
          enum: [on_enter, on_exit, on_violation, on_unknown]
        params:
          type: object
          additionalProperties: true
        enabled:
          type: boolean
      required: [action, when, enabled]
    Fence:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        kind:
          type: string
          enum: [circle, polygon]
        center:
          $ref: "#/components/schemas/Point"
        radius_m:
          type: number
        polygon:
          type: array
          items:
            $ref: "#/components/schemas/Point"
        rules:
          type: object
          properties:
            violation_interval_cycles:
              type: integer
            dwell_seconds:
              type: integer
        actions:
          type: array
          items:
            $ref: "#/components/schemas/FenceAction"
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
      required: [id, name, kind, rules, actions, created_at, updated_at]
    FenceList:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/Fence"
        total:
          type: integer
      required: [items, total]
    Route:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        corridor_m:
          type: number
        waypoints:
          type: array
          items:
            $ref: "#/components/schemas/Point"
        device_ids:
          type: array
          items:
            type: string
        color:
          type: string
        actions:
          type: array
          items:
            $ref: "#/components/schemas/FenceAction"
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
      required: [id, name, corridor_m, waypoints, device_ids, actions, created_at, updated_at]
    RouteList:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/Route"
        total:
          type: integer
      required: [items, total]
    POI:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        category:
          type: string
        tags:
          type: array
          items:
            type: string
        point:
          $ref: "#/components/schemas/Point"
        metadata:
          type: object
          additionalProperties:
            type: string
      required: [id, name, category, point]
    POIList:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/POI"
        total:
          type: integer
      required: [items, total]
    ProviderHealth:
      type: object
      properties:
        ok:
          type: boolean
        error:
          type: string
        devices:
          type: integer
        latency_ms:
          type: integer
        last_ok:
          type: string
          format: date-time
      required: [ok, devices, latency_ms]
    CycleStats:
      type: object
      properties:
        at:
          type: string
          format: date-time
        duration_ms:
          type: integer
        mode:
          type: string
        devices_total:
          type: integer
        inside:
          type: integer
        outside:
          type: integer
        unknown:
          type: integer
        transitions:
          type: integer
        actions_planned:
          type: integer
        actions_executed:
          type: integer
        evaluation_errors:
          type: integer
        providers:
          type: object
          additionalProperties:
            $ref: "#/components/schemas/ProviderHealth"
      required: [at, duration_ms, mode, devices_total, inside, outside, unknown, transitions, actions_planned, actions_executed, evaluation_errors, providers]
    EngineStatus:
      type: object
      properties:
        mode:
          type: string
        enforcement:
          type: string
        interval_seconds:
          type: integer
        running:
          type: boolean
        cycles:
          type: integer
        last_cycle:
          $ref: "#/components/schemas/CycleStats"
        next_cycle_at:
          type: string
          format: date-time
        providers:
          type: object
          additionalProperties:
            $ref: "#/components/schemas/ProviderHealth"
      required: [mode, enforcement, interval_seconds, running, cycles, providers]
    Transition:
      type: object
      properties:
        at:
          type: string
          format: date-time
        device_id:
          type: string
        device_name:
          type: string
        from:
          type: string
        to:
          type: string
      required: [at, device_id, device_name, from, to]
    ActionResult:
      type: object
      properties:
        adapter:
          type: string
        ok:
          type: boolean
        device_id:
          type: string
        device_name:
          type: string
        action:
          type: string
        params:
          type: object
          additionalProperties: true
        dry_run:
          type: boolean
        simulated:
          type: boolean
        error:
          type: string
        command_id:
          type: string
        note:
          type: string
        at:
          type: string
          format: date-time
        fence_id:
          type: string
        trigger:
          type: string
      required: [adapter, ok, device_id, device_name, action, dry_run, simulated, at]
```

- [ ] **Step 4: Test (pasa), commit**

Run: `go test ./internal/api/ -run TestRutasYOpenAPICoinciden -v`
Expected: PASS. Si falla por una ruta, corregir el YAML (nunca el registro) salvo que la ruta esté mal registrada.

```bash
git add docs/openapi.yaml internal/api/openapi_test.go
git commit -q -m "docs(api): contrato OpenAPI 3.1 con x-capability y test de paridad con el registro

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 13: Subcomandos `serve`, `doctor` y `open` (`cmd/lucidfence`)

**Files:**
- Create: `cmd/lucidfence/app.go`, `cmd/lucidfence/serve.go`, `cmd/lucidfence/doctor.go`, `cmd/lucidfence/open.go`
- Create: `cmd/lucidfence/app_test.go`, `cmd/lucidfence/serve_test.go`, `cmd/lucidfence/doctor_test.go`, `cmd/lucidfence/open_test.go`
- Modify: `cmd/lucidfence/main.go` (mapa de subcomandos y `usage`)

**Interfaces:**
- Produces:
  ```go
  type commonFlags struct { ConfigPath, DataDir, Listen string }
  func parseCommon(name string, args []string, stderr io.Writer, extra func(*flag.FlagSet)) (commonFlags, *flag.FlagSet, error)  // -config (config.json), -data, -listen
  type app struct { cfg config.Config; store *store.Store; org *store.OrgStore; auth *auth.Store; engine *engine.Engine; handler http.Handler; logger *slog.Logger }
  func buildApp(f commonFlags, logger *slog.Logger) (*app, error)   // simulation: registra y construye el conector; live → error "el modo live llega en M3"
  func serve(ctx context.Context, f commonFlags, autostart bool, stdout, stderr io.Writer) int  // imprime "listening on http://host:port" y termina al cancelar ctx
  func runServe(args []string, stdout, stderr io.Writer) int   // envuelve serve con señales SIGINT/SIGTERM; flag -no-autostart
  func runDoctor(args []string, stdout, stderr io.Writer) int  // tabla OK/WARN/FAIL; exit 1 si hay FAIL
  func runOpen(args []string, stdout, stderr io.Writer) int    // abre el navegador si /api/v1/health responde
  var browserOpener = func(url string) error                   // sustituible en tests
  ```

- [ ] **Step 1: Tests de `buildApp` y `serve` (fallan)**

`cmd/lucidfence/app_test.go`:
```go
package main

import (
	"bytes"
	"log/slog"
	"path/filepath"
	"strings"
	"testing"
)

func TestBuildAppSimulacionPorDefecto(t *testing.T) {
	dir := t.TempDir()
	a, err := buildApp(commonFlags{ConfigPath: filepath.Join(dir, "config.json"), DataDir: filepath.Join(dir, "data")}, slog.New(slog.NewTextHandler(&bytes.Buffer{}, nil)))
	if err != nil {
		t.Fatal(err)
	}
	if a.cfg.Mode != "simulation" || a.engine == nil || a.handler == nil || a.auth == nil || a.org.ID() != "default" {
		t.Fatalf("%+v", a.cfg)
	}
}

func TestBuildAppModoLiveNoDisponibleEnM1(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "config.json")
	writeFile(t, cfg, `{"mode":"live"}`)
	_, err := buildApp(commonFlags{ConfigPath: cfg, DataDir: filepath.Join(dir, "data")}, slog.Default())
	if err == nil || !strings.Contains(err.Error(), "live") {
		t.Fatalf("esperaba error de modo live: %v", err)
	}
}

func TestParseCommonFlags(t *testing.T) {
	var errb bytes.Buffer
	f, _, err := parseCommon("serve", []string{"-data", "/tmp/x", "-listen", "127.0.0.1:1"}, &errb, nil)
	if err != nil || f.DataDir != "/tmp/x" || f.Listen != "127.0.0.1:1" || f.ConfigPath != "config.json" {
		t.Fatalf("%v %+v", err, f)
	}
	if _, _, err := parseCommon("serve", []string{"-nope"}, &errb, nil); err == nil {
		t.Fatal("flag desconocido debe fallar")
	}
}
```

`cmd/lucidfence/serve_test.go`:
```go
package main

import (
	"bytes"
	"context"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"testing"
	"time"
)

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

func TestServeArrancaImprimeDireccionYParaConContexto(t *testing.T) {
	dir := t.TempDir()
	var out, errb bytes.Buffer
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan int)
	go func() {
		done <- serve(ctx, commonFlags{ConfigPath: filepath.Join(dir, "config.json"), DataDir: filepath.Join(dir, "data"), Listen: "127.0.0.1:0"}, true, &out, &errb)
	}()
	re := regexp.MustCompile(`listening on (http://127\.0\.0\.1:\d+)`)
	var url string
	for deadline := time.Now().Add(5 * time.Second); time.Now().Before(deadline) && url == ""; {
		if m := re.FindStringSubmatch(out.String()); m != nil {
			url = m[1]
		}
		time.Sleep(20 * time.Millisecond)
	}
	if url == "" {
		t.Fatalf("no imprimió la dirección: %q %q", out.String(), errb.String())
	}
	res, err := http.Get(url + "/api/v1/health")
	if err != nil || res.StatusCode != 200 {
		t.Fatalf("health: %v %v", err, res)
	}
	res.Body.Close()
	cancel()
	select {
	case code := <-done:
		if code != 0 {
			t.Fatalf("exit=%d stderr=%s", code, errb.String())
		}
	case <-time.After(15 * time.Second):
		t.Fatal("serve no terminó tras cancelar")
	}
}

func TestServePuertoOcupadoFalla(t *testing.T) {
	dir := t.TempDir()
	var out, errb bytes.Buffer
	ln, _ := (&netListenConfig{}).listen("127.0.0.1:0")
	defer ln.Close()
	code := serve(context.Background(), commonFlags{ConfigPath: filepath.Join(dir, "config.json"), DataDir: filepath.Join(dir, "data"), Listen: ln.Addr().String()}, false, &out, &errb)
	if code != 1 || !bytes.Contains(errb.Bytes(), []byte("no se puede escuchar")) {
		t.Fatalf("exit=%d stderr=%q", code, errb.String())
	}
}
```

- [ ] **Step 2: Implementar `app.go` y `serve.go`**

`cmd/lucidfence/app.go`:
```go
package main

import (
	"flag"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/adrimg3196/lucidfence/internal/api"
	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
	"github.com/adrimg3196/lucidfence/internal/web"
)

type commonFlags struct {
	ConfigPath string
	DataDir    string
	Listen     string
}

func parseCommon(name string, args []string, stderr io.Writer, extra func(*flag.FlagSet)) (commonFlags, *flag.FlagSet, error) {
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	fs.SetOutput(stderr)
	var f commonFlags
	fs.StringVar(&f.ConfigPath, "config", "config.json", "ruta de config.json")
	fs.StringVar(&f.DataDir, "data", "", "directorio de datos (sobrescribe data_dir)")
	fs.StringVar(&f.Listen, "listen", "", "host:puerto (sobrescribe listen)")
	if extra != nil {
		extra(fs)
	}
	if err := fs.Parse(args); err != nil {
		return f, fs, err
	}
	return f, fs, nil
}

type app struct {
	cfg     config.Config
	store   *store.Store
	org     *store.OrgStore
	auth    *auth.Store
	engine  *engine.Engine
	handler http.Handler
	logger  *slog.Logger
}

func loadConfig(f commonFlags) (config.Config, error) {
	cfg, err := config.Load(f.ConfigPath)
	if err != nil {
		return cfg, err
	}
	if f.DataDir != "" {
		cfg.DataDir = f.DataDir
	}
	if f.Listen != "" {
		cfg.Listen = f.Listen
	}
	return cfg, cfg.Validate()
}

func buildAdapters(cfg config.Config, org *store.OrgStore) ([]uem.Adapter, error) {
	reg := uem.NewRegistry()
	reg.Register(simulation.Name, simulation.NewFromConfig)
	if cfg.Mode != "simulation" {
		return nil, fmt.Errorf("el modo %q llega en M3 (conectores reales); usa mode=simulation", cfg.Mode)
	}
	simCfg := map[string]any{}
	if _, err := os.Stat(org.Path("seed.json")); err == nil {
		simCfg["seed_path"] = org.Path("seed.json")
	}
	ad, err := reg.New(simulation.Name, simCfg, nil)
	if err != nil {
		return nil, err
	}
	return []uem.Adapter{ad}, nil
}

func buildApp(f commonFlags, logger *slog.Logger) (*app, error) {
	cfg, err := loadConfig(f)
	if err != nil {
		return nil, err
	}
	st, err := store.Open(cfg.DataDir)
	if err != nil {
		return nil, err
	}
	org, err := st.Org(cfg.Org)
	if err != nil {
		return nil, err
	}
	as, err := auth.Open(st.AuthDir(), time.Now)
	if err != nil {
		return nil, err
	}
	adapters, err := buildAdapters(cfg, org)
	if err != nil {
		return nil, err
	}
	eng := engine.New(org, adapters, engine.Options{Mode: cfg.Mode, Interval: cfg.Interval(), Logger: logger})
	dist := web.Dist()
	handler, _ := api.New(api.Deps{Engine: eng, Org: org, Auth: as, Web: web.Handler(dist), WebBuilt: web.IsBuilt(dist), Config: cfg, Logger: logger})
	return &app{cfg: cfg, store: st, org: org, auth: as, engine: eng, handler: handler, logger: logger}, nil
}

func newLogger(level string, w io.Writer) *slog.Logger {
	var lvl slog.Level
	_ = lvl.UnmarshalText([]byte(level))
	return slog.New(slog.NewTextHandler(w, &slog.HandlerOptions{Level: lvl}))
}
```

`cmd/lucidfence/serve.go`:
```go
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

type netListenConfig struct{}

func (netListenConfig) listen(addr string) (net.Listener, error) { return net.Listen("tcp", addr) }

// serve arranca el servidor y el motor; termina cuando ctx se cancela.
func serve(ctx context.Context, f commonFlags, autostart bool, stdout, stderr io.Writer) int {
	logger := newLogger("info", stderr)
	a, err := buildApp(f, logger)
	if err != nil {
		fmt.Fprintf(stderr, "lucidfence serve: %v\n", err)
		return 1
	}
	logger = newLogger(a.cfg.LogLevel, stderr)
	ln, err := netListenConfig{}.listen(a.cfg.Listen)
	if err != nil {
		fmt.Fprintf(stderr, "lucidfence serve: no se puede escuchar en %s: %v\n", a.cfg.Listen, err)
		return 1
	}
	fmt.Fprintf(stdout, "listening on http://%s\n", ln.Addr())
	fmt.Fprintf(stdout, "modo=%s enforcement=observe datos=%s dashboard=%v\n", a.cfg.Mode, a.cfg.DataDir, a.engine != nil)
	if autostart {
		a.engine.Start(ctx)
	}
	srv := &http.Server{Handler: a.handler, ReadHeaderTimeout: 10 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 60 * time.Second, IdleTimeout: 2 * time.Minute}
	errCh := make(chan error, 1)
	go func() { errCh <- srv.Serve(ln) }()
	select {
	case <-ctx.Done():
	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			fmt.Fprintf(stderr, "lucidfence serve: %v\n", err)
			return 1
		}
	}
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Warn("apagado forzado", "error", err)
	}
	a.engine.Stop()
	fmt.Fprintln(stdout, "parado")
	return 0
}

func runServe(args []string, stdout, stderr io.Writer) int {
	var noAutostart bool
	f, _, err := parseCommon("serve", args, stderr, func(fs *flag.FlagSet) {
		fs.BoolVar(&noAutostart, "no-autostart", false, "no lanzar el ciclo periódico (solo API)")
	})
	if err != nil {
		return 2
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return serve(ctx, f, !noAutostart, stdout, stderr)
}
```

- [ ] **Step 3: Registrar `serve` en `main.go` y ejecutar tests**

En `cmd/lucidfence/main.go`, sustituir `commands()` y `usage`:
```go
const usage = `uso: lucidfence <subcomando> [opciones]

subcomandos:
  serve     arranca el servidor y el dashboard (127.0.0.1:8765 por defecto)
  doctor    diagnostica la instalación local
  open      abre el dashboard en el navegador si el servidor responde
  version   imprime la versión del binario

opciones comunes: -config config.json  -data <dir>  -listen host:puerto
`

func commands() map[string]command {
	return map[string]command{
		"version": runVersion,
		"serve":   runServe,
		"doctor":  runDoctor,
		"open":    runOpen,
	}
}
```

Crear temporalmente en `cmd/lucidfence/doctor.go` y `open.go` solo la firma (`func runDoctor(args []string, stdout, stderr io.Writer) int { return 0 }`, ídem `runOpen`) para compilar; se implementan en los pasos siguientes.

Run: `go test ./cmd/lucidfence/ -race -run 'TestBuildApp|TestParseCommon|TestServe' -v`
Expected: PASS.

- [ ] **Step 4: Tests de `doctor` y `open` (fallan)**

`cmd/lucidfence/doctor_test.go`:
```go
package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDoctorInstalacionLimpia(t *testing.T) {
	dir := t.TempDir()
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", filepath.Join(dir, "config.json"), "-data", filepath.Join(dir, "data"), "-listen", "127.0.0.1:1"}, &out, &errb)
	s := out.String()
	for _, want := range []string{"OK    binario", "OK    config.json", "OK    directorio de datos", "WARN  usuarios", "WARN  servidor"} {
		if !strings.Contains(s, want) {
			t.Fatalf("falta %q en:\n%s", want, s)
		}
	}
	if code != 0 {
		t.Fatalf("sin FAIL el exit es 0, got %d", code)
	}
}

func TestDoctorFallaConConfigInvalida(t *testing.T) {
	dir := t.TempDir()
	cfg := filepath.Join(dir, "config.json")
	os.WriteFile(cfg, []byte(`{"interval_seconds": 1}`), 0o600)
	var out, errb bytes.Buffer
	code := runDoctor([]string{"-config", cfg, "-data", filepath.Join(dir, "data")}, &out, &errb)
	if code != 1 || !strings.Contains(out.String(), "FAIL  config.json") || !strings.Contains(out.String(), "interval_seconds") {
		t.Fatalf("exit=%d\n%s", code, out.String())
	}
}
```

`cmd/lucidfence/open_test.go`:
```go
package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
)

func TestOpenAbreSiHealthResponde(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v1/health" {
			w.Write([]byte(`{"status":"ok"}`))
			return
		}
		http.NotFound(w, r)
	}))
	defer srv.Close()
	var opened string
	prev := browserOpener
	browserOpener = func(url string) error { opened = url; return nil }
	defer func() { browserOpener = prev }()
	var out, errb bytes.Buffer
	code := runOpen([]string{"-config", filepath.Join(t.TempDir(), "config.json"), "-listen", strings.TrimPrefix(srv.URL, "http://")}, &out, &errb)
	if code != 0 || opened != srv.URL+"/" {
		t.Fatalf("exit=%d opened=%q stderr=%s", code, opened, errb.String())
	}
}

func TestOpenSinServidorExplica(t *testing.T) {
	prev := browserOpener
	browserOpener = func(string) error { t.Fatal("no debe abrir"); return nil }
	defer func() { browserOpener = prev }()
	var out, errb bytes.Buffer
	code := runOpen([]string{"-config", filepath.Join(t.TempDir(), "config.json"), "-listen", "127.0.0.1:1"}, &out, &errb)
	if code != 1 || !strings.Contains(errb.String(), "lucidfence serve") {
		t.Fatalf("exit=%d stderr=%q", code, errb.String())
	}
}
```

- [ ] **Step 5: Implementar `doctor.go` y `open.go`**

`cmd/lucidfence/doctor.go`:
```go
package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/version"
	"github.com/adrimg3196/lucidfence/internal/web"
)

type check struct {
	Name     string
	OK       bool
	Severity string // error | warning
	Detail   string
}

func healthy(listen string, timeout time.Duration) bool {
	c := http.Client{Timeout: timeout}
	res, err := c.Get("http://" + listen + "/api/v1/health")
	if err != nil {
		return false
	}
	res.Body.Close()
	return res.StatusCode == 200
}

func doctorChecks(f commonFlags) []check {
	var out []check
	out = append(out, check{Name: "binario", OK: true, Detail: version.String()})
	cfg, err := loadConfig(f)
	if err != nil {
		return append(out, check{Name: "config.json", Severity: "error", Detail: err.Error()})
	}
	out = append(out, check{Name: "config.json", OK: true, Detail: fmt.Sprintf("%s (modo %s, intervalo %ds, listen %s)", f.ConfigPath, cfg.Mode, cfg.IntervalSeconds, cfg.Listen)})
	st, err := store.Open(cfg.DataDir)
	if err != nil {
		return append(out, check{Name: "directorio de datos", Severity: "error", Detail: err.Error()})
	}
	probe := filepath.Join(st.Root(), ".doctor-probe")
	if err := os.WriteFile(probe, []byte("ok"), 0o600); err != nil {
		out = append(out, check{Name: "directorio de datos", Severity: "error", Detail: "no escribible: " + err.Error()})
	} else {
		_ = os.Remove(probe)
		out = append(out, check{Name: "directorio de datos", OK: true, Detail: st.Root()})
	}
	if web.IsBuilt(web.Dist()) {
		out = append(out, check{Name: "dashboard embebido", OK: true, Detail: "compilado"})
	} else {
		out = append(out, check{Name: "dashboard embebido", Severity: "warning", Detail: "este binario no lleva el dashboard (make web build); la API funciona"})
	}
	if org, err := st.Org(cfg.Org); err == nil {
		if _, err := os.Stat(org.Path("seed.json")); err == nil {
			out = append(out, check{Name: "seed de simulación", OK: true, Detail: org.Path("seed.json")})
		} else {
			out = append(out, check{Name: "seed de simulación", Severity: "warning", Detail: "sin seed.json; se usará la flota demo embebida"})
		}
	}
	if as, err := auth.Open(st.AuthDir(), time.Now); err == nil {
		if as.HasUsers() {
			out = append(out, check{Name: "usuarios", OK: true, Detail: "owner creado"})
		} else {
			out = append(out, check{Name: "usuarios", Severity: "warning", Detail: "pendiente el asistente inicial (abre el dashboard)"})
		}
	}
	if healthy(cfg.Listen, 2*time.Second) {
		out = append(out, check{Name: "servidor", OK: true, Detail: "responde en http://" + cfg.Listen})
	} else {
		out = append(out, check{Name: "servidor", Severity: "warning", Detail: "no responde en http://" + cfg.Listen + "; arranca con lucidfence serve"})
	}
	return out
}

func runDoctor(args []string, stdout, stderr io.Writer) int {
	f, _, err := parseCommon("doctor", args, stderr, nil)
	if err != nil {
		return 2
	}
	code := 0
	for _, c := range doctorChecks(f) {
		mark := "OK  "
		if !c.OK {
			mark = "WARN"
			if c.Severity == "error" {
				mark, code = "FAIL", 1
			}
		}
		fmt.Fprintf(stdout, "%s  %-22s %s\n", mark, c.Name, c.Detail)
	}
	return code
}
```

`cmd/lucidfence/open.go`:
```go
package main

import (
	"fmt"
	"io"
	"os/exec"
	"runtime"
	"time"
)

// browserOpener abre una URL en el navegador del sistema; los tests lo sustituyen.
var browserOpener = func(url string) error {
	switch runtime.GOOS {
	case "darwin":
		return exec.Command("open", url).Start()
	case "windows":
		return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	default:
		return exec.Command("xdg-open", url).Start()
	}
}

func runOpen(args []string, stdout, stderr io.Writer) int {
	f, _, err := parseCommon("open", args, stderr, nil)
	if err != nil {
		return 2
	}
	cfg, err := loadConfig(f)
	if err != nil {
		fmt.Fprintf(stderr, "lucidfence open: %v\n", err)
		return 1
	}
	url := "http://" + cfg.Listen + "/"
	if !healthy(cfg.Listen, 2*time.Second) {
		fmt.Fprintf(stderr, "lucidfence open: el servidor no responde en %s; arranca con `lucidfence serve`\n", url)
		return 1
	}
	if err := browserOpener(url); err != nil {
		fmt.Fprintf(stderr, "lucidfence open: no se pudo abrir el navegador: %v\nabre %s manualmente\n", err, url)
		return 1
	}
	fmt.Fprintf(stdout, "abriendo %s\n", url)
	return 0
}
```

- [ ] **Step 6: Tests completos, lint, prueba manual, commit**

```bash
go test ./cmd/lucidfence/ -race -cover -v
golangci-lint run ./cmd/...
make build && ./bin/lucidfence doctor -data /tmp/lf-doctor && ./bin/lucidfence serve -data /tmp/lf-m1 -listen 127.0.0.1:8765 &
sleep 2 && curl -s http://127.0.0.1:8765/api/v1/health && kill %1
```

Expected: tests PASS ≥ 70 %; `doctor` imprime la tabla; `health` responde con `"setup_required":true`.

```bash
git add cmd/lucidfence
git commit -q -m "feat(cli): serve con apagado ordenado, doctor con diagnóstico en tabla y open

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 14: Batería runtime del hito (`internal/battery`)

**Files:**
- Create: `internal/battery/server.go`, `internal/battery/checks_m1.go`, `internal/battery/server_test.go`
- Modify: `internal/battery/battery.go` (`Env` con cliente HTTP y CSRF; `Checks()` concatena M0 y M1), `Makefile` (`battery: web build`)

**Interfaces:**
- Produces:
  ```go
  type Env struct { Bin, Tmp, BaseURL string; Client *http.Client; CSRF string; stop func() }
  func (env *Env) StartServer(ctx context.Context) error   // lanza `bin serve -data <Tmp>/data -config <Tmp>/config.json -listen 127.0.0.1:0`, parsea "listening on", rellena BaseURL y Client (con cookie jar)
  func (env *Env) StopServer()
  func (env *Env) GetJSON(ctx, path string, out any) (int, error)
  func (env *Env) PostJSON(ctx, path string, body, out any) (int, error)  // añade X-LucidFence-CSRF si env.CSRF != ""
  func checksM1() []Check
  ```
  Checks M1 (nombres exactos, en orden): `serve arranca y /api/v1/health responde`, `readyz confirma datos escribibles`, `setup crea el owner y abre sesión`, `sin sesión /devices devuelve 401 con forma de error`, `flota demo visible vía /devices`, `run-once evalúa la flota y hay dispositivos inside`, `transición none:unknown → demo-hq:inside registrada`, `acciones on_enter ejecutadas en dry-run (observe)`, `dashboard real embebido en /`, `mutación con cookie sin CSRF devuelve 403`, `servidor para limpio`.

- [ ] **Step 1: Test del arranque de servidor (falla)**

`internal/battery/server_test.go`:
```go
package battery

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

func buildBinary(t *testing.T) string {
	t.Helper()
	bin := filepath.Join(t.TempDir(), "lucidfence")
	cmd := exec.Command("go", "build", "-o", bin, "../../cmd/lucidfence")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go build: %v\n%s", err, out)
	}
	return bin
}

func TestStartServerYChecksM1(t *testing.T) {
	if testing.Short() {
		t.Skip("compila el binario; omitido en -short")
	}
	env := &Env{Bin: buildBinary(t), Tmp: t.TempDir()}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	if err := env.StartServer(ctx); err != nil {
		t.Fatal(err)
	}
	defer env.StopServer()
	var health map[string]any
	if code, err := env.GetJSON(ctx, "/api/v1/health", &health); err != nil || code != 200 || health["status"] != "ok" {
		t.Fatalf("%d %v %v", code, err, health)
	}
	var buf bytesBuffer
	passed, total := Run(ctx, env, checksM1WithoutServer(), &buf)
	if passed != total {
		t.Fatalf("batería M1: %d/%d\n%s", passed, total, buf.String())
	}
	if _, err := os.Stat(filepath.Join(env.Tmp, "data", "orgs", "default", "devices.json")); err != nil {
		t.Fatal("run-once debe persistir devices.json")
	}
}
```

Y en el mismo fichero de test, el buffer auxiliar:
```go
import "bytes"

type bytesBuffer = bytes.Buffer
```

- [ ] **Step 2: Implementar `server.go`, `checks_m1.go` y ampliar `battery.go`**

`internal/battery/battery.go`, sustituir `Env` y `Checks`:
```go
// Env es el entorno compartido por los checks.
type Env struct {
	Bin     string       // ruta al binario lucidfence compilado
	Tmp     string       // directorio temporal para datos
	BaseURL string       // http://127.0.0.1:<port> cuando hay servidor
	Client  *http.Client // con cookie jar; lo rellena StartServer
	CSRF    string       // token CSRF de la sesión abierta por el check de setup
	stop    func()
}

// Checks devuelve todos los checks registrados, en orden.
func Checks() []Check {
	return append(checksM0(), checksM1()...)
}
```
(añadir `"net/http"` a los imports).

`internal/battery/server.go`:
```go
package battery

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var listenRe = regexp.MustCompile(`listening on (http://127\.0\.0\.1:\d+)`)

// StartServer lanza el binario en un puerto libre con datos temporales.
func (env *Env) StartServer(ctx context.Context) error {
	dataDir := filepath.Join(env.Tmp, "data")
	cmd := exec.CommandContext(ctx, env.Bin, "serve", "-data", dataDir, "-config", filepath.Join(env.Tmp, "config.json"), "-listen", "127.0.0.1:0")
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		return err
	}
	env.stop = func() {
		_ = cmd.Process.Signal(os.Interrupt)
		done := make(chan struct{})
		go func() { _ = cmd.Wait(); close(done) }()
		select {
		case <-done:
		case <-time.After(10 * time.Second):
			_ = cmd.Process.Kill()
		}
	}
	lines := make(chan string, 1)
	go func() {
		sc := bufio.NewScanner(stdout)
		for sc.Scan() {
			if m := listenRe.FindStringSubmatch(sc.Text()); m != nil {
				lines <- m[1]
				break
			}
		}
		_, _ = io.Copy(io.Discard, stdout)
	}()
	select {
	case url := <-lines:
		env.BaseURL = url
	case <-time.After(15 * time.Second):
		env.StopServer()
		return fmt.Errorf("el servidor no imprimió su dirección en 15 s; stderr: %s", stderr.String())
	case <-ctx.Done():
		return ctx.Err()
	}
	jar, _ := cookiejar.New(nil)
	env.Client = &http.Client{Jar: jar, Timeout: 30 * time.Second}
	return nil
}

// StopServer para el binario (SIGINT, kill a los 10 s).
func (env *Env) StopServer() {
	if env.stop != nil {
		env.stop()
		env.stop = nil
	}
}

func (env *Env) do(ctx context.Context, method, path string, body, out any) (int, error) {
	if env.Client == nil {
		return 0, errors.New("servidor no arrancado")
	}
	var buf bytes.Buffer
	if body != nil {
		_ = json.NewEncoder(&buf).Encode(body)
	}
	req, err := http.NewRequestWithContext(ctx, method, env.BaseURL+path, &buf)
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/json")
	if env.CSRF != "" {
		req.Header.Set("X-LucidFence-CSRF", env.CSRF)
	}
	res, err := env.Client.Do(req)
	if err != nil {
		return 0, err
	}
	defer res.Body.Close()
	raw, _ := io.ReadAll(res.Body)
	if out != nil && len(raw) > 0 && strings.HasPrefix(res.Header.Get("Content-Type"), "application/json") {
		_ = json.Unmarshal(raw, out)
	}
	if s, ok := out.(*string); ok {
		*s = string(raw)
	}
	return res.StatusCode, nil
}

// GetJSON hace GET y decodifica JSON (o vuelca el cuerpo si out es *string).
func (env *Env) GetJSON(ctx context.Context, path string, out any) (int, error) {
	return env.do(ctx, http.MethodGet, path, nil, out)
}

// PostJSON hace POST con cuerpo JSON y cabecera CSRF si hay sesión.
func (env *Env) PostJSON(ctx context.Context, path string, body, out any) (int, error) {
	return env.do(ctx, http.MethodPost, path, body, out)
}
```

`internal/battery/checks_m1.go`:
```go
package battery

import (
	"context"
	"fmt"
	"strings"
)

func checksM1() []Check {
	return append([]Check{{Name: "serve arranca y /api/v1/health responde", Run: checkServe}}, checksM1WithoutServer()...)
}

// checksM1WithoutServer son los checks que asumen el servidor ya arrancado.
func checksM1WithoutServer() []Check {
	return []Check{
		{Name: "readyz confirma datos escribibles", Run: checkReadyz},
		{Name: "setup crea el owner y abre sesión", Run: checkSetup},
		{Name: "sin sesión /devices devuelve 401 con forma de error", Run: checkUnauthenticated},
		{Name: "flota demo visible vía /devices", Run: checkDevices},
		{Name: "run-once evalúa la flota y hay dispositivos inside", Run: checkRunOnce},
		{Name: "transición none:unknown → demo-hq:inside registrada", Run: checkTransition},
		{Name: "acciones on_enter ejecutadas en dry-run (observe)", Run: checkActionsDryRun},
		{Name: "dashboard real embebido en /", Run: checkDashboard},
		{Name: "mutación con cookie sin CSRF devuelve 403", Run: checkCSRF},
		{Name: "servidor para limpio", Run: checkStop},
	}
}

func checkServe(ctx context.Context, env *Env) error {
	if err := env.StartServer(ctx); err != nil {
		return err
	}
	var h map[string]any
	code, err := env.GetJSON(ctx, "/api/v1/health", &h)
	if err != nil || code != 200 || h["status"] != "ok" || h["setup_required"] != true {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, h)
	}
	return nil
}

func checkReadyz(ctx context.Context, env *Env) error {
	var r map[string]any
	if code, err := env.GetJSON(ctx, "/api/v1/readyz", &r); err != nil || code != 200 || r["ready"] != true {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, r)
	}
	return nil
}

func checkSetup(ctx context.Context, env *Env) error {
	var out map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/auth/setup", map[string]any{"email": "battery@lucidfence.local", "name": "Batería", "password": "bateria-runtime-2026", "mode": "demo"}, &out)
	if err != nil || code != 201 {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, out)
	}
	csrf, _ := out["csrf"].(string)
	if csrf == "" {
		return fmt.Errorf("sin csrf: %v", out)
	}
	env.CSRF = csrf
	return nil
}

func checkUnauthenticated(ctx context.Context, env *Env) error {
	anon := &Env{BaseURL: env.BaseURL, Client: &http.Client{}}
	var out map[string]any
	code, err := anon.GetJSON(ctx, "/api/v1/devices", &out)
	if err != nil || code != 401 || out["code"] != "unauthenticated" || out["error"] == "" {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, out)
	}
	return nil
}

func checkDevices(ctx context.Context, env *Env) error {
	var out map[string]any
	code, err := env.GetJSON(ctx, "/api/v1/devices", &out)
	if err != nil || code != 200 {
		return fmt.Errorf("code=%d err=%v", code, err)
	}
	if n, _ := out["total"].(float64); n != 6 {
		return fmt.Errorf("total=%v, quiero 6", out["total"])
	}
	return nil
}

func checkRunOnce(ctx context.Context, env *Env) error {
	var st map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/engine/run-once", nil, &st)
	if err != nil || code != 200 {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, st)
	}
	if st["devices_total"].(float64) != 6 || st["inside"].(float64) < 2 {
		return fmt.Errorf("stats=%v", st)
	}
	var devs map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/devices?state=inside", &devs); err != nil {
		return err
	}
	for _, it := range devs["items"].([]any) {
		if d := it.(map[string]any); d["id"] == "dev-001" && d["inside_fence"] == "demo-hq" {
			return nil
		}
	}
	return fmt.Errorf("dev-001 no está inside en demo-hq: %v", devs)
}

func checkTransition(ctx context.Context, env *Env) error {
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/events?limit=100", &out); err != nil {
		return err
	}
	for _, it := range out["items"].([]any) {
		ev := it.(map[string]any)
		if ev["device_id"] == "dev-001" && ev["from"] == "none:unknown" && ev["to"] == "demo-hq:inside" {
			return nil
		}
	}
	return fmt.Errorf("sin transición de dev-001: %v", out)
}

func checkActionsDryRun(ctx context.Context, env *Env) error {
	var out map[string]any
	if _, err := env.GetJSON(ctx, "/api/v1/actions?limit=100", &out); err != nil {
		return err
	}
	items := out["items"].([]any)
	if len(items) == 0 {
		return fmt.Errorf("sin acciones")
	}
	for _, it := range items {
		a := it.(map[string]any)
		if a["dry_run"] != true || a["simulated"] != true {
			return fmt.Errorf("acción fuera de dry-run: %v", a)
		}
	}
	return nil
}

func checkDashboard(ctx context.Context, env *Env) error {
	var html string
	code, err := env.GetJSON(ctx, "/", &html)
	if err != nil || code != 200 {
		return fmt.Errorf("code=%d err=%v", code, err)
	}
	if !strings.Contains(html, `id="root"`) || strings.Contains(html, "frontend no compilado") {
		return fmt.Errorf("el binario no lleva el dashboard compilado (make web)")
	}
	return nil
}

func checkCSRF(ctx context.Context, env *Env) error {
	saved := env.CSRF
	env.CSRF = ""
	defer func() { env.CSRF = saved }()
	var out map[string]any
	code, err := env.PostJSON(ctx, "/api/v1/fences", map[string]any{"id": "x", "name": "X", "kind": "circle", "center": map[string]float64{"lat": 1, "lng": 1}, "radius_m": 10}, &out)
	if err != nil || code != 403 || out["code"] != "csrf" {
		return fmt.Errorf("code=%d err=%v body=%v", code, err, out)
	}
	return nil
}

func checkStop(_ context.Context, env *Env) error {
	env.StopServer()
	return nil
}
```

(añadir `"net/http"` a los imports de `checks_m1.go`).

- [ ] **Step 3: Makefile y ejecución**

En `Makefile`, cambiar `battery: build` por `battery: web build`.

```bash
go test ./internal/battery/ -race -v
make web && make build && scripts/battery.sh bin/lucidfence
```

Expected: test PASS; batería `RUNTIME: 12/12`.

- [ ] **Step 4: Commit**

```bash
git add internal/battery Makefile
git commit -q -m "test(battery): checks en vivo del núcleo demo (serve, setup, flota, ciclo, transición, dry-run, CSRF, dashboard)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 15: Frontend base: dependencias, primitivas UI, i18n, permisos, estados y cliente API tipado

**Files:**
- Modify: `web/package.json`, `internal/arch/allowlist_npm.txt` (añadir `@testing-library/user-event`)
- Create: `web/src/lib/utils.ts`, `web/src/lib/i18n.tsx`, `web/src/lib/i18n.test.tsx`, `web/src/lib/permissions.ts`, `web/src/lib/permissions.test.ts`, `web/src/lib/format.ts`, `web/src/lib/query.ts`
- Create: `web/src/components/ui/button.tsx`, `input.tsx`, `label.tsx`, `card.tsx`, `badge.tsx`, `skeleton.tsx`, `table.tsx`, `dialog.tsx`, `tabs.tsx`, `select.tsx`
- Create: `web/src/components/states/Loading.tsx`, `Empty.tsx`, `ErrorState.tsx`, `states.test.tsx`
- Create: `web/src/api/client.ts`, `web/src/api/hooks.ts`, `web/src/api/schema.d.ts` (generado y commiteado), `web/src/test/render.tsx`

**Interfaces:**
- Produces:
  ```ts
  // lib/i18n.tsx
  export type Lang = "es" | "en"; export type Key = keyof typeof es;
  export function I18nProvider({ children, initial? }): JSX.Element
  export function useT(): (key: Key, vars?: Record<string, string | number>) => string
  export function useLang(): { lang: Lang; setLang: (l: Lang) => void }
  // lib/permissions.ts
  export function can(capabilities: readonly string[] | undefined, cap: string): boolean
  // api/client.ts
  export const api: openapi-fetch client tipado con `paths`; export function setCsrf(v: string): void
  export class ApiError extends Error { status: number; code: string; detail?: unknown }
  export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T
  // api/hooks.ts (TanStack Query)
  export type Device = components["schemas"]["Device"]; Fence; Route; POI; Transition; ActionResult; EngineStatus; CycleStats; Health; SessionResponse
  export function useHealth(); useAuthStatus(); useMe(); useSetup(); useLogin(); useLogout()
  export function useDevices(params?: { state?: string; q?: string }); useDevice(id); useDeviceTrail(id, limit?)
  export function useFences(); useFence(id); useCreateFence(); useUpdateFence(); useDeleteFence()
  export function useEngineStatus(); useRunOnce(); useEvents(limit?); useActions(limit?)
  // components/states
  export function Loading({ rows?: number; label?: string }); Empty({ title; description?; action?: ReactNode }); ErrorState({ error: unknown; onRetry?: () => void })
  // test/render.tsx
  export function renderWithProviders(ui: ReactNode, opts?: { route?: string }): RenderResult
  ```

- [ ] **Step 1: Dependencias**

En `web/package.json`, `dependencies`:
```json
  "dependencies": {
    "@hookform/resolvers": "5.9.1",
    "@phosphor-icons/react": "2.1.10",
    "@tanstack/react-query": "5.102.8",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "geist": "1.7.2",
    "maplibre-gl": "6.7.0",
    "motion": "13.2.0",
    "openapi-fetch": "0.17.0",
    "radix-ui": "1.6.7",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "react-hook-form": "7.87.0",
    "react-router": "8.3.1",
    "recharts": "3.10.1",
    "tailwind-merge": "3.6.0",
    "zod": "4.5.4"
  },
```
y añadir a `devDependencies`: `"openapi-typescript": "7.13.0"`, `"@testing-library/user-event": "14.6.1"`. Añadir a `scripts`: `"gen:api": "openapi-typescript ../docs/openapi.yaml -o src/api/schema.d.ts"`. Añadir `@testing-library/user-event` a `internal/arch/allowlist_npm.txt`.

```bash
cd web && npm install && npm run gen:api && head -5 src/api/schema.d.ts && cd .. && go test ./internal/arch/
```

Expected: `schema.d.ts` generado con `export interface paths`; allowlist verde.

- [ ] **Step 2: Utilidades, i18n y permisos con tests**

`web/src/lib/utils.ts`:
```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

`web/src/lib/format.ts`:
```ts
export function formatDateTime(iso: string | null | undefined, lang: string): string {
  if (!iso) return "—".replace("—", "-");
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return new Intl.DateTimeFormat(lang, { dateStyle: "short", timeStyle: "short" }).format(d);
}

export function percent(part: number, total: number): string {
  if (total === 0) return "0 %";
  return `${Math.round((part / total) * 100)} %`;
}

export function meters(m: number | null | undefined): string {
  if (m == null) return "-";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}
```

`web/src/lib/i18n.tsx`:
```tsx
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export const es = {
  "app.name": "LucidFence",
  "nav.overview": "Visión general",
  "nav.map": "Mapa",
  "nav.devices": "Dispositivos",
  "nav.fences": "Geocercas",
  "nav.logout": "Cerrar sesión",
  "theme.toggle": "Cambiar tema",
  "lang.toggle": "English",
  "state.loading": "Cargando",
  "state.empty": "Nada que mostrar",
  "state.error": "Algo ha fallado",
  "state.retry": "Reintentar",
  "setup.title": "Configura LucidFence",
  "setup.subtitle": "Crea la cuenta de propietario. Todo se guarda en esta máquina.",
  "setup.email": "Email",
  "setup.name": "Nombre",
  "setup.password": "Contraseña (mínimo 10 caracteres)",
  "setup.mode": "Cómo quieres empezar",
  "setup.mode.demo": "Demo local con flota simulada",
  "setup.mode.demo.help": "Seis dispositivos en Madrid, dos geocercas y una ruta. Sin conectar ningún UEM.",
  "setup.mode.empty": "Vacío, conectaré mi UEM",
  "setup.mode.empty.help": "Sin datos. Los conectores reales llegan en el siguiente hito.",
  "setup.submit": "Crear cuenta y entrar",
  "login.title": "Iniciar sesión",
  "login.email": "Email",
  "login.password": "Contraseña",
  "login.submit": "Entrar",
  "login.invalid": "Email o contraseña incorrectos",
  "login.throttled": "Demasiados intentos. Espera un minuto.",
  "overview.title": "Visión general",
  "overview.devices": "Dispositivos",
  "overview.inside": "Dentro",
  "overview.outside": "Fuera",
  "overview.unknown": "Sin ubicación",
  "overview.compliance": "Cumplimiento",
  "overview.engine": "Motor",
  "overview.engine.mode": "Modo",
  "overview.engine.enforcement": "Enforcement",
  "overview.engine.interval": "Intervalo",
  "overview.engine.lastCycle": "Último ciclo",
  "overview.engine.cycles": "Ciclos",
  "overview.engine.run": "Ejecutar ciclo ahora",
  "overview.engine.running": "Ejecutando",
  "overview.events": "Últimas transiciones",
  "overview.providers": "Proveedores",
  "overview.noEvents": "Aún no hay transiciones. Ejecuta un ciclo.",
  "map.title": "Mapa en vivo",
  "map.legend.inside": "Dentro de geocerca",
  "map.legend.outside": "Fuera",
  "map.legend.unknown": "Sin ubicación",
  "map.disabled": "El mapa está desactivado en la configuración (map.enabled=false).",
  "devices.title": "Dispositivos",
  "devices.search": "Buscar por nombre, usuario, modelo o serie",
  "devices.filter.all": "Todos",
  "devices.col.name": "Nombre",
  "devices.col.platform": "Plataforma",
  "devices.col.state": "Geocerca",
  "devices.col.user": "Usuario",
  "devices.col.lastReport": "Último informe",
  "devices.empty": "Sin dispositivos. Ejecuta un ciclo del motor.",
  "device.inventory": "Inventario",
  "device.risk": "Riesgo",
  "device.risk.pending": "Sin evaluar: el motor de riesgo llega en el siguiente hito.",
  "device.trail": "Recorrido",
  "device.events": "Transiciones",
  "device.back": "Volver a dispositivos",
  "device.field.os": "Sistema",
  "device.field.model": "Modelo",
  "device.field.serial": "Serie",
  "device.field.battery": "Batería",
  "device.field.storage": "Almacenamiento",
  "device.field.encryption": "Cifrado",
  "device.field.user": "Usuario",
  "device.field.department": "Departamento",
  "device.field.route": "Ruta",
  "fences.title": "Geocercas",
  "fences.new": "Nueva geocerca",
  "fences.col.name": "Nombre",
  "fences.col.kind": "Tipo",
  "fences.col.actions": "Acciones",
  "fences.empty": "Sin geocercas. Crea la primera.",
  "fences.delete": "Eliminar",
  "fences.delete.confirm": "¿Eliminar la geocerca {name}?",
  "fence.editor.new": "Nueva geocerca",
  "fence.editor.edit": "Editar geocerca",
  "fence.name": "Nombre",
  "fence.id": "Identificador",
  "fence.kind": "Forma",
  "fence.kind.circle": "Círculo",
  "fence.kind.polygon": "Polígono",
  "fence.center": "Centro (lat, lng)",
  "fence.radius": "Radio (m)",
  "fence.polygon": "Vértices, uno por línea: lat, lng",
  "fence.actions": "Acciones por evento",
  "fence.actions.add": "Añadir acción",
  "fence.when.on_enter": "Al entrar",
  "fence.when.on_exit": "Al salir",
  "fence.when.on_violation": "Violación sostenida",
  "fence.when.on_unknown": "Al perder ubicación",
  "fence.save": "Guardar",
  "fence.cancel": "Cancelar",
  "fence.error.polygon": "Un polígono necesita al menos 3 vértices válidos",
  "state.inside": "dentro",
  "state.outside": "fuera",
  "state.unknown": "sin ubicación",
  "common.yes": "Sí",
  "common.no": "No",
  "common.unknown": "Desconocido",
} as const;

export type Key = keyof typeof es;
export type Lang = "es" | "en";

export const en: Record<Key, string> = {
  "app.name": "LucidFence",
  "nav.overview": "Overview",
  "nav.map": "Map",
  "nav.devices": "Devices",
  "nav.fences": "Geofences",
  "nav.logout": "Sign out",
  "theme.toggle": "Toggle theme",
  "lang.toggle": "Español",
  "state.loading": "Loading",
  "state.empty": "Nothing to show",
  "state.error": "Something went wrong",
  "state.retry": "Retry",
  "setup.title": "Set up LucidFence",
  "setup.subtitle": "Create the owner account. Everything stays on this machine.",
  "setup.email": "Email",
  "setup.name": "Name",
  "setup.password": "Password (10 characters minimum)",
  "setup.mode": "How do you want to start",
  "setup.mode.demo": "Local demo with a simulated fleet",
  "setup.mode.demo.help": "Six devices in Madrid, two geofences and one route. No UEM connected.",
  "setup.mode.empty": "Empty, I will connect my UEM",
  "setup.mode.empty.help": "No data. Real connectors arrive in the next milestone.",
  "setup.submit": "Create account and sign in",
  "login.title": "Sign in",
  "login.email": "Email",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.invalid": "Wrong email or password",
  "login.throttled": "Too many attempts. Wait a minute.",
  "overview.title": "Overview",
  "overview.devices": "Devices",
  "overview.inside": "Inside",
  "overview.outside": "Outside",
  "overview.unknown": "No location",
  "overview.compliance": "Compliance",
  "overview.engine": "Engine",
  "overview.engine.mode": "Mode",
  "overview.engine.enforcement": "Enforcement",
  "overview.engine.interval": "Interval",
  "overview.engine.lastCycle": "Last cycle",
  "overview.engine.cycles": "Cycles",
  "overview.engine.run": "Run a cycle now",
  "overview.engine.running": "Running",
  "overview.events": "Latest transitions",
  "overview.providers": "Providers",
  "overview.noEvents": "No transitions yet. Run a cycle.",
  "map.title": "Live map",
  "map.legend.inside": "Inside a geofence",
  "map.legend.outside": "Outside",
  "map.legend.unknown": "No location",
  "map.disabled": "The map is disabled in the configuration (map.enabled=false).",
  "devices.title": "Devices",
  "devices.search": "Search by name, user, model or serial",
  "devices.filter.all": "All",
  "devices.col.name": "Name",
  "devices.col.platform": "Platform",
  "devices.col.state": "Geofence",
  "devices.col.user": "User",
  "devices.col.lastReport": "Last report",
  "devices.empty": "No devices. Run an engine cycle.",
  "device.inventory": "Inventory",
  "device.risk": "Risk",
  "device.risk.pending": "Not evaluated: the risk engine arrives in the next milestone.",
  "device.trail": "Trail",
  "device.events": "Transitions",
  "device.back": "Back to devices",
  "device.field.os": "OS",
  "device.field.model": "Model",
  "device.field.serial": "Serial",
  "device.field.battery": "Battery",
  "device.field.storage": "Storage",
  "device.field.encryption": "Encryption",
  "device.field.user": "User",
  "device.field.department": "Department",
  "device.field.route": "Route",
  "fences.title": "Geofences",
  "fences.new": "New geofence",
  "fences.col.name": "Name",
  "fences.col.kind": "Kind",
  "fences.col.actions": "Actions",
  "fences.empty": "No geofences. Create the first one.",
  "fences.delete": "Delete",
  "fences.delete.confirm": "Delete geofence {name}?",
  "fence.editor.new": "New geofence",
  "fence.editor.edit": "Edit geofence",
  "fence.name": "Name",
  "fence.id": "Identifier",
  "fence.kind": "Shape",
  "fence.kind.circle": "Circle",
  "fence.kind.polygon": "Polygon",
  "fence.center": "Center (lat, lng)",
  "fence.radius": "Radius (m)",
  "fence.polygon": "Vertices, one per line: lat, lng",
  "fence.actions": "Actions per event",
  "fence.actions.add": "Add action",
  "fence.when.on_enter": "On enter",
  "fence.when.on_exit": "On exit",
  "fence.when.on_violation": "Standing violation",
  "fence.when.on_unknown": "On lost location",
  "fence.save": "Save",
  "fence.cancel": "Cancel",
  "fence.error.polygon": "A polygon needs at least 3 valid vertices",
  "state.inside": "inside",
  "state.outside": "outside",
  "state.unknown": "no location",
  "common.yes": "Yes",
  "common.no": "No",
  "common.unknown": "Unknown",
};

const dicts: Record<Lang, Record<Key, string>> = { es, en };

export function detectLang(): Lang {
  try {
    const saved = localStorage.getItem("lf.lang");
    if (saved === "es" || saved === "en") return saved;
  } catch {
    /* sin storage */
  }
  return typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("es") ? "es" : "en";
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (key: Key, vars?: Record<string, string | number>) => string };
const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? detectLang());
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("lf.lang", l);
    } catch {
      /* sin storage */
    }
  }, []);
  const t = useCallback(
    (key: Key, vars?: Record<string, string | number>) => {
      let s: string = dicts[lang][key] ?? key;
      for (const [k, v] of Object.entries(vars ?? {})) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useT fuera de I18nProvider");
  return ctx;
}

export function useT() {
  return useI18n().t;
}

export function useLang() {
  const { lang, setLang } = useI18n();
  return { lang, setLang };
}
```

`web/src/lib/i18n.test.tsx`:
```tsx
import { renderHook, act } from "@testing-library/react";
import { I18nProvider, useT, useLang, es, en } from "./i18n";

test("traduce, interpola y cambia de idioma", () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => <I18nProvider initial="es">{children}</I18nProvider>;
  const { result } = renderHook(() => ({ t: useT(), lang: useLang() }), { wrapper });
  expect(result.current.t("nav.devices")).toBe("Dispositivos");
  expect(result.current.t("fences.delete.confirm", { name: "HQ" })).toBe("¿Eliminar la geocerca HQ?");
  act(() => result.current.lang.setLang("en"));
  expect(result.current.t("nav.devices")).toBe("Devices");
});

test("los diccionarios tienen las mismas claves", () => {
  expect(Object.keys(en).sort()).toEqual(Object.keys(es).sort());
});
```

`web/src/lib/permissions.ts`:
```ts
// La API es la fuente de verdad: /auth/me devuelve las capacidades del rol.
// La UI solo oculta lo que el rol no puede hacer; el servidor lo rechaza igualmente.
export function can(capabilities: readonly string[] | undefined, cap: string): boolean {
  return Array.isArray(capabilities) && capabilities.includes(cap);
}
```

`web/src/lib/permissions.test.ts`:
```ts
import { can } from "./permissions";

test("can consulta la lista de capacidades", () => {
  expect(can(["fence:read", "fence:write"], "fence:write")).toBe(true);
  expect(can(["fence:read"], "fence:write")).toBe(false);
  expect(can(undefined, "fence:read")).toBe(false);
});
```

`web/src/lib/query.ts`:
```ts
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, err) => !(err instanceof ApiError && (err.status === 401 || err.status === 403 || err.status === 404)) && count < 2,
        staleTime: 5_000,
        refetchOnWindowFocus: false,
      },
    },
  });
}
```

- [ ] **Step 3: Cliente API y hooks**

`web/src/api/client.ts`:
```ts
import createClient from "openapi-fetch";
import type { paths } from "./schema";

let csrf = "";

export function setCsrf(value: string) {
  csrf = value;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const api = createClient<paths>({ baseUrl: "/", credentials: "same-origin" });

api.use({
  onRequest({ request }) {
    if (csrf && request.method !== "GET" && request.method !== "HEAD") request.headers.set("X-LucidFence-CSRF", csrf);
    return request;
  },
});

type Result<T> = { data?: T; error?: unknown; response: Response };

export function unwrap<T>(res: Result<T>): T {
  if (res.response.ok) return res.data as T;
  const err = (res.error ?? {}) as { error?: string; code?: string; detail?: unknown };
  throw new ApiError(res.response.status, err.code ?? "unknown", err.error ?? `HTTP ${res.response.status}`, err.detail);
}
```

`web/src/api/hooks.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, setCsrf, unwrap } from "./client";
import type { components } from "./schema";

export type Device = components["schemas"]["Device"];
export type Fence = components["schemas"]["Fence"];
export type Route = components["schemas"]["Route"];
export type POI = components["schemas"]["POI"];
export type Transition = components["schemas"]["Transition"];
export type ActionResult = components["schemas"]["ActionResult"];
export type EngineStatus = components["schemas"]["EngineStatus"];
export type CycleStats = components["schemas"]["CycleStats"];
export type Health = components["schemas"]["Health"];
export type SessionResponse = components["schemas"]["SessionResponse"];
export type TrailPoint = components["schemas"]["TrailPoint"];

export const keys = {
  health: ["health"] as const,
  authStatus: ["auth", "status"] as const,
  me: ["auth", "me"] as const,
  devices: (p?: { state?: string; q?: string }) => ["devices", p ?? {}] as const,
  device: (id: string) => ["devices", id] as const,
  trail: (id: string, limit: number) => ["devices", id, "trail", limit] as const,
  fences: ["fences"] as const,
  fence: (id: string) => ["fences", id] as const,
  engine: ["engine", "status"] as const,
  events: (limit: number) => ["events", limit] as const,
  actions: (limit: number) => ["actions", limit] as const,
};

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: async () => unwrap(await api.GET("/api/v1/health")) });
}

export function useAuthStatus() {
  return useQuery({ queryKey: keys.authStatus, queryFn: async () => unwrap(await api.GET("/api/v1/auth/status")) });
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        const me = unwrap(await api.GET("/api/v1/auth/me"));
        setCsrf(me.csrf);
        return me;
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
  });
}

function useSessionMutation<TBody>(path: "/api/v1/auth/setup" | "/api/v1/auth/login") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: TBody) => {
      const res = await api.POST(path, { body: body as never });
      const session = unwrap(res) as SessionResponse;
      setCsrf(session.csrf);
      return session;
    },
    onSuccess: (session) => {
      qc.setQueryData(keys.me, session);
      qc.setQueryData(keys.authStatus, { setup_required: false });
    },
  });
}

export function useSetup() {
  return useSessionMutation<components["schemas"]["SetupRequest"]>("/api/v1/auth/setup");
}

export function useLogin() {
  return useSessionMutation<components["schemas"]["LoginRequest"]>("/api/v1/auth/login");
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/v1/auth/logout"));
      setCsrf("");
    },
    onSuccess: () => {
      qc.setQueryData(keys.me, null);
      qc.clear();
    },
  });
}

export function useDevices(params?: { state?: string; q?: string }) {
  return useQuery({
    queryKey: keys.devices(params),
    queryFn: async () => unwrap(await api.GET("/api/v1/devices", { params: { query: params } })),
    refetchInterval: 15_000,
  });
}

export function useDevice(id: string) {
  return useQuery({ queryKey: keys.device(id), queryFn: async () => unwrap(await api.GET("/api/v1/devices/{id}", { params: { path: { id } } })), enabled: !!id });
}

export function useDeviceTrail(id: string, limit = 200) {
  return useQuery({
    queryKey: keys.trail(id, limit),
    queryFn: async () => unwrap(await api.GET("/api/v1/devices/{id}/trail", { params: { path: { id }, query: { limit } } })),
    enabled: !!id,
  });
}

export function useFences() {
  return useQuery({ queryKey: keys.fences, queryFn: async () => unwrap(await api.GET("/api/v1/fences")) });
}

export function useFence(id: string) {
  return useQuery({ queryKey: keys.fence(id), queryFn: async () => unwrap(await api.GET("/api/v1/fences/{id}", { params: { path: { id } } })), enabled: !!id });
}

function useInvalidate(...keysToInvalidate: readonly (readonly unknown[])[]) {
  const qc = useQueryClient();
  return () => Promise.all(keysToInvalidate.map((k) => qc.invalidateQueries({ queryKey: k })));
}

export function useCreateFence() {
  const invalidate = useInvalidate(keys.fences);
  return useMutation({ mutationFn: async (body: Fence) => unwrap(await api.POST("/api/v1/fences", { body })), onSuccess: invalidate });
}

export function useUpdateFence() {
  const invalidate = useInvalidate(keys.fences);
  return useMutation({
    mutationFn: async (body: Fence) => unwrap(await api.PUT("/api/v1/fences/{id}", { params: { path: { id: body.id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteFence() {
  const invalidate = useInvalidate(keys.fences);
  return useMutation({ mutationFn: async (id: string) => unwrap(await api.DELETE("/api/v1/fences/{id}", { params: { path: { id } } })), onSuccess: invalidate });
}

export function useEngineStatus() {
  return useQuery({ queryKey: keys.engine, queryFn: async () => unwrap(await api.GET("/api/v1/engine/status")), refetchInterval: 15_000 });
}

export function useRunOnce() {
  const invalidate = useInvalidate(keys.engine, ["devices"], ["events"], ["actions"]);
  return useMutation({ mutationFn: async () => unwrap(await api.POST("/api/v1/engine/run-once")), onSuccess: invalidate });
}

export function useEvents(limit = 20) {
  return useQuery({ queryKey: keys.events(limit), queryFn: async () => unwrap(await api.GET("/api/v1/events", { params: { query: { limit } } })), refetchInterval: 15_000 });
}

export function useActions(limit = 20) {
  return useQuery({ queryKey: keys.actions(limit), queryFn: async () => unwrap(await api.GET("/api/v1/actions", { params: { query: { limit } } })) });
}
```

- [ ] **Step 4: Primitivas UI propias (patrón shadcn: cva + tailwind-merge + Radix)**

`web/src/components/ui/button.tsx`:
```tsx
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-ui)] text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:pointer-events-none disabled:opacity-50 active:translate-y-px",
  {
    variants: {
      variant: {
        default: "bg-accent text-accent-fg hover:bg-accent-h",
        secondary: "border border-border bg-panel text-fg hover:bg-bg-2",
        ghost: "text-fg-2 hover:bg-bg-2 hover:text-fg",
        destructive: "bg-sev-high text-white hover:opacity-90",
      },
      size: { sm: "h-8 px-3", md: "h-9 px-4", lg: "h-11 px-6 text-base", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, ...props }, ref) => {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
});
Button.displayName = "Button";
```

`web/src/components/ui/input.tsx`:
```tsx
import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-9 w-full rounded-[var(--radius-ui)] border border-border bg-panel px-3 text-sm text-fg placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:opacity-50 aria-invalid:border-sev-high",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
```

`web/src/components/ui/label.tsx`:
```tsx
import type { LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium text-fg-2", className)} {...props} />;
}
```

`web/src/components/ui/card.tsx`:
```tsx
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-[var(--radius-ui)] border border-border bg-panel", className)} {...props} />;
}
export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center justify-between gap-4 px-5 pt-5", className)} {...props} />;
}
export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("text-sm font-semibold tracking-tight text-fg", className)} {...props} />;
}
export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5 pt-3", className)} {...props} />;
}
```

`web/src/components/ui/badge.tsx`:
```tsx
import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      neutral: "border-border bg-bg-2 text-fg-2",
      success: "border-transparent bg-sev-low/15 text-sev-low",
      warning: "border-transparent bg-sev-medium/15 text-sev-medium",
      danger: "border-transparent bg-sev-high/15 text-sev-high",
      info: "border-transparent bg-info/15 text-info",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({ className, variant, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
```

`web/src/components/ui/skeleton.tsx`:
```tsx
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn("animate-pulse rounded-[var(--radius-ui)] bg-bg-2", className)} {...props} />;
}
```

`web/src/components/ui/table.tsx`:
```tsx
import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto rounded-[var(--radius-ui)] border border-border">
      <table className={cn("w-full caption-bottom text-sm", className)} {...props} />
    </div>
  );
}
export function THead(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className="bg-bg-2 text-left text-xs uppercase tracking-wide text-muted" {...props} />;
}
export function TBody(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className="divide-y divide-border" {...props} />;
}
export function TR({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("hover:bg-bg-2/60", className)} {...props} />;
}
export function TH({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("px-4 py-2 font-medium", className)} {...props} />;
}
export function TD({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-4 py-2 align-middle", className)} {...props} />;
}
```

`web/src/components/ui/dialog.tsx`:
```tsx
import { Dialog as D } from "radix-ui";
import type { ReactNode } from "react";

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, cancelLabel, onConfirm, children }: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description?: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 bg-fg/40" />
        <D.Content className="fixed left-1/2 top-1/2 w-[min(92vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-ui)] border border-border bg-panel p-5 shadow-lg">
          <D.Title className="text-base font-semibold">{title}</D.Title>
          {description && <D.Description className="mt-1 text-sm text-muted">{description}</D.Description>}
          {children}
          <div className="mt-5 flex justify-end gap-2">
            <D.Close className="h-9 rounded-[var(--radius-ui)] border border-border px-4 text-sm">{cancelLabel}</D.Close>
            <button type="button" onClick={onConfirm} className="h-9 rounded-[var(--radius-ui)] bg-sev-high px-4 text-sm font-medium text-white">
              {confirmLabel}
            </button>
          </div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
```

`web/src/components/ui/tabs.tsx`:
```tsx
import { Tabs as T } from "radix-ui";
import { cn } from "@/lib/utils";

export const Tabs = T.Root;
export function TabsList({ className, ...props }: React.ComponentProps<typeof T.List>) {
  return <T.List className={cn("inline-flex gap-1 rounded-[var(--radius-ui)] border border-border bg-bg-2 p-1", className)} {...props} />;
}
export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn("rounded-[6px] px-3 py-1.5 text-sm text-fg-2 data-[state=active]:bg-panel data-[state=active]:text-fg data-[state=active]:shadow-sm", className)}
      {...props}
    />
  );
}
export const TabsContent = T.Content;
```

`web/src/components/ui/select.tsx`:
```tsx
import { forwardRef, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const NativeSelect = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn("h-9 w-full rounded-[var(--radius-ui)] border border-border bg-panel px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40", className)}
    {...props}
  />
));
NativeSelect.displayName = "NativeSelect";
```

- [ ] **Step 5: Componentes de estado con test**

`web/src/components/states/Loading.tsx`:
```tsx
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n";

export function Loading({ rows = 4, label }: { rows?: number; label?: string }) {
  const t = useT();
  return (
    <div role="status" aria-label={label ?? t("state.loading")} className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
```

`web/src/components/states/Empty.tsx`:
```tsx
import type { ReactNode } from "react";
import { Tray } from "@phosphor-icons/react";

export function Empty({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[var(--radius-ui)] border border-dashed border-border px-6 py-14 text-center">
      <Tray size={28} weight="regular" className="text-muted" aria-hidden />
      <p className="mt-3 text-sm font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-[45ch] text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

`web/src/components/states/ErrorState.tsx`:
```tsx
import { WarningCircle } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { ApiError } from "@/api/client";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT();
  const message = error instanceof ApiError ? `${error.message} (${error.code})` : error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-start gap-3 rounded-[var(--radius-ui)] border border-sev-high/30 bg-sev-high/5 p-4">
      <WarningCircle size={20} className="mt-0.5 shrink-0 text-sev-high" aria-hidden />
      <div className="flex-1">
        <p className="text-sm font-medium text-fg">{t("state.error")}</p>
        <p className="mt-0.5 break-words text-sm text-fg-2">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {t("state.retry")}
        </Button>
      )}
    </div>
  );
}
```

`web/src/test/render.tsx`:
```tsx
import { render } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import type { ReactNode } from "react";
import { I18nProvider } from "@/lib/i18n";
import { createQueryClient } from "@/lib/query";

export function renderWithProviders(ui: ReactNode, opts: { route?: string } = {}) {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initial="es">
        <MemoryRouter initialEntries={[opts.route ?? "/"]}>{ui}</MemoryRouter>
      </I18nProvider>
    </QueryClientProvider>,
  );
}
```

`web/src/components/states/states.test.tsx`:
```tsx
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { Loading } from "./Loading";
import { Empty } from "./Empty";
import { ErrorState } from "./ErrorState";
import { ApiError } from "@/api/client";

test("Loading expone role=status con etiqueta", () => {
  renderWithProviders(<Loading rows={2} />);
  expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
});

test("Empty muestra título, descripción y acción", () => {
  renderWithProviders(<Empty title="Sin geocercas" description="Crea la primera" action={<button>Crear</button>} />);
  expect(screen.getByText("Sin geocercas")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Crear" })).toBeInTheDocument();
});

test("ErrorState muestra el código de la API y reintenta", () => {
  const retry = vi.fn();
  renderWithProviders(<ErrorState error={new ApiError(403, "forbidden", "sin permiso")} onRetry={retry} />);
  expect(screen.getByRole("alert")).toHaveTextContent("sin permiso (forbidden)");
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(retry).toHaveBeenCalled();
});
```

- [ ] **Step 6: Verificar, sincronía del esquema generado, commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && npm run gen:api && git diff --exit-code src/api/schema.d.ts && cd ..
```

Expected: verde y sin diff en `schema.d.ts`. Añadir en `.github/workflows/ci.yml`, job `web`, tras `npm ci`: `- run: npm run gen:api && git diff --exit-code src/api/schema.d.ts`.

```bash
git add web internal/arch/allowlist_npm.txt .github/workflows/ci.yml
git commit -q -m "feat(web): base del dashboard: primitivas UI propias, i18n ES/EN, permisos, estados y cliente API tipado desde OpenAPI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 16: Shell, router, tema y guard de autenticación

**Files:**
- Create: `web/src/app/theme.tsx`, `web/src/app/nav.ts`, `web/src/app/Shell.tsx`, `web/src/app/AuthGate.tsx`, `web/src/app/router.tsx`, `web/src/app/AuthGate.test.tsx`, `web/src/app/Shell.test.tsx`
- Modify: `web/src/app/App.tsx`, `web/src/app/App.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  // theme.tsx
  export function ThemeProvider({ children }); export function useTheme(): { theme: "light" | "dark"; toggle: () => void }
  // nav.ts
  export const navItems: { to: string; key: Key; icon: Icon }[]   // "/", "/map", "/devices", "/fences"
  // AuthGate.tsx: envuelve rutas privadas; setup_required → <Navigate to="/setup" />; me === null → <Navigate to="/login" />; cargando → <Loading />
  // router.tsx: export const router = createBrowserRouter([...]); rutas: /setup, /login, y bajo AuthGate+Shell: / (overview), /map, /devices, /devices/:id, /fences, /fences/new, /fences/:id
  ```
  Las páginas de features llegan en Tasks 17-21; en esta tarea se registran como placeholders mínimos `export function OverviewPage() { return <h1>...</h1> }` en `web/src/features/<x>/<X>Page.tsx` que las tareas siguientes sustituyen.

- [ ] **Step 1: Tests (fallan)**

`web/src/app/AuthGate.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { AuthGate } from "./AuthGate";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useAuthStatus: vi.fn(), useMe: vi.fn() }));

function tree() {
  return (
    <Routes>
      <Route path="/setup" element={<p>SETUP</p>} />
      <Route path="/login" element={<p>LOGIN</p>} />
      <Route element={<AuthGate />}>
        <Route path="/" element={<p>PRIVADO</p>} />
      </Route>
    </Routes>
  );
}

test("redirige a /setup si falta el asistente", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: { setup_required: true }, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: null, isPending: false, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByText("SETUP")).toBeInTheDocument();
});

test("redirige a /login sin sesión", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: { setup_required: false }, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: null, isPending: false, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByText("LOGIN")).toBeInTheDocument();
});

test("muestra el contenido con sesión", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: { setup_required: false }, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { user: { role: "owner" }, csrf: "x", capabilities: [] }, isPending: false, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByText("PRIVADO")).toBeInTheDocument();
});

test("muestra cargando mientras resuelve", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: undefined, isPending: true, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: undefined, isPending: true, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByRole("status")).toBeInTheDocument();
});
```

`web/src/app/Shell.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { Shell } from "./Shell";
import { ThemeProvider } from "./theme";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useMe: vi.fn(), useLogout: vi.fn() }));

test("el shell muestra la navegación y el usuario", () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { user: { name: "Adri", email: "a@x.com", role: "owner", org: "default" }, csrf: "x", capabilities: [] } } as never);
  vi.mocked(hooks.useLogout).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  renderWithProviders(
    <ThemeProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<p>HOME</p>} />
        </Route>
      </Routes>
    </ThemeProvider>,
  );
  for (const label of ["Visión general", "Mapa", "Dispositivos", "Geocercas"]) {
    expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
  }
  expect(screen.getByText("Adri")).toBeInTheDocument();
  expect(screen.getByText("HOME")).toBeInTheDocument();
});
```

- [ ] **Step 2: Implementar tema, nav, shell, gate y router**

`web/src/app/theme.tsx`:
```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Theme = "light" | "dark";
const ThemeContext = createContext<{ theme: Theme; toggle: () => void } | null>(null);

function initial(): Theme {
  try {
    const saved = localStorage.getItem("lf.theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* sin storage */
  }
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem("lf.theme", theme);
    } catch {
      /* sin storage */
    }
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme fuera de ThemeProvider");
  return ctx;
}
```

`web/src/app/nav.ts`:
```ts
import { SquaresFour, MapTrifold, DeviceMobile, Polygon, type Icon } from "@phosphor-icons/react";
import type { Key } from "@/lib/i18n";

export const navItems: { to: string; key: Key; icon: Icon }[] = [
  { to: "/", key: "nav.overview", icon: SquaresFour },
  { to: "/map", key: "nav.map", icon: MapTrifold },
  { to: "/devices", key: "nav.devices", icon: DeviceMobile },
  { to: "/fences", key: "nav.fences", icon: Polygon },
];
```

`web/src/app/Shell.tsx`:
```tsx
import { NavLink, Outlet } from "react-router";
import { Moon, Sun, SignOut, Translate } from "@phosphor-icons/react";
import { navItems } from "./nav";
import { useTheme } from "./theme";
import { useT, useLang } from "@/lib/i18n";
import { useMe, useLogout } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Shell() {
  const t = useT();
  const { lang, setLang } = useLang();
  const { theme, toggle } = useTheme();
  const me = useMe();
  const logout = useLogout();
  const user = me.data?.user;
  return (
    <div className="grid min-h-dvh grid-cols-1 md:grid-cols-[232px_1fr]">
      <aside className="border-b border-border bg-panel md:border-b-0 md:border-r">
        <div className="flex h-16 items-center px-5 text-base font-semibold tracking-tight">{t("app.name")}</div>
        <nav aria-label="principal" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {navItems.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn("flex items-center gap-2.5 rounded-[var(--radius-ui)] px-3 py-2 text-sm text-fg-2 hover:bg-bg-2 hover:text-fg", isActive && "bg-accent/10 text-accent")
              }
            >
              <Icon size={18} weight="regular" aria-hidden />
              {t(key)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-panel px-6">
          <span className="text-sm text-muted">{user?.org}</span>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" aria-label={t("lang.toggle")} onClick={() => setLang(lang === "es" ? "en" : "es")}>
              <Translate size={18} aria-hidden />
            </Button>
            <Button variant="ghost" size="icon" aria-label={t("theme.toggle")} onClick={toggle}>
              {theme === "dark" ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
            </Button>
            {user && <span className="ml-2 text-sm font-medium">{user.name}</span>}
            <Button variant="ghost" size="icon" aria-label={t("nav.logout")} onClick={() => logout.mutate()} disabled={logout.isPending}>
              <SignOut size={18} aria-hidden />
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

`web/src/app/AuthGate.tsx`:
```tsx
import { Navigate, Outlet } from "react-router";
import { useAuthStatus, useMe } from "@/api/hooks";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";

export function AuthGate() {
  const status = useAuthStatus();
  const me = useMe();
  if (status.isPending || me.isPending) return <Loading rows={3} />;
  if (status.error) return <ErrorState error={status.error} onRetry={() => status.refetch()} />;
  if (status.data?.setup_required) return <Navigate to="/setup" replace />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <Outlet />;
}
```

`web/src/app/router.tsx`:
```tsx
import { createBrowserRouter } from "react-router";
import { Shell } from "./Shell";
import { AuthGate } from "./AuthGate";
import { SetupPage } from "@/features/setup/SetupPage";
import { LoginPage } from "@/features/login/LoginPage";
import { OverviewPage } from "@/features/overview/OverviewPage";
import { MapPage } from "@/features/map/MapPage";
import { DevicesPage } from "@/features/devices/DevicesPage";
import { DeviceDetailPage } from "@/features/devices/DeviceDetailPage";
import { FencesPage } from "@/features/fences/FencesPage";
import { FenceEditorPage } from "@/features/fences/FenceEditorPage";

export const router = createBrowserRouter([
  { path: "/setup", element: <SetupPage /> },
  { path: "/login", element: <LoginPage /> },
  {
    element: <AuthGate />,
    children: [
      {
        element: <Shell />,
        children: [
          { path: "/", element: <OverviewPage /> },
          { path: "/map", element: <MapPage /> },
          { path: "/devices", element: <DevicesPage /> },
          { path: "/devices/:id", element: <DeviceDetailPage /> },
          { path: "/fences", element: <FencesPage /> },
          { path: "/fences/new", element: <FenceEditorPage /> },
          { path: "/fences/:id", element: <FenceEditorPage /> },
        ],
      },
    ],
  },
]);
```

`web/src/app/App.tsx`:
```tsx
import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { I18nProvider } from "@/lib/i18n";
import { createQueryClient } from "@/lib/query";
import { ThemeProvider } from "./theme";
import { router } from "./router";

export function App() {
  const [qc] = useState(createQueryClient);
  return (
    <QueryClientProvider client={qc}>
      <I18nProvider>
        <ThemeProvider>
          <RouterProvider router={router} />
        </ThemeProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
```

`web/src/app/App.test.tsx` (sustituir):
```tsx
import { render } from "@testing-library/react";
import { App } from "./App";

test("App monta sin errores", () => {
  const { container } = render(<App />);
  expect(container).toBeTruthy();
});
```

Placeholders de páginas (uno por fichero, misma forma; se sustituyen en Tasks 17-21):
```tsx
// web/src/features/setup/SetupPage.tsx
export function SetupPage() {
  return <h1>setup</h1>;
}
```
Ídem `features/login/LoginPage.tsx` (`LoginPage`), `features/overview/OverviewPage.tsx` (`OverviewPage`), `features/map/MapPage.tsx` (`MapPage`), `features/devices/DevicesPage.tsx` (`DevicesPage`), `features/devices/DeviceDetailPage.tsx` (`DeviceDetailPage`), `features/fences/FencesPage.tsx` (`FencesPage`), `features/fences/FenceEditorPage.tsx` (`FenceEditorPage`).

- [ ] **Step 3: Verificar y commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && cd ..
git add web
git commit -q -m "feat(web): shell con navegación, tema claro/oscuro, router y guard de autenticación

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 17: Asistente inicial y login

**Files:**
- Create: `web/src/features/setup/SetupPage.tsx`, `web/src/features/setup/SetupPage.test.tsx`, `web/src/features/login/LoginPage.tsx`, `web/src/features/login/LoginPage.test.tsx`, `web/src/features/auth/AuthLayout.tsx`

- [ ] **Step 1: Tests (fallan)**

`web/src/features/setup/SetupPage.test.tsx`:
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { SetupPage } from "./SetupPage";
import * as hooks from "@/api/hooks";

const navigate = vi.fn();
vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => navigate }));
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useSetup: vi.fn() }));

test("valida campos y envía en modo demo", async () => {
  const mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(hooks.useSetup).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(<SetupPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Crear cuenta y entrar" }));
  expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
  expect(mutateAsync).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText("Email"), "adri@example.com");
  await user.type(screen.getByLabelText("Nombre"), "Adri");
  await user.type(screen.getByLabelText("Contraseña (mínimo 10 caracteres)"), "contraseña-larga-1");
  await user.click(screen.getByLabelText("Demo local con flota simulada"));
  await user.click(screen.getByRole("button", { name: "Crear cuenta y entrar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ email: "adri@example.com", name: "Adri", password: "contraseña-larga-1", mode: "demo" }));
  expect(navigate).toHaveBeenCalledWith("/", { replace: true });
});
```

`web/src/features/login/LoginPage.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { LoginPage } from "./LoginPage";
import { ApiError } from "@/api/client";
import * as hooks from "@/api/hooks";

vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => vi.fn() }));
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useLogin: vi.fn() }));

test("muestra el error de credenciales de la API", async () => {
  const mutateAsync = vi.fn().mockRejectedValue(new ApiError(401, "invalid_credentials", "email o contraseña incorrectos"));
  vi.mocked(hooks.useLogin).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(<LoginPage />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), "a@x.com");
  await user.type(screen.getByLabelText("Contraseña"), "lo-que-sea-largo");
  await user.click(screen.getByRole("button", { name: "Entrar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos");
});
```

- [ ] **Step 2: Implementar layout, setup y login**

`web/src/features/auth/AuthLayout.tsx`:
```tsx
import type { ReactNode } from "react";
import { useT } from "@/lib/i18n";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  const t = useT();
  return (
    <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <section className="flex flex-col justify-center px-8 py-12 lg:px-16">
        <p className="text-sm font-semibold text-accent">{t("app.name")}</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-2 max-w-[48ch] text-sm text-muted">{subtitle}</p>}
        <div className="mt-8 max-w-md">{children}</div>
      </section>
      <aside className="hidden bg-bg-2 lg:block" aria-hidden />
    </div>
  );
}
```

`web/src/features/setup/SetupPage.tsx`:
```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/states/ErrorState";
import { useSetup } from "@/api/hooks";
import { useT } from "@/lib/i18n";

const schema = z.object({
  email: z.email(),
  name: z.string().trim().min(1),
  password: z.string().min(10),
  mode: z.enum(["demo", "empty"]),
});
type Form = z.infer<typeof schema>;

export function SetupPage() {
  const t = useT();
  const navigate = useNavigate();
  const setup = useSetup();
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { email: "", name: "", password: "", mode: "demo" } });
  const errors = form.formState.errors;
  const onSubmit = form.handleSubmit(async (values) => {
    await setup.mutateAsync(values);
    navigate("/", { replace: true });
  });
  return (
    <AuthLayout title={t("setup.title")} subtitle={t("setup.subtitle")}>
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <Field label={t("setup.email")} id="email" error={errors.email && "email"}>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...form.register("email")} />
        </Field>
        <Field label={t("setup.name")} id="name" error={errors.name && "name"}>
          <Input id="name" autoComplete="name" aria-invalid={!!errors.name} {...form.register("name")} />
        </Field>
        <Field label={t("setup.password")} id="password" error={errors.password && "password"}>
          <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...form.register("password")} />
        </Field>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-fg-2">{t("setup.mode")}</legend>
          {(["demo", "empty"] as const).map((m) => (
            <label key={m} className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-ui)] border border-border p-3 has-[:checked]:border-accent has-[:checked]:bg-accent/5">
              <input type="radio" value={m} className="mt-1" {...form.register("mode")} />
              <span>
                <span className="block text-sm font-medium">{t(`setup.mode.${m}`)}</span>
                <span className="block text-sm text-muted">{t(`setup.mode.${m}.help`)}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {setup.error && <ErrorState error={setup.error} />}
        <Button type="submit" size="lg" className="w-full" disabled={setup.isPending}>
          {t("setup.submit")}
        </Button>
      </form>
    </AuthLayout>
  );
}

export function Field({ label, id, error, children }: { label: string; id: string; error?: string | false; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error && (
        <p role="alert" className="text-xs text-sev-high">
          {label}
        </p>
      )}
    </div>
  );
}
```

`web/src/features/login/LoginPage.tsx`:
```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { Field } from "@/features/setup/SetupPage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/api/client";
import { useLogin } from "@/api/hooks";
import { useT } from "@/lib/i18n";

const schema = z.object({ email: z.email(), password: z.string().min(1) });
type Form = z.infer<typeof schema>;

export function LoginPage() {
  const t = useT();
  const navigate = useNavigate();
  const login = useLogin();
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });
  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      navigate("/", { replace: true });
    } catch {
      /* el error se muestra desde login.error */
    }
  });
  const err = login.error;
  const message = err instanceof ApiError ? (err.code === "throttled" ? t("login.throttled") : t("login.invalid")) : err ? String(err) : null;
  return (
    <AuthLayout title={t("login.title")}>
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <Field label={t("login.email")} id="email" error={form.formState.errors.email && "email"}>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label={t("login.password")} id="password" error={form.formState.errors.password && "password"}>
          <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
        </Field>
        {message && (
          <p role="alert" className="rounded-[var(--radius-ui)] border border-sev-high/30 bg-sev-high/5 p-3 text-sm text-fg">
            {message}
          </p>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={login.isPending}>
          {t("login.submit")}
        </Button>
      </form>
    </AuthLayout>
  );
}
```

- [ ] **Step 3: Verificar y commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && cd ..
git add web
git commit -q -m "feat(web): asistente inicial (owner + demo/vacío) y login con errores de la API

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 18: Visión general

**Files:**
- Create: `web/src/features/overview/OverviewPage.tsx`, `web/src/features/overview/Kpi.tsx`, `web/src/features/overview/EngineCard.tsx`, `web/src/features/overview/OverviewPage.test.tsx`

- [ ] **Step 1: Test (falla)**

`web/src/features/overview/OverviewPage.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { OverviewPage } from "./OverviewPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useDevices: vi.fn(), useEngineStatus: vi.fn(), useEvents: vi.fn(), useRunOnce: vi.fn(), useMe: vi.fn(),
}));

const device = (id: string, fence_state: string, compliant: boolean | null) => ({ id, name: id, fence_state, compliant });

function mock(over: Partial<Record<"devices" | "engine" | "events", unknown>> = {}) {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items: [device("a", "inside", true), device("b", "outside", false), device("c", "unknown", null)], total: 3 }, isPending: false, error: null, refetch: vi.fn(), ...(over.devices as object) } as never);
  vi.mocked(hooks.useEngineStatus).mockReturnValue({ data: { mode: "simulation", enforcement: "observe", interval_seconds: 900, running: true, cycles: 2, providers: { simulation: { ok: true, devices: 3, latency_ms: 4 } }, last_cycle: { at: "2026-09-05T12:00:00Z" } }, isPending: false, error: null, ...(over.engine as object) } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({ data: { items: [{ at: "2026-09-05T12:00:00Z", device_id: "a", device_name: "a", from: "none:unknown", to: "demo-hq:inside" }] }, isPending: false, error: null, ...(over.events as object) } as never);
  vi.mocked(hooks.useRunOnce).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["engine:run"] } } as never);
}

test("contenido: KPIs, motor, transiciones y proveedores", () => {
  mock();
  renderWithProviders(<OverviewPage />);
  expect(screen.getByText("Dispositivos").nextSibling).toHaveTextContent("3");
  expect(screen.getByText("Dentro").nextSibling).toHaveTextContent("1");
  expect(screen.getByText("Cumplimiento").nextSibling).toHaveTextContent("33 %");
  expect(screen.getByRole("button", { name: "Ejecutar ciclo ahora" })).toBeEnabled();
  expect(screen.getByText("demo-hq:inside")).toBeInTheDocument();
  expect(screen.getByText("simulation")).toBeInTheDocument();
});

test("cargando, vacío y error", () => {
  mock({ devices: { data: undefined, isPending: true }, events: { data: { items: [] } }, engine: { data: undefined, error: new Error("boom"), isPending: false } });
  renderWithProviders(<OverviewPage />);
  expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  expect(screen.getByText("Aún no hay transiciones. Ejecuta un ciclo.")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("boom");
});

test("sin engine:run no se muestra el botón", () => {
  mock();
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: [] } } as never);
  renderWithProviders(<OverviewPage />);
  expect(screen.queryByRole("button", { name: "Ejecutar ciclo ahora" })).toBeNull();
});
```

- [ ] **Step 2: Implementar**

`web/src/features/overview/Kpi.tsx`:
```tsx
export function Kpi({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "neutral" | "success" | "warning" | "danger" }) {
  const color = { neutral: "text-fg", success: "text-sev-low", warning: "text-sev-medium", danger: "text-sev-high" }[tone];
  return (
    <div className="rounded-[var(--radius-ui)] border border-border bg-panel px-5 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-3xl font-semibold tabular-nums tracking-tight ${color}`}>{value}</p>
    </div>
  );
}
```

`web/src/features/overview/EngineCard.tsx`:
```tsx
import { Play } from "@phosphor-icons/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useEngineStatus, useRunOnce, useMe } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";
import { can } from "@/lib/permissions";

export function EngineCard() {
  const t = useT();
  const { lang } = useLang();
  const status = useEngineStatus();
  const run = useRunOnce();
  const me = useMe();
  const canRun = can(me.data?.capabilities, "engine:run");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("overview.engine")}</CardTitle>
        {canRun && (
          <Button size="sm" variant="secondary" onClick={() => run.mutate()} disabled={run.isPending}>
            <Play size={14} aria-hidden />
            {run.isPending ? t("overview.engine.running") : t("overview.engine.run")}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {status.isPending && <Loading rows={3} />}
        {status.error && <ErrorState error={status.error} onRetry={() => status.refetch()} />}
        {status.data && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <dt className="text-muted">{t("overview.engine.mode")}</dt>
            <dd>{status.data.mode}</dd>
            <dt className="text-muted">{t("overview.engine.enforcement")}</dt>
            <dd>
              <Badge variant="info">{status.data.enforcement}</Badge>
            </dd>
            <dt className="text-muted">{t("overview.engine.interval")}</dt>
            <dd>{Math.round(status.data.interval_seconds / 60)} min</dd>
            <dt className="text-muted">{t("overview.engine.cycles")}</dt>
            <dd>{status.data.cycles}</dd>
            <dt className="text-muted">{t("overview.engine.lastCycle")}</dt>
            <dd>{formatDateTime(status.data.last_cycle?.at, lang)}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
```

`web/src/features/overview/OverviewPage.tsx`:
```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices, useEngineStatus, useEvents } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime, percent } from "@/lib/format";
import { Kpi } from "./Kpi";
import { EngineCard } from "./EngineCard";

export function OverviewPage() {
  const t = useT();
  const { lang } = useLang();
  const devices = useDevices();
  const events = useEvents(10);
  const engine = useEngineStatus();
  const items = devices.data?.items ?? [];
  const count = (s: string) => items.filter((d) => d.fence_state === s).length;
  const compliant = items.filter((d) => d.compliant === true).length;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("overview.title")}</h1>
      {devices.isPending && <Loading rows={2} />}
      {devices.error && <ErrorState error={devices.error} onRetry={() => devices.refetch()} />}
      {devices.data && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <Kpi label={t("overview.devices")} value={items.length} />
          <Kpi label={t("overview.inside")} value={count("inside")} tone="success" />
          <Kpi label={t("overview.outside")} value={count("outside")} tone="warning" />
          <Kpi label={t("overview.unknown")} value={count("unknown")} />
          <Kpi label={t("overview.compliance")} value={percent(compliant, items.length)} />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-6">
          <EngineCard />
          <Card>
            <CardHeader>
              <CardTitle>{t("overview.providers")}</CardTitle>
            </CardHeader>
            <CardContent>
              {engine.data && (
                <ul className="divide-y divide-border text-sm">
                  {Object.entries(engine.data.providers).map(([name, h]) => (
                    <li key={name} className="flex items-center justify-between py-2">
                      <span>{name}</span>
                      <span className="flex items-center gap-2 text-muted">
                        {h.devices} · {h.latency_ms} ms
                        <Badge variant={h.ok ? "success" : "danger"}>{h.ok ? "ok" : h.error}</Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{t("overview.events")}</CardTitle>
          </CardHeader>
          <CardContent>
            {events.isPending && <Loading rows={4} />}
            {events.error && <ErrorState error={events.error} onRetry={() => events.refetch()} />}
            {events.data && events.data.items.length === 0 && <Empty title={t("overview.noEvents")} />}
            {events.data && events.data.items.length > 0 && (
              <ul className="divide-y divide-border text-sm">
                {[...events.data.items].reverse().map((ev, i) => (
                  <li key={i} className="grid grid-cols-[1fr_auto] gap-2 py-2">
                    <span>
                      <span className="font-medium">{ev.device_name}</span> <span className="text-muted">{ev.from}</span> → <span>{ev.to}</span>
                    </span>
                    <span className="text-muted">{formatDateTime(ev.at, lang)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verificar y commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && cd ..
git add web
git commit -q -m "feat(web): visión general con KPIs, motor, proveedores y últimas transiciones

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 19: Mapa en vivo (MapLibre)

**Files:**
- Create: `web/src/lib/geo.ts`, `web/src/lib/geo.test.ts`, `web/src/components/map/FleetMap.tsx`, `web/src/components/map/style.ts`, `web/src/features/map/MapPage.tsx`, `web/src/features/map/MapPage.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  // lib/geo.ts
  export function circleToPolygon(center: { lat: number; lng: number }, radiusM: number, steps = 64): [number, number][]  // anillo cerrado [lng, lat]
  export function fencesToGeoJSON(fences: Fence[]): GeoJSON.FeatureCollection
  export function devicesToGeoJSON(devices: Device[]): GeoJSON.FeatureCollection   // solo con location.point; properties {id, name, fence_state}
  // components/map/style.ts
  export function rasterStyle(tilesUrl: string): maplibregl.StyleSpecification
  // components/map/FleetMap.tsx
  export function FleetMap({ fences, devices, tilesUrl, onDeviceClick? }): JSX.Element  // div.h-full; capas "fences-fill", "fences-line", "devices"
  ```

- [ ] **Step 1: Tests (fallan)**

`web/src/lib/geo.test.ts`:
```ts
import { circleToPolygon, fencesToGeoJSON, devicesToGeoJSON } from "./geo";
import type { Device, Fence } from "@/api/hooks";

test("circleToPolygon devuelve un anillo cerrado de steps+1 puntos alrededor del centro", () => {
  const ring = circleToPolygon({ lat: 40.421, lng: -3.708 }, 500, 8);
  expect(ring).toHaveLength(9);
  expect(ring[0]).toEqual(ring[8]);
  for (const [lng, lat] of ring) {
    expect(Math.abs(lat - 40.421)).toBeLessThan(0.006);
    expect(Math.abs(lng + 3.708)).toBeLessThan(0.008);
  }
});

test("fencesToGeoJSON convierte círculos y polígonos", () => {
  const fences = [
    { id: "c", name: "C", kind: "circle", center: { lat: 1, lng: 2 }, radius_m: 100, rules: {}, actions: [] },
    { id: "p", name: "P", kind: "polygon", polygon: [{ lat: 0, lng: 0 }, { lat: 0, lng: 1 }, { lat: 1, lng: 1 }], rules: {}, actions: [] },
  ] as unknown as Fence[];
  const fc = fencesToGeoJSON(fences);
  expect(fc.features).toHaveLength(2);
  expect(fc.features[1].geometry).toEqual({ type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] });
});

test("devicesToGeoJSON omite dispositivos sin ubicación", () => {
  const devices = [
    { id: "a", name: "A", fence_state: "inside", location: { point: { lat: 1, lng: 2 } } },
    { id: "b", name: "B", fence_state: "unknown", location: {} },
  ] as unknown as Device[];
  const fc = devicesToGeoJSON(devices);
  expect(fc.features).toHaveLength(1);
  expect(fc.features[0].properties).toEqual({ id: "a", name: "A", fence_state: "inside" });
});
```

`web/src/features/map/MapPage.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { MapPage } from "./MapPage";
import * as hooks from "@/api/hooks";

const mapInstances: unknown[] = [];
vi.mock("maplibre-gl", () => {
  class Map {
    handlers: Record<string, () => void> = {};
    constructor(public opts: unknown) { mapInstances.push(this); }
    on(ev: string, a: unknown, b?: unknown) { const fn = (typeof a === "function" ? a : b) as () => void; this.handlers[ev] = fn; if (ev === "load") fn(); }
    addSource() {} getSource() { return undefined; } addLayer() {} addControl() {} fitBounds() {} remove() {} getCanvas() { return { style: {} }; }
  }
  class Popup { setLngLat() { return this; } setHTML() { return this; } addTo() { return this; } }
  class NavigationControl {}
  class LngLatBounds { extend() { return this; } isEmpty() { return false; } }
  return { default: { Map, Popup, NavigationControl, LngLatBounds }, Map, Popup, NavigationControl, LngLatBounds };
});
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useHealth: vi.fn(), useFences: vi.fn(), useDevices: vi.fn() }));

function mock(mapEnabled: boolean) {
  vi.mocked(hooks.useHealth).mockReturnValue({ data: { map: { enabled: mapEnabled, tiles_url: "https://t/{z}/{x}/{y}.png" } }, isPending: false, error: null } as never);
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
}

test("renderiza leyenda y crea el mapa", () => {
  mock(true);
  renderWithProviders(<MapPage />);
  expect(screen.getByText("Dentro de geocerca")).toBeInTheDocument();
  expect(mapInstances.length).toBeGreaterThan(0);
});

test("mapa desactivado por configuración", () => {
  mock(false);
  renderWithProviders(<MapPage />);
  expect(screen.getByText(/map.enabled=false/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Implementar**

`web/src/lib/geo.ts`:
```ts
import type { Device, Fence } from "@/api/hooks";

const EARTH_M = 6_371_000;

export function circleToPolygon(center: { lat: number; lng: number }, radiusM: number, steps = 64): [number, number][] {
  const ring: [number, number][] = [];
  const dLat = (radiusM / EARTH_M) * (180 / Math.PI);
  const dLng = dLat / Math.cos((center.lat * Math.PI) / 180);
  for (let i = 0; i < steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    ring.push([center.lng + dLng * Math.cos(a), center.lat + dLat * Math.sin(a)]);
  }
  ring.push(ring[0]);
  return ring;
}

export function fencesToGeoJSON(fences: Fence[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: fences.map((f) => {
      const ring =
        f.kind === "circle" && f.center
          ? circleToPolygon(f.center, f.radius_m ?? 0)
          : [...(f.polygon ?? []).map((p) => [p.lng, p.lat] as [number, number]), ...(f.polygon?.length ? [[f.polygon[0].lng, f.polygon[0].lat] as [number, number]] : [])];
      return { type: "Feature", properties: { id: f.id, name: f.name, kind: f.kind }, geometry: { type: "Polygon", coordinates: [ring] } };
    }),
  };
}

export function devicesToGeoJSON(devices: Device[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: devices
      .filter((d) => d.location?.point)
      .map((d) => ({
        type: "Feature",
        properties: { id: d.id, name: d.name, fence_state: d.fence_state },
        geometry: { type: "Point", coordinates: [d.location.point!.lng, d.location.point!.lat] },
      })),
  };
}
```

`web/src/components/map/style.ts`:
```ts
import type { StyleSpecification } from "maplibre-gl";

export function rasterStyle(tilesUrl: string): StyleSpecification {
  return {
    version: 8,
    sources: { osm: { type: "raster", tiles: [tilesUrl], tileSize: 256, attribution: "© OpenStreetMap contributors" } },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  };
}
```

`web/src/components/map/FleetMap.tsx`:
```tsx
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Device, Fence } from "@/api/hooks";
import { devicesToGeoJSON, fencesToGeoJSON } from "@/lib/geo";
import { rasterStyle } from "./style";

const colors = { inside: "#346538", outside: "#956400", unknown: "#5E635C" };

export function FleetMap({ fences, devices, tilesUrl, onDeviceClick }: { fences: Fence[]; devices: Device[]; tilesUrl: string; onDeviceClick?: (id: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const loaded = useRef(false);
  const fitted = useRef(false);

  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({ container: container.current, style: rasterStyle(tilesUrl), center: [-3.708, 40.421], zoom: 12, attributionControl: {} });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.on("load", () => {
      m.addSource("fences", { type: "geojson", data: fencesToGeoJSON([]) });
      m.addSource("devices", { type: "geojson", data: devicesToGeoJSON([]) });
      m.addLayer({ id: "fences-fill", type: "fill", source: "fences", paint: { "fill-color": "#3E7A5E", "fill-opacity": 0.12 } });
      m.addLayer({ id: "fences-line", type: "line", source: "fences", paint: { "line-color": "#3E7A5E", "line-width": 2 } });
      m.addLayer({
        id: "devices",
        type: "circle",
        source: "devices",
        paint: {
          "circle-radius": 7,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#FFFFFF",
          "circle-color": ["match", ["get", "fence_state"], "inside", colors.inside, "outside", colors.outside, colors.unknown],
        },
      });
      m.on("click", "devices", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as { id: string; name: string; fence_state: string };
        new maplibregl.Popup().setLngLat(e.lngLat).setHTML(`<strong>${p.name}</strong><br/>${p.fence_state}`).addTo(m);
        onDeviceClick?.(p.id);
      });
      m.on("mouseenter", "devices", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "devices", () => (m.getCanvas().style.cursor = ""));
      loaded.current = true;
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      loaded.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !loaded.current) return;
    const fSrc = m.getSource("fences") as maplibregl.GeoJSONSource | undefined;
    const dSrc = m.getSource("devices") as maplibregl.GeoJSONSource | undefined;
    fSrc?.setData(fencesToGeoJSON(fences));
    dSrc?.setData(devicesToGeoJSON(devices));
    if (!fitted.current && devices.some((d) => d.location?.point)) {
      const b = new maplibregl.LngLatBounds();
      for (const d of devices) if (d.location?.point) b.extend([d.location.point.lng, d.location.point.lat]);
      m.fitBounds(b, { padding: 60, maxZoom: 14, duration: 0 });
      fitted.current = true;
    }
  }, [fences, devices]);

  return <div ref={container} className="h-full min-h-[520px] w-full rounded-[var(--radius-ui)] border border-border" />;
}
```

`web/src/features/map/MapPage.tsx`:
```tsx
import { useNavigate } from "react-router";
import { FleetMap } from "@/components/map/FleetMap";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices, useFences, useHealth } from "@/api/hooks";
import { useT } from "@/lib/i18n";

const legend = [
  { key: "map.legend.inside", color: "#346538" },
  { key: "map.legend.outside", color: "#956400" },
  { key: "map.legend.unknown", color: "#5E635C" },
] as const;

export function MapPage() {
  const t = useT();
  const navigate = useNavigate();
  const health = useHealth();
  const fences = useFences();
  const devices = useDevices();
  const error = health.error ?? fences.error ?? devices.error;
  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("map.title")}</h1>
        <ul className="flex gap-4 text-sm text-fg-2">
          {legend.map((l) => (
            <li key={l.key} className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full" style={{ background: l.color }} aria-hidden />
              {t(l.key)}
            </li>
          ))}
        </ul>
      </div>
      {error && <ErrorState error={error} />}
      {(health.isPending || fences.isPending || devices.isPending) && <Loading rows={6} />}
      {health.data && !health.data.map.enabled && <p className="text-sm text-muted">{t("map.disabled")}</p>}
      {health.data?.map.enabled && fences.data && devices.data && (
        <div className="min-h-0 flex-1">
          <FleetMap fences={fences.data.items} devices={devices.data.items} tilesUrl={health.data.map.tiles_url} onDeviceClick={(id) => navigate(`/devices/${id}`)} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verificar y commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && cd ..
git add web
git commit -q -m "feat(web): mapa en vivo con MapLibre (geocercas, dispositivos por estado, popups)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 20: Dispositivos: lista y detalle

**Files:**
- Create: `web/src/components/StateBadge.tsx`, `web/src/features/devices/DevicesPage.tsx`, `web/src/features/devices/DeviceDetailPage.tsx`, `web/src/features/devices/DevicesPage.test.tsx`, `web/src/features/devices/DeviceDetailPage.test.tsx`

- [ ] **Step 1: Tests (fallan)**

`web/src/features/devices/DevicesPage.test.tsx`:
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { DevicesPage } from "./DevicesPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useDevices: vi.fn() }));

const items = [
  { id: "dev-001", name: "Tablet Campo A1", platform: "android", fence_state: "inside", inventory: { assigned_user: "Lucía" }, last_report_at: "2026-09-05T12:00:00Z" },
  { id: "dev-004", name: "Portátil Ventas", platform: "macos", fence_state: "outside", inventory: { assigned_user: "Sara" }, last_report_at: "2026-09-05T12:00:00Z" },
];

test("lista, filtra por estado y busca", async () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items, total: 2 }, isPending: false, error: null } as never);
  renderWithProviders(<DevicesPage />);
  expect(screen.getByRole("link", { name: /Tablet Campo A1/ })).toHaveAttribute("href", "/devices/dev-001");
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "dentro" }));
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "inside", q: "" }));
  await user.type(screen.getByRole("searchbox"), "sara");
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "inside", q: "sara" }));
});

test("vacío y error", () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  const { unmount } = renderWithProviders(<DevicesPage />);
  expect(screen.getByText("Sin dispositivos. Ejecuta un ciclo del motor.")).toBeInTheDocument();
  unmount();
  vi.mocked(hooks.useDevices).mockReturnValue({ data: undefined, isPending: false, error: new Error("caído"), refetch: vi.fn() } as never);
  renderWithProviders(<DevicesPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("caído");
});
```

`web/src/features/devices/DeviceDetailPage.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { DeviceDetailPage } from "./DeviceDetailPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useDevice: vi.fn(), useDeviceTrail: vi.fn(), useEvents: vi.fn() }));

test("muestra inventario, riesgo pendiente, recorrido y transiciones del dispositivo", () => {
  vi.mocked(hooks.useDevice).mockReturnValue({
    data: { id: "dev-001", name: "Tablet Campo A1", platform: "android", fence_state: "inside", inside_fence: "demo-hq", route_state: "unassigned", last_report_at: "2026-09-05T12:00:00Z",
      inventory: { os_version: "Android 14", model: "Samsung Galaxy Tab Active5", serial_number: "RZ8T", battery_level: 87, storage_total_gb: 128, storage_free_gb: 64.5, encryption_enabled: true, assigned_user: "Lucía", department: "Operaciones" },
      risk: { score: null, severity: "", reasons: [], matched_policies: [], provenance: "", verified: false }, location: { point: { lat: 40.42, lng: -3.71 } } },
    isPending: false, error: null } as never);
  vi.mocked(hooks.useDeviceTrail).mockReturnValue({ data: { items: [{ at: "2026-09-05T12:00:00Z", point: { lat: 40.42, lng: -3.71 } }] }, isPending: false, error: null } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({ data: { items: [{ at: "2026-09-05T12:00:00Z", device_id: "dev-001", device_name: "x", from: "none:unknown", to: "demo-hq:inside" }, { at: "2026-09-05T12:00:00Z", device_id: "dev-002", device_name: "y", from: "a", to: "b" }] }, isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/devices/:id" element={<DeviceDetailPage />} />
    </Routes>,
    { route: "/devices/dev-001" },
  );
  expect(screen.getByRole("heading", { name: "Tablet Campo A1" })).toBeInTheDocument();
  expect(screen.getByText("Samsung Galaxy Tab Active5")).toBeInTheDocument();
  expect(screen.getByText("87 %")).toBeInTheDocument();
  expect(screen.getByText(/Sin evaluar/)).toBeInTheDocument();
  expect(screen.getByText("demo-hq:inside")).toBeInTheDocument();
  expect(screen.queryByText("b")).toBeNull();
});
```

- [ ] **Step 2: Implementar**

`web/src/components/StateBadge.tsx`:
```tsx
import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";

const variant = { inside: "success", outside: "warning", unknown: "neutral" } as const;

export function StateBadge({ state }: { state: "inside" | "outside" | "unknown" | string }) {
  const t = useT();
  const s = (state === "inside" || state === "outside" ? state : "unknown") as keyof typeof variant;
  return <Badge variant={variant[s]}>{t(`state.${s}`)}</Badge>;
}
```

`web/src/features/devices/DevicesPage.tsx`:
```tsx
import { useState } from "react";
import { Link } from "react-router";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { StateBadge } from "@/components/StateBadge";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

const states = ["", "inside", "outside", "unknown"] as const;

export function DevicesPage() {
  const t = useT();
  const { lang } = useLang();
  const [state, setState] = useState<string>("");
  const [q, setQ] = useState("");
  const devices = useDevices({ state, q });
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-tight">{t("devices.title")}</h1>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Tabs value={state} onValueChange={setState}>
          <TabsList>
            {states.map((s) => (
              <TabsTrigger key={s} value={s}>
                {s === "" ? t("devices.filter.all") : t(`state.${s}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative md:w-80">
          <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-2.5 text-muted" aria-hidden />
          <Input type="search" role="searchbox" placeholder={t("devices.search")} value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
      </div>
      {devices.isPending && <Loading rows={6} />}
      {devices.error && <ErrorState error={devices.error} onRetry={() => devices.refetch()} />}
      {devices.data && devices.data.items.length === 0 && <Empty title={t("devices.empty")} />}
      {devices.data && devices.data.items.length > 0 && (
        <Table>
          <THead>
            <tr>
              <TH>{t("devices.col.name")}</TH>
              <TH>{t("devices.col.platform")}</TH>
              <TH>{t("devices.col.state")}</TH>
              <TH>{t("devices.col.user")}</TH>
              <TH>{t("devices.col.lastReport")}</TH>
            </tr>
          </THead>
          <TBody>
            {devices.data.items.map((d) => (
              <TR key={d.id}>
                <TD>
                  <Link to={`/devices/${d.id}`} className="font-medium text-fg hover:text-accent">
                    {d.name}
                  </Link>
                  <span className="ml-2 font-mono text-xs text-muted">{d.id}</span>
                </TD>
                <TD>{d.platform}</TD>
                <TD>
                  <StateBadge state={d.fence_state} />
                  {d.inside_fence && <span className="ml-2 text-xs text-muted">{d.inside_fence}</span>}
                </TD>
                <TD>{d.inventory?.assigned_user ?? "-"}</TD>
                <TD className="text-muted">{formatDateTime(d.last_report_at, lang)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </div>
  );
}
```

`web/src/features/devices/DeviceDetailPage.tsx`:
```tsx
import { Link, useParams } from "react-router";
import { ArrowLeft } from "@phosphor-icons/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StateBadge } from "@/components/StateBadge";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevice, useDeviceTrail, useEvents } from "@/api/hooks";
import { useT, useLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/format";

export function DeviceDetailPage() {
  const { id = "" } = useParams();
  const t = useT();
  const { lang } = useLang();
  const device = useDevice(id);
  const trail = useDeviceTrail(id, 20);
  const events = useEvents(200);
  if (device.isPending) return <Loading rows={6} />;
  if (device.error) return <ErrorState error={device.error} onRetry={() => device.refetch()} />;
  const d = device.data!;
  const inv = d.inventory ?? {};
  const yesNo = (v: boolean | undefined) => (v == null ? t("common.unknown") : v ? t("common.yes") : t("common.no"));
  const fields: [string, string][] = [
    [t("device.field.os"), inv.os_version ?? "-"],
    [t("device.field.model"), inv.model ?? "-"],
    [t("device.field.serial"), inv.serial_number ?? "-"],
    [t("device.field.battery"), inv.battery_level != null ? `${inv.battery_level} %` : "-"],
    [t("device.field.storage"), inv.storage_total_gb != null ? `${inv.storage_free_gb ?? "?"} / ${inv.storage_total_gb} GB` : "-"],
    [t("device.field.encryption"), yesNo(inv.encryption_enabled)],
    [t("device.field.user"), inv.assigned_user ?? "-"],
    [t("device.field.department"), inv.department ?? "-"],
    [t("device.field.route"), d.route_id ? `${d.route_id} (${d.route_state})` : "-"],
  ];
  const mine = (events.data?.items ?? []).filter((e) => e.device_id === id).reverse();
  return (
    <div className="space-y-6">
      <Link to="/devices" className="inline-flex items-center gap-1 text-sm text-fg-2 hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> {t("device.back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{d.name}</h1>
        <span className="font-mono text-sm text-muted">{d.id}</span>
        <span className="text-sm text-muted">{d.platform}</span>
        <StateBadge state={d.fence_state} />
        {d.inside_fence && <span className="text-sm text-muted">{d.inside_fence}</span>}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("device.inventory")}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
              {fields.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-border py-1.5">
                  <dt className="text-muted">{k}</dt>
                  <dd className="text-right">{v}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("device.risk")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted">{d.risk?.score == null ? t("device.risk.pending") : `${d.risk.score} · ${d.risk.severity}`}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("device.trail")}</CardTitle>
          </CardHeader>
          <CardContent>
            {trail.isPending && <Loading rows={3} />}
            {trail.data && (
              <ul className="space-y-1 font-mono text-xs text-fg-2">
                {[...trail.data.items].reverse().map((p, i) => (
                  <li key={i}>
                    {formatDateTime(p.at, lang)} · {p.point.lat.toFixed(5)}, {p.point.lng.toFixed(5)}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("device.events")}</CardTitle>
          </CardHeader>
          <CardContent>
            {events.isPending && <Loading rows={3} />}
            {events.data && (
              <ul className="divide-y divide-border text-sm">
                {mine.map((ev, i) => (
                  <li key={i} className="flex justify-between py-2">
                    <span>
                      <span className="text-muted">{ev.from}</span> → {ev.to}
                    </span>
                    <span className="text-muted">{formatDateTime(ev.at, lang)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verificar y commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && cd ..
git add web
git commit -q -m "feat(web): dispositivos con filtros, búsqueda y detalle con inventario, recorrido y transiciones

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 21: Geocercas: lista y editor

**Files:**
- Create: `web/src/lib/slug.ts`, `web/src/lib/slug.test.ts`, `web/src/features/fences/fenceForm.ts`, `web/src/features/fences/fenceForm.test.ts`, `web/src/features/fences/FencesPage.tsx`, `web/src/features/fences/FencesPage.test.tsx`, `web/src/features/fences/FenceEditorPage.tsx`, `web/src/features/fences/FenceEditorPage.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export function slugify(s: string): string   // "Demo HQ · Madrid" → "demo-hq-madrid"
  // fenceForm.ts
  export const actionValues = ["message","notify","locate","lock","reboot","clear_passcode","wipe","set_compliance","custom"] as const
  export const whenValues = ["on_enter","on_exit","on_violation","on_unknown"] as const
  export const fenceFormSchema: z.ZodType<FenceForm>; export type FenceForm
  export function parsePolygon(text: string): { lat: number; lng: number }[] | null
  export function toFence(form: FenceForm): Fence; export function fromFence(f: Fence): FenceForm; export const emptyForm: FenceForm
  ```

- [ ] **Step 1: Tests (fallan)**

`web/src/lib/slug.test.ts`:
```ts
import { slugify } from "./slug";

test("slugify", () => {
  expect(slugify("Demo HQ · Madrid")).toBe("demo-hq-madrid");
  expect(slugify("  Almacén Sur  ")).toBe("almacen-sur");
  expect(slugify("---")).toBe("");
});
```

`web/src/features/fences/fenceForm.test.ts`:
```ts
import { fenceFormSchema, parsePolygon, toFence, fromFence, emptyForm } from "./fenceForm";

test("parsePolygon acepta 'lat, lng' por línea y rechaza basura", () => {
  expect(parsePolygon("40.40, -3.72\n40.40,-3.70\n 40.44 , -3.70 ")).toEqual([{ lat: 40.4, lng: -3.72 }, { lat: 40.4, lng: -3.7 }, { lat: 40.44, lng: -3.7 }]);
  expect(parsePolygon("40.40, -3.72\nabc")).toBeNull();
  expect(parsePolygon("1,2\n3,4")).toBeNull();
});

test("schema exige centro y radio en círculo, y 3 vértices en polígono", () => {
  const circle = { ...emptyForm, name: "HQ", id: "hq", kind: "circle" as const, centerLat: 40.42, centerLng: -3.71, radiusM: 300 };
  expect(fenceFormSchema.safeParse(circle).success).toBe(true);
  expect(fenceFormSchema.safeParse({ ...circle, radiusM: 0 }).success).toBe(false);
  const poly = { ...emptyForm, name: "P", id: "p", kind: "polygon" as const, polygonText: "0,0\n0,1\n1,1" };
  expect(fenceFormSchema.safeParse(poly).success).toBe(true);
  expect(fenceFormSchema.safeParse({ ...poly, polygonText: "0,0\n0,1" }).success).toBe(false);
});

test("toFence y fromFence son inversas", () => {
  const form = { ...emptyForm, name: "HQ", id: "hq", kind: "circle" as const, centerLat: 40.42, centerLng: -3.71, radiusM: 300, actions: [{ action: "message" as const, when: "on_enter" as const, text: "hola", enabled: true }] };
  const fence = toFence(form);
  expect(fence).toMatchObject({ id: "hq", kind: "circle", center: { lat: 40.42, lng: -3.71 }, radius_m: 300, actions: [{ action: "message", when: "on_enter", enabled: true, params: { text: "hola" } }] });
  expect(fromFence(fence)).toMatchObject({ name: "HQ", id: "hq", kind: "circle", centerLat: 40.42, radiusM: 300, actions: [{ action: "message", text: "hola" }] });
});
```

`web/src/features/fences/FencesPage.test.tsx`:
```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { FencesPage } from "./FencesPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useFences: vi.fn(), useDeleteFence: vi.fn(), useMe: vi.fn() }));

test("lista, permisos y borrado con confirmación", async () => {
  const mutate = vi.fn();
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [{ id: "demo-hq", name: "Demo HQ", kind: "circle", actions: [{}, {}] }], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate, isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:write", "fence:delete"] } } as never);
  renderWithProviders(<FencesPage />);
  expect(screen.getByRole("link", { name: "Nueva geocerca" })).toHaveAttribute("href", "/fences/new");
  expect(screen.getByRole("link", { name: "Demo HQ" })).toHaveAttribute("href", "/fences/demo-hq");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  expect(await screen.findByText("¿Eliminar la geocerca Demo HQ?")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "Eliminar" }).at(-1)!);
  expect(mutate).toHaveBeenCalledWith("demo-hq");
});

test("sin permisos no hay botones y vacío tiene acción", () => {
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:read"] } } as never);
  renderWithProviders(<FencesPage />);
  expect(screen.getByText("Sin geocercas. Crea la primera.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Nueva geocerca" })).toBeNull();
});
```

`web/src/features/fences/FenceEditorPage.test.tsx`:
```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { FenceEditorPage } from "./FenceEditorPage";
import * as hooks from "@/api/hooks";

const navigate = vi.fn();
vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => navigate }));
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useFence: vi.fn(), useCreateFence: vi.fn(), useUpdateFence: vi.fn() }));

test("crea un círculo con una acción al entrar", async () => {
  const mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(hooks.useFence).mockReturnValue({ data: undefined, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreateFence).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateFence).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/fences/new" element={<FenceEditorPage />} />
    </Routes>,
    { route: "/fences/new" },
  );
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Oficina Norte");
  expect(screen.getByLabelText("Identificador")).toHaveValue("oficina-norte");
  await user.clear(screen.getByLabelText("Latitud"));
  await user.type(screen.getByLabelText("Latitud"), "40.45");
  await user.clear(screen.getByLabelText("Longitud"));
  await user.type(screen.getByLabelText("Longitud"), "-3.7");
  await user.clear(screen.getByLabelText("Radio (m)"));
  await user.type(screen.getByLabelText("Radio (m)"), "250");
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.type(screen.getByLabelText("Texto"), "Bienvenido");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
  expect(mutateAsync.mock.calls[0][0]).toMatchObject({ id: "oficina-norte", kind: "circle", center: { lat: 40.45, lng: -3.7 }, radius_m: 250, actions: [{ action: "message", when: "on_enter", params: { text: "Bienvenido" } }] });
  expect(navigate).toHaveBeenCalledWith("/fences");
});
```

- [ ] **Step 2: Implementar `slug.ts` y `fenceForm.ts`**

`web/src/lib/slug.ts`:
```ts
export function slugify(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}
```

`web/src/features/fences/fenceForm.ts`:
```ts
import { z } from "zod";
import type { Fence } from "@/api/hooks";

export const actionValues = ["message", "notify", "locate", "lock", "reboot", "clear_passcode", "wipe", "set_compliance", "custom"] as const;
export const whenValues = ["on_enter", "on_exit", "on_violation", "on_unknown"] as const;

const actionSchema = z.object({ action: z.enum(actionValues), when: z.enum(whenValues), text: z.string(), enabled: z.boolean() });

export function parsePolygon(text: string): { lat: number; lng: number }[] | null {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const pts: { lat: number; lng: number }[] = [];
  for (const line of lines) {
    const [a, b, ...rest] = line.split(",").map((s) => s.trim());
    if (rest.length || a === undefined || b === undefined) return null;
    const lat = Number(a);
    const lng = Number(b);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
    pts.push({ lat, lng });
  }
  return pts.length >= 3 ? pts : null;
}

export const fenceFormSchema = z
  .object({
    name: z.string().trim().min(1),
    id: z.string().regex(/^[a-z0-9][a-z0-9-]{0,63}$/),
    kind: z.enum(["circle", "polygon"]),
    centerLat: z.coerce.number().min(-90).max(90),
    centerLng: z.coerce.number().min(-180).max(180),
    radiusM: z.coerce.number(),
    polygonText: z.string(),
    actions: z.array(actionSchema),
  })
  .refine((f) => f.kind !== "circle" || f.radiusM > 0, { path: ["radiusM"], message: "radius" })
  .refine((f) => f.kind !== "polygon" || parsePolygon(f.polygonText) !== null, { path: ["polygonText"], message: "polygon" });

export type FenceForm = z.infer<typeof fenceFormSchema>;

export const emptyForm: FenceForm = { name: "", id: "", kind: "circle", centerLat: 40.4168, centerLng: -3.7038, radiusM: 300, polygonText: "", actions: [] };

export function toFence(form: FenceForm): Fence {
  const now = new Date().toISOString();
  const base = {
    id: form.id,
    name: form.name.trim(),
    kind: form.kind,
    rules: {},
    actions: form.actions.map((a) => ({ action: a.action, when: a.when, enabled: a.enabled, params: a.text ? { text: a.text } : {} })),
    created_at: now,
    updated_at: now,
  };
  if (form.kind === "circle") return { ...base, center: { lat: form.centerLat, lng: form.centerLng }, radius_m: form.radiusM } as Fence;
  return { ...base, polygon: parsePolygon(form.polygonText) ?? [] } as Fence;
}

export function fromFence(f: Fence): FenceForm {
  return {
    name: f.name,
    id: f.id,
    kind: f.kind,
    centerLat: f.center?.lat ?? emptyForm.centerLat,
    centerLng: f.center?.lng ?? emptyForm.centerLng,
    radiusM: f.radius_m ?? emptyForm.radiusM,
    polygonText: (f.polygon ?? []).map((p) => `${p.lat}, ${p.lng}`).join("\n"),
    actions: (f.actions ?? []).map((a) => ({
      action: a.action as (typeof actionValues)[number],
      when: a.when as (typeof whenValues)[number],
      text: typeof a.params?.text === "string" ? a.params.text : typeof a.params?.msg === "string" ? a.params.msg : "",
      enabled: a.enabled,
    })),
  };
}
```

- [ ] **Step 3: Implementar `FencesPage.tsx` y `FenceEditorPage.tsx`**

`web/src/features/fences/FencesPage.tsx`:
```tsx
import { useState } from "react";
import { Link } from "react-router";
import { Plus } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Loading } from "@/components/states/Loading";
import { Empty } from "@/components/states/Empty";
import { ErrorState } from "@/components/states/ErrorState";
import { useDeleteFence, useFences, useMe, type Fence } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

export function FencesPage() {
  const t = useT();
  const fences = useFences();
  const del = useDeleteFence();
  const me = useMe();
  const [pending, setPending] = useState<Fence | null>(null);
  const canWrite = can(me.data?.capabilities, "fence:write");
  const canDelete = can(me.data?.capabilities, "fence:delete");
  const newButton = canWrite && (
    <Button asChild>
      <Link to="/fences/new">
        <Plus size={16} aria-hidden /> {t("fences.new")}
      </Link>
    </Button>
  );
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("fences.title")}</h1>
        {newButton}
      </div>
      {fences.isPending && <Loading rows={4} />}
      {fences.error && <ErrorState error={fences.error} onRetry={() => fences.refetch()} />}
      {fences.data && fences.data.items.length === 0 && <Empty title={t("fences.empty")} action={newButton || undefined} />}
      {fences.data && fences.data.items.length > 0 && (
        <Table>
          <THead>
            <tr>
              <TH>{t("fences.col.name")}</TH>
              <TH>{t("fences.col.kind")}</TH>
              <TH>{t("fences.col.actions")}</TH>
              <TH />
            </tr>
          </THead>
          <TBody>
            {fences.data.items.map((f) => (
              <TR key={f.id}>
                <TD>
                  <Link to={`/fences/${f.id}`} className="font-medium hover:text-accent">
                    {f.name}
                  </Link>
                  <span className="ml-2 font-mono text-xs text-muted">{f.id}</span>
                </TD>
                <TD>{t(`fence.kind.${f.kind}`)}</TD>
                <TD>{f.actions.length}</TD>
                <TD className="text-right">
                  {canDelete && (
                    <Button variant="ghost" size="sm" onClick={() => setPending(f)}>
                      {t("fences.delete")}
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={t("fences.delete")}
        description={pending ? t("fences.delete.confirm", { name: pending.name }) : undefined}
        confirmLabel={t("fences.delete")}
        cancelLabel={t("fence.cancel")}
        onConfirm={() => {
          if (pending) del.mutate(pending.id);
          setPending(null);
        }}
      />
    </div>
  );
}
```

`web/src/features/fences/FenceEditorPage.tsx`:
```tsx
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Trash } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useCreateFence, useFence, useUpdateFence } from "@/api/hooks";
import { useT } from "@/lib/i18n";
import { slugify } from "@/lib/slug";
import { actionValues, whenValues, emptyForm, fenceFormSchema, fromFence, toFence, type FenceForm } from "./fenceForm";

export function FenceEditorPage() {
  const { id } = useParams();
  const editing = !!id;
  const t = useT();
  const navigate = useNavigate();
  const existing = useFence(id ?? "");
  const create = useCreateFence();
  const update = useUpdateFence();
  const form = useForm<FenceForm>({ resolver: zodResolver(fenceFormSchema), defaultValues: emptyForm });
  const actions = useFieldArray({ control: form.control, name: "actions" });
  const kind = form.watch("kind");
  const name = form.watch("name");
  useEffect(() => {
    if (!editing) form.setValue("id", slugify(name), { shouldValidate: false });
  }, [name, editing, form]);
  useEffect(() => {
    if (existing.data) form.reset(fromFence(existing.data));
  }, [existing.data, form]);
  const submit = form.handleSubmit(async (values) => {
    const fence = toFence(values);
    await (editing ? update.mutateAsync(fence) : create.mutateAsync(fence));
    navigate("/fences");
  });
  if (editing && existing.isPending) return <Loading rows={6} />;
  if (editing && existing.error) return <ErrorState error={existing.error} />;
  const errs = form.formState.errors;
  const mutationError = create.error ?? update.error;
  return (
    <form onSubmit={submit} noValidate className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{editing ? t("fence.editor.edit") : t("fence.editor.new")}</h1>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="name">{t("fence.name")}</Label>
          <Input id="name" aria-invalid={!!errs.name} {...form.register("name")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="id">{t("fence.id")}</Label>
          <Input id="id" aria-invalid={!!errs.id} readOnly={editing} {...form.register("id")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="kind">{t("fence.kind")}</Label>
          <NativeSelect id="kind" {...form.register("kind")}>
            <option value="circle">{t("fence.kind.circle")}</option>
            <option value="polygon">{t("fence.kind.polygon")}</option>
          </NativeSelect>
        </div>
      </div>
      {kind === "circle" ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="centerLat">Latitud</Label>
            <Input id="centerLat" type="number" step="any" aria-invalid={!!errs.centerLat} {...form.register("centerLat")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="centerLng">Longitud</Label>
            <Input id="centerLng" type="number" step="any" aria-invalid={!!errs.centerLng} {...form.register("centerLng")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="radiusM">{t("fence.radius")}</Label>
            <Input id="radiusM" type="number" step="1" aria-invalid={!!errs.radiusM} {...form.register("radiusM")} />
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="polygonText">{t("fence.polygon")}</Label>
          <textarea id="polygonText" rows={6} aria-invalid={!!errs.polygonText} className="w-full rounded-[var(--radius-ui)] border border-border bg-panel p-3 font-mono text-sm" {...form.register("polygonText")} />
          {errs.polygonText && <p role="alert" className="text-xs text-sev-high">{t("fence.error.polygon")}</p>}
        </div>
      )}
      <fieldset className="space-y-3">
        <div className="flex items-center justify-between">
          <legend className="text-sm font-medium text-fg-2">{t("fence.actions")}</legend>
          <Button type="button" variant="secondary" size="sm" onClick={() => actions.append({ action: "message", when: "on_enter", text: "", enabled: true })}>
            {t("fence.actions.add")}
          </Button>
        </div>
        {actions.fields.map((field, i) => (
          <div key={field.id} className="grid items-end gap-3 rounded-[var(--radius-ui)] border border-border p-3 sm:grid-cols-[1fr_1fr_2fr_auto]">
            <div className="space-y-1.5">
              <Label htmlFor={`action-${i}`}>{t("fences.col.actions")}</Label>
              <NativeSelect id={`action-${i}`} {...form.register(`actions.${i}.action`)}>
                {actionValues.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`when-${i}`}>{t("fence.when.on_enter").split(" ")[0]}</Label>
              <NativeSelect id={`when-${i}`} {...form.register(`actions.${i}.when`)}>
                {whenValues.map((w) => (
                  <option key={w} value={w}>
                    {t(`fence.when.${w}`)}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`text-${i}`}>Texto</Label>
              <Input id={`text-${i}`} {...form.register(`actions.${i}.text`)} />
            </div>
            <Button type="button" variant="ghost" size="icon" aria-label={t("fences.delete")} onClick={() => actions.remove(i)}>
              <Trash size={16} aria-hidden />
            </Button>
          </div>
        ))}
      </fieldset>
      {mutationError && <ErrorState error={mutationError} />}
      <div className="flex gap-2">
        <Button type="submit" disabled={create.isPending || update.isPending}>
          {t("fence.save")}
        </Button>
        <Button type="button" variant="secondary" onClick={() => navigate("/fences")}>
          {t("fence.cancel")}
        </Button>
      </div>
    </form>
  );
}
```

- [ ] **Step 4: Verificar y commit**

```bash
cd web && npm run lint && npm run typecheck && npm test && cd ..
git add web
git commit -q -m "feat(web): geocercas con lista, borrado confirmado y editor círculo/polígono con acciones

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 22: End-to-end con Playwright contra el binario y job `e2e` en CI

**Files:**
- Create: `web/playwright.config.ts`, `web/e2e/demo.spec.ts`
- Modify: `web/package.json` (devDependency `@playwright/test 1.63.0`, script `e2e`), `.gitignore` (`.e2e-data/`), `Makefile` (target `e2e`), `.github/workflows/ci.yml` (job `e2e`), protección de rama

- [ ] **Step 1: Configuración**

`web/package.json`: añadir `"@playwright/test": "1.63.0"` a `devDependencies` y `"e2e": "playwright test"` a `scripts`. Luego `cd web && npm install && npx playwright install chromium`.

`web/playwright.config.ts`:
```ts
import { defineConfig, devices } from "@playwright/test";

const port = 8770;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `rm -rf ../.e2e-data && ../bin/lucidfence serve -data ../.e2e-data -config ../.e2e-config.json -listen 127.0.0.1:${port}`,
    url: `http://127.0.0.1:${port}/api/v1/health`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
```

`web/e2e/demo.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test.describe.serial("núcleo demo", () => {
  test("asistente → demo → visión general → mapa → dispositivo → geocerca → ciclo", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/setup$/);
    await page.getByLabel("Email").fill("e2e@lucidfence.local");
    await page.getByLabel("Nombre").fill("E2E");
    await page.getByLabel(/Contraseña/).fill("contraseña-e2e-2026");
    await page.getByLabel("Demo local con flota simulada").check();
    await page.getByRole("button", { name: "Crear cuenta y entrar" }).click();

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Visión general" })).toBeVisible();
    await expect(page.locator("p", { hasText: /^Dispositivos$/ }).locator("xpath=following-sibling::p")).toHaveText("6");

    await page.getByRole("link", { name: "Mapa" }).click();
    await expect(page.getByText("Dentro de geocerca")).toBeVisible();
    await expect(page.locator(".maplibregl-canvas")).toBeVisible();

    await page.getByRole("link", { name: "Dispositivos" }).click();
    await expect(page.getByRole("row")).toHaveCount(7);
    await page.getByRole("link", { name: /Tablet Campo A1/ }).click();
    await expect(page.getByText("Samsung Galaxy Tab Active5")).toBeVisible();

    await page.getByRole("link", { name: "Geocercas" }).click();
    await expect(page.getByRole("link", { name: "Demo HQ · Madrid" })).toBeVisible();
    await page.getByRole("link", { name: "Nueva geocerca" }).click();
    await page.getByLabel("Nombre").fill("Oficina Norte");
    await page.getByLabel("Latitud").fill("40.45");
    await page.getByLabel("Longitud").fill("-3.65");
    await page.getByLabel("Radio (m)").fill("400");
    await page.getByRole("button", { name: "Guardar" }).click();
    await expect(page.getByRole("link", { name: "Oficina Norte" })).toBeVisible();

    await page.getByRole("link", { name: "Visión general" }).click();
    await page.getByRole("button", { name: "Ejecutar ciclo ahora" }).click();
    await expect(page.getByText("demo-hq:inside").first()).toBeVisible();
  });
});
```

`.gitignore`: añadir `.e2e-data/` y `.e2e-config.json`.

`Makefile`:
```make
e2e: web build
	cd web && npx playwright install chromium && npm run e2e
```
y `verify: lint cover web battery e2e`.

- [ ] **Step 2: Ejecutar en local**

```bash
make web build && cd web && npm run e2e && cd ..
```

Expected: 1 test verde. Si `.maplibregl-canvas` no aparece por falta de WebGL en el entorno, comprobar que el navegador arranca con los `launchOptions.args` indicados; en última instancia sustituir esa aserción por `await expect(page.locator(".maplibregl-map")).toBeVisible()` y anotar en el commit el motivo.

- [ ] **Step 3: Job `e2e` en CI y checks obligatorios**

Añadir a `.github/workflows/ci.yml`:
```yaml
  e2e:
    name: e2e
    needs: [web]
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web } }
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-go@v7
        with: { go-version-file: go.mod }
      - uses: actions/setup-node@v7
        with: { node-version: 24, cache: npm, cache-dependency-path: web/package-lock.json }
      - uses: actions/download-artifact@v7
        with: { name: web-dist, path: internal/web/dist }
      - name: compilar binario con dashboard
        working-directory: .
        run: CGO_ENABLED=0 go build -trimpath -o bin/lucidfence ./cmd/lucidfence
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npm run e2e
      - uses: actions/upload-artifact@v7
        if: failure()
        with: { name: playwright-report, path: web/playwright-report, retention-days: 7 }
```

Protección de rama con el sexto check (tras el primer run verde en la rama):
```bash
gh api -X PUT repos/adrimg3196/lucidfence/branches/main/protection --input - <<'EOF'
{
  "required_status_checks": { "strict": true, "contexts": ["go-lint", "go-test", "web", "battery", "security", "e2e"] },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0, "require_code_owner_reviews": true, "dismiss_stale_reviews": true },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false
}
EOF
```

- [ ] **Step 4: Commit**

```bash
git add web/playwright.config.ts web/e2e web/package.json web/package-lock.json .gitignore Makefile .github/workflows/ci.yml
git commit -q -m "test(e2e): flujo demo completo con Playwright contra el binario y job e2e en CI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
```

---

### Task 23: Verificación completa, integración en `main`, pre-release `2.0.0-alpha.1` y cierre

- [ ] **Step 1: Gate completo en local**

```bash
make verify
```

Expected: `verify: OK` (lint, cobertura con suelos, web, batería `RUNTIME: 12/12`, e2e).

- [ ] **Step 2: Push, CI verde y fast-forward de `main`**

```bash
git push -u origin m1/nucleo-demo
sleep 20
run_id=$(gh run list --branch m1/nucleo-demo --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$run_id" --exit-status
git fetch origin main
git merge -s ours origin/main -m "chore: absorber main en m1/nucleo-demo (estrategia ours)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
git push origin m1/nucleo-demo:main
```

Expected: seis checks verdes; push a `main` en fast-forward. Si `main` no ha cambiado desde M0, el `merge -s ours` no crea commit (`Already up to date`) y el push sigue siendo fast-forward.

- [ ] **Step 3: Binarios de la pre-release**

```bash
rm -rf dist && mkdir -p dist
for target in darwin/arm64 darwin/amd64 linux/amd64 linux/arm64; do
  GOOS=${target%/*} GOARCH=${target#*/} CGO_ENABLED=0 go build -trimpath \
    -ldflags "-s -w -X github.com/adrimg3196/lucidfence/internal/version.Version=2.0.0-alpha.1 -X github.com/adrimg3196/lucidfence/internal/version.Commit=$(git rev-parse --short HEAD)" \
    -o "dist/lucidfence-2.0.0-alpha.1-${target%/*}-${target#*/}" ./cmd/lucidfence
done
(cd dist && shasum -a 256 lucidfence-* > SHA256SUMS)
./dist/lucidfence-2.0.0-alpha.1-darwin-arm64 version
```

Expected: cuatro binarios con el dashboard embebido (el `make web` de `verify` ya dejó `internal/web/dist` poblado) y la línea `lucidfence 2.0.0-alpha.1 (...)`.

- [ ] **Step 4: Tag y GitHub pre-release**

```bash
git tag -a v2.0.0-alpha.1 -m "LucidFence 2.0.0-alpha.1: núcleo demo (M1)"
git tag -a m1-nucleo-demo -m "M1: núcleo demo"
git push origin v2.0.0-alpha.1 m1-nucleo-demo
cat > /tmp/notes.md <<'EOF'
Primera pre-release de LucidFence 2.0 (reescritura en Go). Núcleo demo:

- Un binario. `./lucidfence serve` y abre http://127.0.0.1:8765
- Asistente inicial, flota simulada de 6 dispositivos en Madrid, dos geocercas, una ruta
- Motor de evaluación (observe: todo dry-run), transiciones, acciones simuladas
- Dashboard: visión general, mapa en vivo, dispositivos, geocercas
- CLI: serve, doctor, open, version

No incluye todavía conectores UEM reales, motor de riesgo, incidentes ni webhooks (hitos M2-M4).
Datos en ./data (permisos 0600/0700). Verifica el checksum con SHA256SUMS.
EOF
gh release create v2.0.0-alpha.1 --prerelease --title "LucidFence 2.0.0-alpha.1 (núcleo demo)" --notes-file /tmp/notes.md dist/*
gh release view v2.0.0-alpha.1 --json assets --jq '.assets[].name'
```

Expected: la release lista los cuatro binarios y `SHA256SUMS`.

- [ ] **Step 5: `CHANGELOG.md` y `README.md`**

Añadir en `CHANGELOG.md` bajo `## [2.0.0-dev]` una sección `### Añadido` con las viñetas de las notas de la release, y en `README.md` sustituir el bloque "Estado" por: `main` = 2.0 en construcción; última pre-release `2.0.0-alpha.1` (enlace a Releases); 1.6.1 sigue siendo la última estable. Commit y push a `main`:

```bash
git add CHANGELOG.md README.md
git commit -q -m "docs: notas de 2.0.0-alpha.1 en CHANGELOG y README

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GjMTkpr4PnhrZTzqQ7J75w"
git push origin HEAD:main
```

- [ ] **Step 6: Mensaje de cierre al propietario** (contenido mínimo):
  - Qué se puede probar: descargar `lucidfence-2.0.0-alpha.1-darwin-arm64`, `chmod +x`, `./lucidfence serve`, abrir el dashboard, elegir demo.
  - Gate: seis checks obligatorios en `main`; `RUNTIME: 12/12`; e2e verde.
  - Lo que NO está aún (M2-M5) y el siguiente plan a escribir: `2026-09-05-m2-riesgo-y-acciones.md`.
