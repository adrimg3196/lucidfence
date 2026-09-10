package api

import (
	"net/http"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

// registerPolicies monta el recurso de políticas. Las tres rutas literales van
// antes que el crud genérico solo por legibilidad: el ServeMux de Go resuelve
// por especificidad, así que /policies/templates gana a /policies/{id} igual
// que /pois/geojson gana a /pois/{id} desde M1.
func (s *server) registerPolicies() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/policies/templates", Cap: auth.PolicyRead, Handler: s.policyTemplates})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/policies/fields", Cap: auth.PolicyRead, Handler: s.policyFields})
	// policy:read y no policy:write: Engine.Replay es de solo lectura (no toca
	// el adapter, ni actions.jsonl, ni cooldowns.json), y quien solo mira la
	// consola tiene que poder preguntar qué haría una política antes de pedir
	// que se guarde.
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/policies/replay", Cap: auth.PolicyRead, Handler: s.policyReplay})
	crud[policy.Policy]{
		path: "/api/v1/policies", readCap: auth.PolicyRead, writeCap: auth.PolicyWrite, deleteCap: auth.PolicyWrite,
		load: s.org().Policies, save: s.org().SavePolicies,
		id:       func(p policy.Policy) string { return p.ID },
		stamp:    stampPolicy,
		validate: policy.ValidateAll,
	}.register(s)
}

// stampPolicy fija las fechas del registro. En create (prev == nil) las pone
// las dos; en update copia created_at de lo guardado, para que un PUT cuyo
// cuerpo no lo incluya (el caso normal del editor) no borre la fecha de alta.
// Actions se normaliza a lista vacía para que el JSON de salida no lleve null;
// When no se normaliza porque una política sin condiciones no es válida y
// ValidateAll la rechaza antes de guardarla.
func stampPolicy(next *policy.Policy, prev *policy.Policy, now time.Time) {
	if prev == nil {
		next.CreatedAt = now
	} else {
		next.CreatedAt = prev.CreatedAt
	}
	next.UpdatedAt = now
	if next.Actions == nil {
		next.Actions = []policy.Action{}
	}
}

// policyTemplates devuelve las cinco plantillas del dominio. policy.Templates
// construye copias nuevas en cada llamada, así que lo que sale por el cable no
// es un alias del catálogo. Van sin fechar: las sella quien las guarde.
func (s *server) policyTemplates(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	ts := policy.Templates()
	writeJSON(w, http.StatusOK, map[string]any{"items": ts, "total": len(ts)})
}

// policyFields publica el vocabulario del editor. Es la única fuente de verdad:
// si la UI repitiera estas listas en TypeScript, añadir un campo en Go la
// dejaría mintiendo en silencio.
func (s *server) policyFields(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	ops := make([]string, 0, len(policy.Ops))
	for _, op := range policy.Ops {
		ops = append(ops, string(op))
	}
	writeJSON(w, http.StatusOK, map[string]any{"fields": policy.Fields, "ops": ops})
}

// policyReplay simula una política candidata contra el histórico. La valida
// aquí, antes de llamar al motor, porque Engine.Replay devuelve un error
// desnudo tanto para una política mal escrita (400, culpa de quien llama) como
// para un fallo de lectura del store (500, culpa nuestra), y esos dos casos no
// pueden compartir respuesta. El limit no se comprueba: replayLimit lo acota.
func (s *server) policyReplay(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	var req engine.ReplayRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if err := req.Policy.Validate(); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	res, err := s.d.Engine.Replay(req)
	if err != nil {
		s.fail(w, "policies.replay", err)
		return
	}
	writeJSON(w, http.StatusOK, res)
}
