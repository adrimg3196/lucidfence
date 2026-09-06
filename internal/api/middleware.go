package api

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"net"
	"net/http"
	"strings"

	"github.com/adrimg3196/lucidfence/internal/auth"
)

// CookieName es la cookie de sesión del dashboard.
const CookieName = "lf_session"

// CSRFHeader es la cabecera obligatoria en mutaciones con cookie.
const CSRFHeader = "X-LucidFence-CSRF"

func requestID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func isLoopback(remoteAddr string) bool {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func (s *server) authenticate(r *http.Request) (*auth.Principal, error) {
	if c, err := r.Cookie(CookieName); err == nil && c.Value != "" {
		return s.d.Auth.Resolve(c.Value)
	}
	if h := r.Header.Get("Authorization"); strings.HasPrefix(h, "Bearer ") && isLoopback(r.RemoteAddr) {
		return s.d.Auth.ResolveLocal(strings.TrimPrefix(h, "Bearer "), s.d.Config.Org)
	}
	return nil, auth.ErrUnauthenticated
}

func mutating(method string) bool {
	return method != http.MethodGet && method != http.MethodHead && method != http.MethodOptions
}

func (s *server) wrap(rt Route) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				s.d.Logger.Error("panic en handler", "path", r.URL.Path, "panic", rec, "request_id", w.Header().Get("X-Request-ID"))
				writeError(w, http.StatusInternalServerError, "internal", "error interno")
			}
		}()
		var p *auth.Principal
		if !rt.Public {
			var err error
			p, err = s.authenticate(r)
			if err != nil {
				if errors.Is(err, auth.ErrUnauthenticated) {
					writeError(w, http.StatusUnauthorized, "unauthenticated", "inicia sesión")
					return
				}
				writeError(w, http.StatusInternalServerError, "internal", "error de autenticación")
				return
			}
			if !auth.Can(p.Role, rt.Cap) {
				writeError(w, http.StatusForbidden, "forbidden", "sin permiso")
				return
			}
			if p.Via == "session" && mutating(r.Method) && r.Header.Get(CSRFHeader) != p.CSRF {
				writeError(w, http.StatusForbidden, "csrf", "falta o no coincide la cabecera "+CSRFHeader)
				return
			}
		}
		rt.Handler(w, r, p)
	})
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("X-Request-ID", requestID())
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "no-referrer")
		h.Set("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob: https:; connect-src 'self' https:; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'none'")
		next.ServeHTTP(w, r)
	})
}
