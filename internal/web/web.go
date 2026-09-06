// Package web embebe el dashboard compilado (web/ → internal/web/dist) y lo
// sirve como SPA. placeholder.html está siempre en git para que go:embed
// compile aunque el frontend no se haya construido.
package web

import (
	"bytes"
	"embed"
	"io"
	"io/fs"
	"net/http"
	"path"
	"strings"
)

//go:embed all:dist
var dist embed.FS

// Dist devuelve el subárbol embebido (index.html, assets/...).
func Dist() fs.FS {
	sub, err := fs.Sub(dist, "dist")
	if err != nil {
		panic(err) // solo si el embed está roto en compilación
	}
	return sub
}

// IsBuilt indica si el árbol contiene un index.html real (no solo el placeholder).
func IsBuilt(fsys fs.FS) bool {
	_, err := fs.Stat(fsys, "index.html")
	return err == nil
}

// Handler sirve ficheros estáticos y hace fallback SPA a index.html; sin
// build sirve placeholder.html para que /api siga siendo verificable.
//
// No usa http.FileServer: su lógica interna de serveFile redirige toda
// petición cuyo r.URL.Path termine en "/index.html" (incluida la que este
// handler reescribe internamente como fallback), lo que convertía "/" en un
// 301 en vez de servir el contenido. Servimos el fichero directamente con
// http.ServeContent para controlar ese comportamiento.
func Handler(fsys fs.FS) http.Handler {
	fallback := "index.html"
	if !IsBuilt(fsys) {
		fallback = "placeholder.html"
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "método no permitido", http.StatusMethodNotAllowed)
			return
		}
		name := strings.TrimPrefix(r.URL.Path, "/")
		if name == "" {
			name = fallback
		}
		if info, err := fs.Stat(fsys, name); err != nil || info.IsDir() {
			// Un directorio real (p.ej. "assets" sin fichero "assets"
			// propio) no es servible: cae al fallback igual que una ruta
			// inexistente. La excepción es un asset ausente (bajo
			// assets/ o fonts/, o con extensión de fichero): eso es un
			// 404 real, no una ruta de cliente que resolver por SPA.
			if isStaticAsset(name) {
				http.NotFound(w, r)
				return
			}
			name = fallback
		}
		if strings.HasPrefix(name, "assets/") {
			w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
		} else {
			w.Header().Set("Cache-Control", "no-cache")
		}
		serveFile(w, r, fsys, name)
	})
}

// isStaticAsset distingue un fichero estático ausente (404 real) de una ruta
// de cliente sin extensión (fallback SPA): assets/ y fonts/ solo contienen
// ficheros generados en el build, y cualquier nombre con extensión de
// fichero (p.ej. robots.txt) tampoco es una ruta de React Router.
func isStaticAsset(name string) bool {
	for _, prefix := range []string{"assets/", "fonts/"} {
		if rest, ok := strings.CutPrefix(name, prefix); ok && rest != "" {
			return true
		}
	}
	return path.Ext(name) != ""
}

// serveFile abre name dentro de fsys y lo escribe con http.ServeContent,
// que gestiona Content-Type, Range y cabeceras condicionales sin aplicar el
// redirect especial de index.html de http.FileServer.
func serveFile(w http.ResponseWriter, r *http.Request, fsys fs.FS, name string) {
	f, err := fsys.Open(name)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer func() { _ = f.Close() }()
	info, err := f.Stat()
	if err != nil {
		http.Error(w, "error interno", http.StatusInternalServerError)
		return
	}
	if info.IsDir() {
		// No debería alcanzarse: Handler ya sustituye por el fallback
		// cualquier name que resuelva a un directorio. Defensivo, para
		// que serveFile nunca intente leer un directorio con
		// io.ReadAll (que fallaría) ni filtre esa ruta interna.
		http.NotFound(w, r)
		return
	}
	if rs, ok := f.(io.ReadSeeker); ok {
		http.ServeContent(w, r, name, info.ModTime(), rs)
		return
	}
	data, err := io.ReadAll(f)
	if err != nil {
		http.Error(w, "error interno", http.StatusInternalServerError)
		return
	}
	http.ServeContent(w, r, name, info.ModTime(), bytes.NewReader(data))
}
