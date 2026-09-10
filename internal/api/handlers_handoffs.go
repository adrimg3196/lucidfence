package api

import (
	"errors"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/playbook"
	"github.com/adrimg3196/lucidfence/internal/engine"
)

func (s *server) registerHandoffs() {
	s.reg.Add(Route{Method: "GET", Path: "/api/v1/handoffs", Cap: auth.IncidentRead, Handler: s.handoffsList})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/handoffs/{id}/approve", Cap: auth.HandoffApprove, Handler: s.handoffApprove})
	s.reg.Add(Route{Method: "POST", Path: "/api/v1/handoffs/{id}/reject", Cap: auth.HandoffApprove, Handler: s.handoffReject})
}

// decisionBody es el cuerpo de aprobar y rechazar. Solo lleva la nota: quién
// decide lo dice la sesión, no el cliente.
type decisionBody struct {
	Note string `json:"note"`
}

func handoffStatusesHint() string {
	names := make([]string, len(playbook.HandoffStatuses))
	for i, st := range playbook.HandoffStatuses {
		names[i] = string(st)
	}
	return strings.Join(names, "|")
}

func validHandoffStatus(s string) bool {
	for _, st := range playbook.HandoffStatuses {
		if string(st) == s {
			return true
		}
	}
	return false
}

// sortHandoffs deja arriba lo que espera decisión humana y, dentro de cada
// grupo, lo más reciente primero: la bandeja se abre para decidir, no para
// leer historia.
func sortHandoffs(hs []playbook.Handoff) {
	sort.SliceStable(hs, func(i, j int) bool {
		pi, pj := hs[i].Status == playbook.HandoffPending, hs[j].Status == playbook.HandoffPending
		if pi != pj {
			return pi
		}
		return hs[i].RequestedAt.After(hs[j].RequestedAt)
	})
}

// handoffsList publica la bandeja. Un status desconocido es un 400 y no una
// lista vacía: en una bandeja de aprobaciones, "no hay nada" y "has escrito
// mal el filtro" no pueden parecer lo mismo.
func (s *server) handoffsList(w http.ResponseWriter, r *http.Request, _ *auth.Principal) {
	want := strings.TrimSpace(r.URL.Query().Get("status"))
	if want != "" && !validHandoffStatus(want) {
		writeError(w, http.StatusBadRequest, "invalid",
			fmt.Sprintf("estado desconocido %q (usa %s)", want, handoffStatusesHint()))
		return
	}
	hs, err := s.org().Handoffs()
	if err != nil {
		s.fail(w, "handoffs.list", err)
		return
	}
	out := make([]playbook.Handoff, 0, len(hs))
	for _, h := range hs {
		if want == "" || string(h.Status) == want {
			out = append(out, h)
		}
	}
	sortHandoffs(out)
	writeJSON(w, http.StatusOK, map[string]any{"items": out, "total": len(out)})
}

func (s *server) handoffApprove(w http.ResponseWriter, r *http.Request, p *auth.Principal) {
	s.decideHandoff(w, r, p, playbook.HandoffApproved)
}

func (s *server) handoffReject(w http.ResponseWriter, r *http.Request, p *auth.Principal) {
	s.decideHandoff(w, r, p, playbook.HandoffRejected)
}

// decideHandoff resuelve las dos decisiones. Aprobar ejecuta la acción POR
// LOS GUARDARRAÍLES (engine.ApproveHandoff): la respuesta lleva el handoff
// entero con su action.Result dentro, con dry_run si la organización sigue
// en observe y con blocked si faltaba la llave de wipe, para que el
// aprobador vea qué ha pasado en lugar de un OK genérico.
func (s *server) decideHandoff(w http.ResponseWriter, r *http.Request, p *auth.Principal, to playbook.HandoffStatus) {
	var body decisionBody
	// La nota es opcional: un cuerpo vacío es una decisión sin comentario.
	if r.ContentLength != 0 {
		if err := decodeJSON(r, &body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid", err.Error())
			return
		}
	}
	id, by := pathID(r), actorOf(p)
	var (
		h   playbook.Handoff
		err error
	)
	if to == playbook.HandoffApproved {
		h, err = s.d.Engine.ApproveHandoff(r.Context(), id, by, body.Note)
	} else {
		h, err = s.d.Engine.RejectHandoff(r.Context(), id, by, body.Note)
	}
	if err == nil {
		writeJSON(w, http.StatusOK, h)
		return
	}
	s.writeEngineActionError(w, "handoffs."+string(to), h.DeviceID, h.Action, err)
}

// writeEngineActionError traduce los centinelas de T16 a la respuesta HTTP.
// engine.ErrActionBlocked no aparece aquí a propósito: un bloqueo del
// guardarraíl no es un error de la petición y lo resuelve cada llamante con
// un 200 y el resultado dentro.
func (s *server) writeEngineActionError(w http.ResponseWriter, op, deviceID string, a action.Action, err error) {
	switch {
	case errors.Is(err, engine.ErrHandoffNotFound), errors.Is(err, engine.ErrDeviceNotFound):
		writeError(w, http.StatusNotFound, "not_found", err.Error())
	case errors.Is(err, engine.ErrHandoffDecided):
		writeError(w, http.StatusConflict, "conflict", err.Error())
	case errors.Is(err, engine.ErrActionSuppressed):
		writeErrorDetail(w, http.StatusConflict, "cooldown", err.Error(), s.cooldownDetail(deviceID, a))
	default:
		s.fail(w, op, err)
	}
}

// cooldownDetail dice cuándo volverá a estar disponible una acción suprimida
// por cooldown. Una supresión no deja rastro en actions.jsonl (T12), así que
// el instante es lo único útil que la API puede devolver. Si no hay marca o
// la ventana está apagada, el 409 va sin detalle antes que con una fecha
// inventada.
func (s *server) cooldownDetail(deviceID string, a action.Action) any {
	set, err := s.org().Settings()
	if err != nil || set.Enforcement.ActionCooldownSeconds <= 0 {
		return nil
	}
	last, ok := s.org().LastActionAt(deviceID, a)
	if !ok {
		return nil
	}
	window := time.Duration(set.Enforcement.ActionCooldownSeconds) * time.Second
	return map[string]any{"retry_after": last.Add(window).UTC().Format(time.RFC3339)}
}
