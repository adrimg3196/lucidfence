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
