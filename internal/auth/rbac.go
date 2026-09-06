// Package auth cubre usuarios locales, sesiones con CSRF, token local para
// CLI/MCP y la matriz de roles y capacidades (spec §6.2-§6.3).
package auth

import (
	"fmt"
	"sort"
)

// Role es un rol dentro de una organización.
type Role string

// Capability es un permiso grueso que cada ruta declara.
type Capability string

const (
	Owner    Role = "owner"
	Admin    Role = "admin"
	Operator Role = "operator"
	Viewer   Role = "viewer"
	Auditor  Role = "auditor"
)

const (
	OrgRead        Capability = "org:read"
	OrgUpdate      Capability = "org:update"
	OrgDelete      Capability = "org:delete"
	UserInvite     Capability = "user:invite"
	UserRemove     Capability = "user:remove"
	UserRole       Capability = "user:role"
	APIKeyManage   Capability = "apikey:manage"
	DeviceRead     Capability = "device:read"
	DeviceWrite    Capability = "device:write"
	DeviceAction   Capability = "device:action"
	FenceRead      Capability = "fence:read"
	FenceWrite     Capability = "fence:write"
	FenceDelete    Capability = "fence:delete"
	RouteRead      Capability = "route:read"
	RouteWrite     Capability = "route:write"
	RouteDelete    Capability = "route:delete"
	PolicyRead     Capability = "policy:read"
	PolicyWrite    Capability = "policy:write"
	EngineRun      Capability = "engine:run"
	EngineConfig   Capability = "engine:config"
	IncidentRead   Capability = "incident:read"
	IncidentWrite  Capability = "incident:write"
	AlertWrite     Capability = "alert:write"
	PlaybookWrite  Capability = "playbook:write"
	HandoffApprove Capability = "handoff:approve"
	ReportRead     Capability = "report:read"
	ReportExport   Capability = "report:export"
	AuditRead      Capability = "audit:read"
)

var readCaps = []Capability{OrgRead, DeviceRead, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead}

func set(caps ...Capability) map[Capability]bool {
	m := map[Capability]bool{}
	for _, c := range caps {
		m[c] = true
	}
	return m
}

var roleCaps = map[Role]map[Capability]bool{
	Viewer:   set(readCaps...),
	Auditor:  set(append(readCaps, ReportExport, AuditRead)...),
	Operator: set(append(readCaps, DeviceAction, FenceWrite, RouteWrite, EngineRun, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove)...),
	Admin: set(append(readCaps, OrgUpdate, UserInvite, UserRemove, APIKeyManage, DeviceWrite, DeviceAction, FenceWrite, FenceDelete, RouteWrite, RouteDelete,
		PolicyWrite, EngineRun, EngineConfig, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove, ReportExport, AuditRead)...),
	Owner: set(append(readCaps, OrgUpdate, OrgDelete, UserInvite, UserRemove, UserRole, APIKeyManage, DeviceWrite, DeviceAction, FenceWrite, FenceDelete, RouteWrite,
		RouteDelete, PolicyWrite, EngineRun, EngineConfig, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove, ReportExport, AuditRead)...),
}

// Can indica si el rol tiene la capacidad.
func Can(role Role, c Capability) bool { return roleCaps[role][c] }

// ParseRole valida un rol.
func ParseRole(s string) (Role, error) {
	r := Role(s)
	if _, ok := roleCaps[r]; !ok {
		return "", fmt.Errorf("rol desconocido %q", s)
	}
	return r, nil
}

// Capabilities lista las capacidades de un rol en orden estable.
func Capabilities(role Role) []Capability {
	out := make([]Capability, 0, len(roleCaps[role]))
	for c := range roleCaps[role] {
		out = append(out, c)
	}
	sort.Slice(out, func(i, j int) bool { return out[i] < out[j] })
	return out
}
