package auth

import "testing"

func TestMatrizDeRoles(t *testing.T) {
	cases := []struct {
		role Role
		cap  Capability
		want bool
	}{
		{Owner, OrgDelete, true}, {Admin, OrgDelete, false}, {Owner, UserRole, true}, {Admin, UserRole, false},
		{Admin, APIKeyManage, true}, {Operator, APIKeyManage, false},
		{Operator, DeviceAction, true}, {Operator, DeviceWrite, false}, {Viewer, DeviceRead, true}, {Viewer, DeviceAction, false},
		{Operator, FenceWrite, true}, {Operator, FenceDelete, false}, {Admin, FenceDelete, true},
		{Operator, EngineRun, true}, {Viewer, EngineRun, false}, {Operator, EngineConfig, false}, {Admin, EngineConfig, true},
		{Operator, HandoffApprove, true}, {Auditor, HandoffApprove, false},
		{Auditor, ReportExport, true}, {Viewer, ReportExport, false}, {Auditor, AuditRead, true}, {Operator, AuditRead, false},
		{Auditor, FenceWrite, false}, {Auditor, OrgRead, true},
		{Role("god"), OrgRead, false},
	}
	for _, c := range cases {
		if got := Can(c.role, c.cap); got != c.want {
			t.Errorf("Can(%s, %s)=%v want %v", c.role, c.cap, got, c.want)
		}
	}
}

func TestParseRoleYCapabilities(t *testing.T) {
	if r, err := ParseRole("admin"); err != nil || r != Admin {
		t.Fatal(err)
	}
	if _, err := ParseRole("root"); err == nil {
		t.Fatal("rol desconocido")
	}
	caps := Capabilities(Viewer)
	if len(caps) == 0 || caps[0] != DeviceRead {
		t.Fatalf("Capabilities(viewer) ordenadas: %v", caps)
	}
}
