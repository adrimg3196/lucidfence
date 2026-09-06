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
		stamp: func(next *fence.Fence, prev *fence.Fence, now time.Time) {
			if prev == nil {
				next.CreatedAt = now
			} else {
				next.CreatedAt = prev.CreatedAt
			}
			next.UpdatedAt = now
			if next.Actions == nil {
				next.Actions = []fence.Action{}
			}
		},
		validate: fence.ValidateAll,
	}.register(s)
}
