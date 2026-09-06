package auth

import "testing"

// todasLasCapacidades son las 28 capacidades declaradas en §6.3, en el orden
// de la tabla de la spec. Es el eje "columna" del test: toda capacidad nueva
// tiene que entrar aquí y en capsPorRol, o el test la delata.
var todasLasCapacidades = []Capability{
	OrgRead, OrgUpdate, OrgDelete, UserInvite, UserRemove, UserRole, APIKeyManage,
	DeviceRead, DeviceWrite, DeviceAction,
	FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead,
	FenceWrite, RouteWrite, FenceDelete, RouteDelete, PolicyWrite,
	EngineRun, EngineConfig,
	IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove,
	ReportExport, AuditRead,
}

// capsPorRol es la matriz de la spec §6.3 copiada como dato, fila a fila:
// para cada rol, exactamente las capacidades marcadas con ✓. Lo que no
// aparece debe estar denegado.
var capsPorRol = map[Role][]Capability{
	Viewer: {OrgRead, DeviceRead, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead},
	Auditor: {OrgRead, DeviceRead, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead,
		ReportExport, AuditRead},
	Operator: {OrgRead, DeviceRead, DeviceAction, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead,
		FenceWrite, RouteWrite, EngineRun, IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove},
	Admin: {OrgRead, OrgUpdate, UserInvite, UserRemove, APIKeyManage,
		DeviceRead, DeviceWrite, DeviceAction, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead,
		FenceWrite, RouteWrite, FenceDelete, RouteDelete, PolicyWrite, EngineRun, EngineConfig,
		IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove, ReportExport, AuditRead},
	Owner: {OrgRead, OrgUpdate, OrgDelete, UserInvite, UserRemove, UserRole, APIKeyManage,
		DeviceRead, DeviceWrite, DeviceAction, FenceRead, RouteRead, PolicyRead, IncidentRead, ReportRead,
		FenceWrite, RouteWrite, FenceDelete, RouteDelete, PolicyWrite, EngineRun, EngineConfig,
		IncidentWrite, AlertWrite, PlaybookWrite, HandoffApprove, ReportExport, AuditRead},
}

// TestMatrizDeRolesCompleta recorre las 5 × 28 celdas de la matriz de la
// spec §6.3 contra Can, en vez de muestrear un puñado de combinaciones: la
// matriz es la única frontera de autorización del producto y §12 exige
// comprobarla entera. Con un muestreo, conceder p. ej. fence:write a viewer
// dejaba la suite en verde (hallazgo C22).
func TestMatrizDeRolesCompleta(t *testing.T) {
	for role, caps := range capsPorRol {
		esperadas := set(caps...)
		for _, c := range todasLasCapacidades {
			if got := Can(role, c); got != esperadas[c] {
				t.Errorf("Can(%s, %s)=%v, la spec §6.3 dice %v", role, c, got, esperadas[c])
			}
		}
	}
	// Nada concedido fuera de la tabla: ni roles ni capacidades que la spec
	// §6.3 no contemple (una capacidad nueva sin fila en la tabla pasaría
	// inadvertida por el doble bucle de arriba).
	declaradas := set(todasLasCapacidades...)
	for role, caps := range roleCaps {
		if _, ok := capsPorRol[role]; !ok {
			t.Errorf("rol %s fuera de la tabla de la spec §6.3", role)
		}
		for c := range caps {
			if !declaradas[c] {
				t.Errorf("el rol %s tiene %s, capacidad que no está en la tabla de la spec §6.3", role, c)
			}
		}
	}
	if Can(Role("god"), OrgRead) {
		t.Error("un rol desconocido no tiene ninguna capacidad")
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
