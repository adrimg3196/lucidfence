// Package device es el modelo normalizado de dispositivo que produce todo
// conector y consume el motor. Los campos que el UEM no informa son nil, no
// cero: el riesgo nunca penaliza lo desconocido.
package device

import (
	"errors"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

// FenceState es la relación del dispositivo con las geocercas.
type FenceState string

// RouteState es la relación con su ruta asignada.
type RouteState string

const (
	Inside  FenceState = "inside"
	Outside FenceState = "outside"
	Unknown FenceState = "unknown"

	OnRoute    RouteState = "on_route"
	OffRoute   RouteState = "off_route"
	Unassigned RouteState = "unassigned"
)

// Location es la última ubicación conocida.
type Location struct {
	Point      *geo.Point `json:"point,omitempty"`
	AccuracyM  *float64   `json:"accuracy_m,omitempty"`
	Source     string     `json:"source"`
	ObservedAt time.Time  `json:"observed_at"`
}

// Network son las señales de red del dispositivo.
type Network struct {
	IP    string `json:"ip,omitempty"`
	SSID  string `json:"ssid,omitempty"`
	BSSID string `json:"bssid,omitempty"`
}

// App es una aplicación instalada.
type App struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

// Inventory es la ficha de IT del dispositivo.
type Inventory struct {
	OSVersion         string     `json:"os_version,omitempty"`
	Model             string     `json:"model,omitempty"`
	Manufacturer      string     `json:"manufacturer,omitempty"`
	SerialNumber      string     `json:"serial_number,omitempty"`
	IMEI              string     `json:"imei,omitempty"`
	BatteryLevel      *int       `json:"battery_level,omitempty"`
	BatteryState      string     `json:"battery_state,omitempty"`
	StorageTotalGB    *float64   `json:"storage_total_gb,omitempty"`
	StorageFreeGB     *float64   `json:"storage_free_gb,omitempty"`
	EncryptionEnabled *bool      `json:"encryption_enabled,omitempty"`
	Carrier           string     `json:"carrier,omitempty"`
	AssignedUser      string     `json:"assigned_user,omitempty"`
	Department        string     `json:"department,omitempty"`
	DeviceTag         string     `json:"device_tag,omitempty"`
	EnrolledAt        *time.Time `json:"enrolled_at,omitempty"`
	LastCheckin       *time.Time `json:"last_checkin,omitempty"`
	ManagementMode    string     `json:"management_mode,omitempty"`
	Ownership         string     `json:"ownership,omitempty"`
	Supervised        *bool      `json:"supervised,omitempty"`
	LockdownMode      *bool      `json:"lockdown_mode,omitempty"`
	Apps              []App      `json:"apps,omitempty"`
}

// Verdict es el veredicto de riesgo explicable. Score nil = sin evaluar o
// evaluación fallida (nunca 0 por defecto).
type Verdict struct {
	Score           *float64   `json:"score"`
	Severity        string     `json:"severity"`
	Reasons         []string   `json:"reasons"`
	MatchedPolicies []string   `json:"matched_policies"`
	EvaluatedAt     *time.Time `json:"evaluated_at,omitempty"`
	Provenance      string     `json:"provenance"`
	Verified        bool       `json:"verified"`
}

// Device es el dispositivo normalizado.
type Device struct {
	ID              string            `json:"id"`
	Name            string            `json:"name"`
	Platform        string            `json:"platform"`
	Status          string            `json:"status,omitempty"`
	Compliant       *bool             `json:"compliant"`
	Provider        string            `json:"provider"`
	ProviderRefs    map[string]string `json:"provider_refs,omitempty"`
	Location        Location          `json:"location"`
	Network         Network           `json:"network"`
	Inventory       Inventory         `json:"inventory"`
	FenceState      FenceState        `json:"fence_state"`
	InsideFence     string            `json:"inside_fence"`
	LastInsideFence string            `json:"last_inside_fence"`
	RouteID         string            `json:"route_id,omitempty"`
	RouteState      RouteState        `json:"route_state"`
	RouteDeviationM *float64          `json:"route_deviation_m,omitempty"`
	Risk            Verdict           `json:"risk"`
	EvaluationError string            `json:"evaluation_error,omitempty"`
	LastReportAt    time.Time         `json:"last_report_at"`
}

// TrailPoint es una posición histórica.
type TrailPoint struct {
	At    time.Time `json:"at"`
	Point geo.Point `json:"point"`
}

// Validate exige id.
func (d Device) Validate() error {
	if d.ID == "" {
		return errors.New("dispositivo sin id")
	}
	return nil
}

// Index indexa por id.
func Index(ds []Device) map[string]Device {
	out := make(map[string]Device, len(ds))
	for _, d := range ds {
		out[d.ID] = d
	}
	return out
}
