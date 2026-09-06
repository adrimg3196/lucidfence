// Package uem define el contrato que implementa todo conector UEM (spec §5.7).
// Un conector nunca hace panic ni tumba el ciclo: Execute devuelve siempre un
// Result; los errores de inventario se reportan como salud del proveedor.
package uem

import (
	"context"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

// Capabilities declara lo que el conector sabe hacer.
type Capabilities struct {
	Actions   []action.Action `json:"actions"`
	Inventory bool            `json:"inventory"`
	Location  bool            `json:"location"`
	Posture   bool            `json:"posture"`
}

// Supports indica si la acción está soportada.
func (c Capabilities) Supports(a action.Action) bool {
	for _, x := range c.Actions {
		if x == a {
			return true
		}
	}
	return false
}

// ConnectionResult es el resultado de "Probar conexión".
type ConnectionResult struct {
	OK         bool   `json:"ok"`
	Verified   string `json:"verified"`
	ErrorType  string `json:"error_type,omitempty"`
	Error      string `json:"error,omitempty"`
	HTTPStatus int    `json:"http_status,omitempty"`
}

// Adapter es el contrato congelado de conector.
type Adapter interface {
	Name() string
	Capabilities() Capabilities
	FetchDevices(ctx context.Context) ([]device.Device, error)
	Execute(ctx context.Context, dev device.Device, a action.Action, params map[string]any, dryRun bool) action.Result
	TestConnection(ctx context.Context) ConnectionResult
}
