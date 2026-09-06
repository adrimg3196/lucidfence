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
	if _, err := s.d.Auth.Setup(b.Email, b.Name, b.Password, s.d.Config.Org); err != nil {
		switch {
		case errors.Is(err, auth.ErrAlreadySetUp):
			writeError(w, http.StatusConflict, "conflict", err.Error())
		default:
			writeError(w, http.StatusBadRequest, "invalid", err.Error())
		}
		return
	}
	if b.Mode == "demo" {
		if err := engine.SeedDemo(s.org(), s.d.Now()); err != nil {
			writeError(w, http.StatusInternalServerError, "internal", "no se pudieron escribir los datos demo: "+err.Error())
			return
		}
	}
	s.openSession(w, r, b.Email, b.Password, http.StatusCreated)
}

func (s *server) authLogin(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	var b loginBody
	if err := decodeJSON(r, &b); err != nil {
		writeError(w, http.StatusBadRequest, "invalid", err.Error())
		return
	}
	s.openSession(w, r, b.Email, b.Password, http.StatusOK)
}

func (s *server) openSession(w http.ResponseWriter, r *http.Request, email, password string, status int) {
	sess, err := s.d.Auth.Login(email, password, s.d.Config.Org)
	switch {
	case errors.Is(err, auth.ErrThrottled):
		writeError(w, http.StatusTooManyRequests, "throttled", err.Error())
		return
	case err != nil:
		writeError(w, http.StatusUnauthorized, "invalid_credentials", "email o contraseña incorrectos")
		return
	}
	p, err := s.d.Auth.Resolve(sess.Token)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal", "sesión no resoluble")
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
