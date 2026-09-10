package api

import (
	"bytes"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
)

// rolePassword es la contraseña de todos los usuarios que siembra newRoleEnv:
// una sola derivación argon2id para los cuatro, porque el hash es el mismo.
const rolePassword = "contraseña-larga-1"

// roleOrder fija el orden en que se siembran los usuarios (users.json es una
// lista, y un orden estable hace el fichero reproducible entre ejecuciones).
var roleOrder = []auth.Role{auth.Owner, auth.Admin, auth.Operator, auth.Viewer, auth.Auditor}

// roleEmails da a cada rol un email reconocible en los mensajes de fallo y en
// las entradas de auditoría que escriben los handlers.
var roleEmails = map[auth.Role]string{
	auth.Owner:    "owner@example.com",
	auth.Admin:    "admin@example.com",
	auth.Operator: "operator@example.com",
	auth.Viewer:   "viewer@example.com",
	auth.Auditor:  "auditor@example.com",
}

// newRoleEnv es newTestEnv con un usuario por rol en vez del owner del
// asistente inicial. auth.Store solo sabe crear owners (Setup), así que la
// única forma de probar de verdad las capacidades de operator, viewer y
// auditor sobre rutas reales es sembrar users.json antes de abrir el store:
// auth.Open lo lee tal cual. La instalación ya tiene usuarios, así que
// /auth/setup responde 409 aquí y los datos de la organización se siembran
// por el store (e.org), no por el modo demo.
func newRoleEnv(t *testing.T) *testEnv {
	t.Helper()
	now := time.Date(2026, 9, 5, 12, 0, 0, 0, time.UTC)
	clock := func() time.Time { return now }
	st, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	org, err := st.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	seedRoleUsers(t, st.AuthDir(), now)
	as, err := auth.Open(st.AuthDir(), clock)
	if err != nil {
		t.Fatal(err)
	}
	eng := engine.New(org, []uem.Adapter{&fakeFleet{now: clock}}, engine.Options{Mode: "simulation", Interval: time.Hour, Now: clock})
	logs := &bytes.Buffer{}
	h, _ := New(Deps{Engine: eng, Org: org, Auth: as, Web: http.NotFoundHandler(), Config: config.Default(), Now: clock,
		Logger: slog.New(slog.NewTextHandler(logs, nil))})
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	return &testEnv{t: t, srv: srv, auth: as, authDir: st.AuthDir(), org: org, logs: logs}
}

// seedRoleUsers escribe users.json con la forma que espera auth.Open: la
// colección {schema_version, items} y, en cada elemento, el usuario público
// más password_hash.
func seedRoleUsers(t *testing.T, dir string, at time.Time) {
	t.Helper()
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	hash, err := auth.HashPassword(rolePassword)
	if err != nil {
		t.Fatal(err)
	}
	items := make([]map[string]any, 0, len(roleOrder))
	for _, role := range roleOrder {
		items = append(items, map[string]any{
			"id": "usr-" + string(role), "email": roleEmails[role], "name": string(role),
			"org_roles":  map[string]string{"default": string(role)},
			"created_at": at, "password_hash": hash,
		})
	}
	if err := store.WriteJSON(filepath.Join(dir, "users.json"), map[string]any{"schema_version": 1, "items": items}); err != nil {
		t.Fatal(err)
	}
}

// as abre sesión como el rol indicado y deja la cookie y el CSRF listos para
// e.do(..., true). Sustituye a e.setup, que solo crea owners.
func (e *testEnv) as(role auth.Role) {
	e.t.Helper()
	res, out := e.do("POST", "/api/v1/auth/login", map[string]any{"email": roleEmails[role], "password": rolePassword}, false)
	if res.StatusCode != 200 {
		e.t.Fatalf("login como %s: %d %v", role, res.StatusCode, out)
	}
	e.cookie = nil
	for _, c := range res.Cookies() {
		if c.Name == CookieName {
			e.cookie = c
		}
	}
	e.csrf, _ = out["csrf"].(string)
	if e.cookie == nil || e.csrf == "" {
		e.t.Fatalf("login como %s sin cookie ni csrf: %v", role, out)
	}
}
