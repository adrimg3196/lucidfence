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
		name := strings.TrimPrefix(r.URL.Path, "/")
		if name == "" {
			name = fallback
		}
		if _, err := fs.Stat(fsys, name); err != nil {
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
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if rs, ok := f.(io.ReadSeeker); ok {
		http.ServeContent(w, r, name, info.ModTime(), rs)
		return
	}
	data, err := io.ReadAll(f)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	http.ServeContent(w, r, name, info.ModTime(), bytes.NewReader(data))
}
