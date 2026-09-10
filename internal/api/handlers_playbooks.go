package api

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/domain/policy"
)

// registerPlaybooks monta el CRUD de playbooks SOAR sobre el crud genérico.
// La lectura va bajo policy:read porque playbooks y políticas comparten
// gramática, editor y catálogo de campos: quien puede leer unas puede leer
// los otros. La escritura exige playbook:write, que la matriz §6.3 da a
// operator además de a admin y owner (a diferencia de policy:write). El
// borrado usa la misma capacidad que la escritura: no existe
// playbook:delete.
func (s *server) registerPlaybooks() {
	crud[playbook.Playbook]{
		path: "/api/v1/playbooks", readCap: auth.PolicyRead, writeCap: auth.PlaybookWrite, deleteCap: auth.PlaybookWrite,
		load: s.org().Playbooks, save: s.org().SavePlaybooks,
		id: func(p playbook.Playbook) string { return p.ID },
		stamp: func(next *playbook.Playbook, prev *playbook.Playbook, now time.Time) {
			if prev == nil {
				next.CreatedAt = now
			} else {
				next.CreatedAt = prev.CreatedAt
			}
			next.UpdatedAt = now
			// Listas vacías, nunca null: el editor de T25 y el motor de T16
			// recorren las dos sin comprobar nada.
			if next.When == nil {
				next.When = []policy.Condition{}
			}
			if next.Actions == nil {
				next.Actions = []policy.Action{}
			}
		},
		validate: playbook.ValidateAll,
	}.register(s)
}
