package web

import (
	"errors"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"
	"time"
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
		if got := rr.Header().Get("Cache-Control"); got != "no-cache" {
			t.Fatalf("%s: cache-control=%q, quería no-cache", path, got)
		}
	}
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/assets/app.js", nil))
	if rr.Code != 200 || rr.Body.String() != "console.log(1)" {
		t.Fatalf("asset: code=%d body=%q", rr.Code, rr.Body.String())
	}
	if got := rr.Header().Get("Cache-Control"); got != "public, max-age=31536000, immutable" {
		t.Fatalf("asset: cache-control=%q", got)
	}
}

func TestHandlerRutaDeDirectorioHaceFallback(t *testing.T) {
	built := fstest.MapFS{
		"index.html":    {Data: []byte(`<div id="root"></div>`)},
		"assets/app.js": {Data: []byte(`console.log(1)`)},
	}
	h := Handler(built)
	for _, path := range []string{"/assets", "/assets/"} {
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, path, nil))
		if rr.Code != 200 || !strings.Contains(rr.Body.String(), `id="root"`) {
			t.Fatalf("%s: code=%d body=%q", path, rr.Code, rr.Body.String())
		}
	}

	unbuilt := fstest.MapFS{
		"placeholder.html": {Data: []byte("LucidFence: frontend no compilado")},
		"assets/x.js":      {Data: []byte(`console.log(2)`)},
	}
	hUnbuilt := Handler(unbuilt)
	for _, path := range []string{"/fonts", "/assets"} {
		rr := httptest.NewRecorder()
		hUnbuilt.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, path, nil))
		if rr.Code != 200 || !strings.Contains(rr.Body.String(), "LucidFence") {
			t.Fatalf("%s: code=%d body=%q", path, rr.Code, rr.Body.String())
		}
	}
}

func TestHandlerAssetAusenteDevuelve404(t *testing.T) {
	fsys := fstest.MapFS{
		"index.html":    {Data: []byte(`<div id="root"></div>`)},
		"assets/app.js": {Data: []byte(`console.log(1)`)},
	}
	h := Handler(fsys)
	for _, path := range []string{"/assets/no-existe.js", "/fonts/no-existe.woff2", "/robots.txt"} {
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, path, nil))
		if rr.Code != http.StatusNotFound {
			t.Fatalf("%s: code=%d, quería 404", path, rr.Code)
		}
	}
	// Una ruta de cliente sin extensión sigue haciendo fallback SPA.
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/devices/abc", nil))
	if rr.Code != http.StatusOK || !strings.Contains(rr.Body.String(), `id="root"`) {
		t.Fatalf("/devices/abc: code=%d body=%q", rr.Code, rr.Body.String())
	}
}

func TestHandlerMetodoNoPermitidoDevuelve405(t *testing.T) {
	fsys := fstest.MapFS{"index.html": {Data: []byte(`<div id="root"></div>`)}}
	h := Handler(fsys)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodPost, "/", nil))
	if rr.Code != http.StatusMethodNotAllowed {
		t.Fatalf("code=%d, quería 405", rr.Code)
	}
	if got := rr.Header().Get("Allow"); got != "GET, HEAD" {
		t.Fatalf("Allow=%q", got)
	}
}

func TestHandlerSinBuildSirvePlaceholder(t *testing.T) {
	fsys := fstest.MapFS{
		"placeholder.html": {Data: []byte("<h1>LucidFence: frontend no compilado</h1>")},
	}
	h := Handler(fsys)
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/", nil))
	if rr.Code != 200 {
		t.Fatalf("code=%d", rr.Code)
	}
	body := rr.Body.String()
	if !strings.Contains(body, "frontend no compilado") {
		t.Fatalf("body=%q", body)
	}
}

// statFailFS envuelve un fs.FS real: Open funciona, pero el fichero que
// devuelve falla siempre en Stat. Ejercita la rama de serveFile que no
// filtra el error real al cliente.
type statFailFS struct{ fs.FS }

func (s statFailFS) Open(name string) (fs.File, error) {
	f, err := s.FS.Open(name)
	if err != nil {
		return nil, err
	}
	return statFailFile{f}, nil
}

type statFailFile struct{ fs.File }

func (statFailFile) Stat() (fs.FileInfo, error) {
	return nil, errors.New("stat roto a propósito")
}

func TestServeFileStatFallaDevuelveErrorInterno(t *testing.T) {
	fsys := statFailFS{fstest.MapFS{"index.html": {Data: []byte("<html></html>")}}}
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/index.html", nil)
	serveFile(rr, req, fsys, "index.html")
	if rr.Code != http.StatusInternalServerError {
		t.Fatalf("code=%d, quería 500", rr.Code)
	}
	if body := strings.TrimSpace(rr.Body.String()); body != "error interno" {
		t.Fatalf("body=%q filtra detalle interno", body)
	}
}

// readFailFS es un fs.FS mínimo cuyo único fichero abre y hace Stat sin
// error, pero cuyo Read siempre falla; al no implementar io.ReadSeeker,
// serveFile toma la vía io.ReadAll y encuentra ese error ahí.
type readFailFS struct{}

func (readFailFS) Open(string) (fs.File, error) { return readFailFile{}, nil }

type readFailFile struct{}

func (readFailFile) Stat() (fs.FileInfo, error) { return fakeFileInfo{}, nil }
func (readFailFile) Read([]byte) (int, error)   { return 0, errors.New("read roto a propósito") }
func (readFailFile) Close() error               { return nil }

type fakeFileInfo struct{}

func (fakeFileInfo) Name() string       { return "index.html" }
func (fakeFileInfo) Size() int64        { return 0 }
func (fakeFileInfo) Mode() fs.FileMode  { return 0 }
func (fakeFileInfo) ModTime() time.Time { return time.Time{} }
func (fakeFileInfo) IsDir() bool        { return false }
func (fakeFileInfo) Sys() any           { return nil }

func TestServeFileReadFallaDevuelveErrorInterno(t *testing.T) {
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/index.html", nil)
	serveFile(rr, req, readFailFS{}, "index.html")
	if rr.Code != http.StatusInternalServerError {
		t.Fatalf("code=%d, quería 500", rr.Code)
	}
	if body := strings.TrimSpace(rr.Body.String()); body != "error interno" {
		t.Fatalf("body=%q filtra detalle interno", body)
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
