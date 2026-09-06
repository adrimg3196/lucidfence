package api

import (
	"errors"
	"net/http"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

func (s *server) registerAuth() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/auth/status", Public: true, Handler: s.authStatus})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/auth/setup", Public: true, Handler: s.authSetup})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/auth/login", Public: true, Handler: s.authLogin})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/auth/logout", Cap: auth.OrgRead, Handler: s.authLogout})
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/auth/me", Cap: auth.OrgRead, Handler: s.authMe})
}

type setupBody struct {
	Email    string `json:"email"`
	Name     string `json:"name"`
	Password string `json:"password"`
	Mode     string `json:"mode"`
}

type loginBody struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func userView(p *auth.Principal) map[string]any {
	return map[string]any{"id": p.UserID, "email": p.Email, "name": p.Name, "org": p.OrgID, "role": p.Role, "via": p.Via}
}

func (s *server) setCookie(w http.ResponseWriter, r *http.Request, token string, maxAge int) {
	http.SetCookie(w, &http.Cookie{Name: CookieName, Value: token, Path: "/", HttpOnly: true, Secure: r.TLS != nil,
		SameSite: http.SameSiteStrictMode, MaxAge: maxAge})
}

func (s *server) authStatus(w http.ResponseWriter, _ *http.Request, _ *auth.Principal) {
	writeJSON(w, http.StatusOK, map[string]any{"setup_required": !s.d.Auth.HasUsers()})
}

func (s *server) authSetup(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	var b setupBody
	if err := decodeJSON(r, &b); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	if b.Mode != "demo" && b.Mode != "empty" {
		writeError(w, http.StatusBadRequest, "invalid", "mode debe ser demo o empty")
		return
	}
	// Solo los errores de validación del propio usuario son 400 con su
	// mensaje; cualquier otro fallo de Setup (persistencia de users.json,
	// entropía del hash) es de clase 500 y su mensaje lleva rutas del
	// directorio de datos, así que va al log y no a la respuesta (M1-R17).
	user, err := s.d.Auth.Setup(b.Email, b.Name, b.Password, s.d.Config.Org)
	if err != nil {
		switch {
		case errors.Is(err, auth.ErrAlreadySetUp):
			writeError(w, http.StatusConflict, "conflict", err.Error())
		case errors.Is(err, auth.ErrInvalidUser), errors.Is(err, auth.ErrWeakPassword):
			writeError(w, http.StatusBadRequest, "invalid", err.Error())
		default:
			s.fail(w, "auth.setup.persist", err)
		}
		return
	}
	if b.Mode == "demo" {
		if err := engine.SeedDemo(s.org(), s.d.Now()); err != nil {
			s.fail(w, "auth.setup.seed", err)
			return
		}
	}
	// El asistente abre la sesión por StartSession, sin volver a pasar por
	// el limitador de intentos de Login: como /auth/login es público y
	// anota los fallos de emails que aún no existen, cualquiera podía
	// precargar el contador del email del owner y dejar la instalación
	// creada pero sin sesión ni salida por la UI (hallazgo C10).
	sess, err := s.d.Auth.StartSession(user.ID, s.d.Config.Org)
	if err != nil {
		s.fail(w, "auth.setup.session", err)
		return
	}
	s.writeSession(w, r, sess, http.StatusCreated)
}

func (s *server) authLogin(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	var b loginBody
	if err := decodeJSON(r, &b); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	s.openSession(w, r, b.Email, b.Password)
}

func (s *server) openSession(w http.ResponseWriter, r *http.Request, email, password string) {
	sess, err := s.d.Auth.Login(email, password, s.d.Config.Org)
	switch {
	case errors.Is(err, auth.ErrThrottled):
		writeError(w, http.StatusTooManyRequests, "throttled", err.Error())
		return
	// Un fallo al guardar sessions.json no es un problema de credenciales:
	// sale como 500 "error interno" y se registra, en vez de acusar al
	// usuario de equivocarse de contraseña (M1-R17, M1-R21).
	case errors.Is(err, auth.ErrPersistence):
		s.fail(w, "auth.login.persist", err)
		return
	case err != nil:
		writeError(w, http.StatusUnauthorized, "invalid_credentials", "email o contraseña incorrectos")
		return
	}
	s.writeSession(w, r, sess, http.StatusOK)
}

// writeSession fija la cookie de sesión y devuelve el usuario resuelto con
// sus capacidades. La comparten el login y el asistente inicial, que abren
// la sesión por caminos distintos.
func (s *server) writeSession(w http.ResponseWriter, r *http.Request, sess auth.Session, status int) {
	p, err := s.d.Auth.Resolve(sess.Token)
	if err != nil {
		s.fail(w, "auth.session.resolve", err)
		return
	}
	s.setCookie(w, r, sess.Token, int(auth.SessionTTL.Seconds()))
	writeJSON(w, status, map[string]any{"user": userView(p), "csrf": sess.CSRF, "capabilities": auth.Capabilities(p.Role)})
}

func (s *server) authLogout(w http.ResponseWriter, r *http.Request, p *auth.Principal) {
	if c, err := r.Cookie(CookieName); err == nil {
		_ = s.d.Auth.Logout(c.Value)
	}
	s.setCookie(w, r, "", -1)
	_ = p
	w.WriteHeader(http.StatusNoContent)
}

func (s *server) authMe(w http.ResponseWriter, _ *http.Request, p *auth.Principal) {
	writeJSON(w, http.StatusOK, map[string]any{"user": userView(p), "csrf": p.CSRF, "capabilities": auth.Capabilities(p.Role)})
}
