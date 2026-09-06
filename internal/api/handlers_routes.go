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
		stamp: func(next *route.Route, prev *route.Route, now time.Time) {
			if prev == nil {
				next.CreatedAt = now
			} else {
				next.CreatedAt = prev.CreatedAt
			}
			next.UpdatedAt = now
			if next.Actions == nil {
				next.Actions = []fence.Action{}
			}
			if next.DeviceIDs == nil {
				next.DeviceIDs = []string{}
			}
		},
		validate: route.ValidateAll,
	}.register(s)
}
