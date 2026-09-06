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
