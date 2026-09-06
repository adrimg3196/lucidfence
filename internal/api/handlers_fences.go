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
