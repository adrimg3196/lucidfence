package web

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"
)

func TestHandlerSirveIndexYFallbackSPA(t *testing.T) {
	fsys := fstest.MapFS{
		"index.html":    {Data: []byte(`<div id="root"></div>`)},
		"assets/app.js": {Data: []byte(`console.log(1)`)},
	}
	h := Handler(fsys)
	for _, path := range []string{"/", "/devices/abc", "/index.html"} {
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, path, nil))
		if rr.Code != 200 || !strings.Contains(rr.Body.String(), `id="root"`) {
			t.Fatalf("%s: code=%d body=%q", path, rr.Code, rr.Body.String())
		}
	}
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/assets/app.js", nil))
	if rr.Code != 200 || rr.Body.String() != "console.log(1)" {
		t.Fatalf("asset: code=%d body=%q", rr.Code, rr.Body.String())
	}
}

func TestHandlerSinBuildSirvePlaceholder(t *testing.T) {
	h := Handler(Dist())
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/", nil))
	if rr.Code != 200 {
		t.Fatalf("code=%d", rr.Code)
	}
	body := rr.Body.String()
	if !strings.Contains(body, "LucidFence") {
		t.Fatalf("body=%q", body)
	}
}

func TestIsBuiltDetectaIndex(t *testing.T) {
	if IsBuilt(fstest.MapFS{"placeholder.html": {Data: []byte("x")}}) {
		t.Fatal("solo placeholder no cuenta como build")
	}
	if !IsBuilt(fstest.MapFS{"index.html": {Data: []byte("x")}}) {
		t.Fatal("index.html cuenta como build")
	}
}
