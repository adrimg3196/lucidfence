// Package alert son las reglas de umbral que una persona administradora define
// para que la flota le avise: fuera de geocerca demasiado tiempo, riesgo por
// encima de X, batería baja. Evalúa una foto de la flota y devuelve disparos;
// el enfriamiento y la entrega viven fuera del dominio (engine y notify).
package alert

import (
	"errors"
	"fmt"
	"math"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// Kind es el tipo de umbral que vigila la regla.
type Kind string

const (
	KindOutsideDuration Kind = "outside_duration"
	KindRiskAbove       Kind = "risk_above"
	KindNonCompliant    Kind = "noncompliant"
	KindBatteryBelow    Kind = "battery_below"
	KindStorageLow      Kind = "storage_low"
	KindStaleCheckin    Kind = "stale_checkin"
)

// Kinds enumera los tipos en orden estable (selector del editor).
var Kinds = []Kind{
	KindOutsideDuration, KindRiskAbove, KindNonCompliant,
	KindBatteryBelow, KindStorageLow, KindStaleCheckin,
}

// IDPattern es el formato del identificador de una regla (slug).
var IDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,63}$`)

// MaxPercentThreshold acota los umbrales expresados en escala 0-100: por
// encima la regla no podría dispararse jamás y sería una alerta muerta.
const MaxPercentThreshold = 100.0

var (
	// ErrKind indica un tipo de alerta fuera de Kinds.
	ErrKind = errors.New("tipo de alerta desconocido")
	// ErrThreshold indica un umbral que no es un número usable.
	ErrThreshold = errors.New("umbral inválido")
)

// Rule es una regla de alerta configurada por la organización.
type Rule struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Kind      Kind      `json:"kind"`
	Threshold float64   `json:"threshold"`
	Severity  string    `json:"severity"`
	Enabled   bool      `json:"enabled"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// Firing es un disparo de una regla sobre un dispositivo concreto.
type Firing struct {
	At         time.Time `json:"at"`
	RuleID     string    `json:"rule_id"`
	RuleName   string    `json:"rule_name"`
	Kind       Kind      `json:"kind"`
	DeviceID   string    `json:"device_id"`
	DeviceName string    `json:"device_name"`
	Severity   string    `json:"severity"`
	Reason     string    `json:"reason"`
	Value      float64   `json:"value"`
}

// Validate comprueba id, nombre, tipo, severidad y umbral.
func (r Rule) Validate() error {
	if !IDPattern.MatchString(r.ID) {
		return fmt.Errorf("id %q inválido: usa minúsculas, dígitos y guiones", r.ID)
	}
	if strings.TrimSpace(r.Name) == "" {
		return fmt.Errorf("la regla %s necesita nombre", r.ID)
	}
	if !validKind(r.Kind) {
		return fmt.Errorf("%w en la regla %s: %q", ErrKind, r.ID, string(r.Kind))
	}
	if !validSeverity(r.Severity) {
		return fmt.Errorf("severidad %q inválida en la regla %s", r.Severity, r.ID)
	}
	return r.validateThreshold()
}

func (r Rule) validateThreshold() error {
	t := r.Threshold
	if math.IsNaN(t) || math.IsInf(t, 0) {
		return fmt.Errorf("%w en la regla %s: no es un número finito", ErrThreshold, r.ID)
	}
	if t < 0 {
		return fmt.Errorf("%w en la regla %s: %s es negativo", ErrThreshold, r.ID, numText(t))
	}
	switch r.Kind {
	case KindRiskAbove, KindBatteryBelow:
		if t > MaxPercentThreshold {
			return fmt.Errorf("%w en la regla %s: %s no cabe en la escala 0-%s",
				ErrThreshold, r.ID, numText(t), numText(MaxPercentThreshold))
		}
	}
	return nil
}

// ValidateAll valida el conjunto y rechaza ids repetidos.
func ValidateAll(rs []Rule) error {
	seen := make(map[string]bool, len(rs))
	for _, r := range rs {
		if err := r.Validate(); err != nil {
			return err
		}
		if seen[r.ID] {
			return fmt.Errorf("regla de alerta duplicada: %s", r.ID)
		}
		seen[r.ID] = true
	}
	return nil
}

// FindByID busca por id.
func FindByID(rs []Rule, id string) (Rule, bool) {
	for _, r := range rs {
		if r.ID == id {
			return r, true
		}
	}
	return Rule{}, false
}

// Evaluate cruza las reglas habilitadas con la foto de la flota. El orden es
// determinista: las reglas en el suyo y, dentro de cada una, los dispositivos
// en el suyo.
func Evaluate(rs []Rule, ds []device.Device, at time.Time) []Firing {
	out := []Firing{}
	for _, r := range rs {
		if !r.Enabled {
			continue
		}
		measure, ok := measures[r.Kind]
		if !ok {
			continue
		}
		for _, d := range ds {
			if d.ID == "" {
				continue
			}
			value, reason, fired := measure(r, d, at)
			if !fired {
				continue
			}
			out = append(out, Firing{
				At: at, RuleID: r.ID, RuleName: r.Name, Kind: r.Kind,
				DeviceID: d.ID, DeviceName: deviceName(d), Severity: r.Severity,
				Reason: reason, Value: value,
			})
		}
	}
	return out
}

// measures asocia cada tipo con su medidor. Un tipo sin medidor no dispara,
// nunca hace panic.
var measures = map[Kind]func(Rule, device.Device, time.Time) (float64, string, bool){
	KindOutsideDuration: outsideDuration,
	KindRiskAbove:       riskAbove,
	KindNonCompliant:    nonCompliant,
	KindBatteryBelow:    batteryBelow,
	KindStorageLow:      storageLow,
	KindStaleCheckin:    staleCheckin,
}

// outsideDuration mide los minutos que el dispositivo lleva fuera de geocerca.
// Dentro, o sin ubicación conocida, no hay nada que medir.
func outsideDuration(r Rule, d device.Device, _ time.Time) (float64, string, bool) {
	if d.FenceState != device.Outside {
		return 0, "", false
	}
	minutes := round1(float64(d.DwellSeconds) / 60)
	if minutes < r.Threshold {
		return 0, "", false
	}
	return minutes, "fuera de geocerca " + numText(minutes) + " min (umbral " + numText(r.Threshold) + " min)", true
}

// riskAbove compara el veredicto persistido. Un score nil es riesgo desconocido
// y lo desconocido jamás se presenta como señal, ni buena ni mala: no dispara.
func riskAbove(r Rule, d device.Device, _ time.Time) (float64, string, bool) {
	if d.Risk.Score == nil {
		return 0, "", false
	}
	score := round1(*d.Risk.Score)
	if score < r.Threshold {
		return 0, "", false
	}
	return score, "riesgo " + numText(score) + " (umbral " + numText(r.Threshold) + ")", true
}

// nonCompliant solo dispara con un incumplimiento explícito: compliant nil es
// "el UEM no lo informa", no "no cumple".
func nonCompliant(_ Rule, d device.Device, _ time.Time) (float64, string, bool) {
	if d.Compliant == nil || *d.Compliant {
		return 0, "", false
	}
	return 1, "el dispositivo no cumple la política UEM", true
}

func batteryBelow(r Rule, d device.Device, _ time.Time) (float64, string, bool) {
	if d.Inventory.BatteryLevel == nil {
		return 0, "", false
	}
	level := float64(*d.Inventory.BatteryLevel)
	if level >= r.Threshold {
		return 0, "", false
	}
	return level, "batería " + numText(level) + " % (umbral < " + numText(r.Threshold) + " %)", true
}

func storageLow(r Rule, d device.Device, _ time.Time) (float64, string, bool) {
	if d.Inventory.StorageFreeGB == nil {
		return 0, "", false
	}
	free := round1(*d.Inventory.StorageFreeGB)
	if free >= r.Threshold {
		return 0, "", false
	}
	return free, "almacenamiento libre " + numText(free) + " GB (umbral < " + numText(r.Threshold) + " GB)", true
}

// staleCheckin mide la antigüedad del último reporte. Sin ningún reporte la
// antigüedad es desconocida, no infinita: no dispara.
func staleCheckin(r Rule, d device.Device, at time.Time) (float64, string, bool) {
	if d.LastReportAt.IsZero() {
		return 0, "", false
	}
	minutes := round1(at.Sub(d.LastReportAt).Minutes())
	if minutes < r.Threshold {
		return 0, "", false
	}
	return minutes, "sin reportar desde hace " + numText(minutes) + " min (umbral " + numText(r.Threshold) + " min)", true
}

func validKind(k Kind) bool {
	for _, v := range Kinds {
		if v == k {
			return true
		}
	}
	return false
}

func validSeverity(s string) bool {
	for _, v := range risk.Severities {
		if v == s {
			return true
		}
	}
	return false
}

func deviceName(d device.Device) string {
	if d.Name != "" {
		return d.Name
	}
	return d.ID
}

// round1 redondea a un decimal para que el valor del disparo y el número que
// aparece en el motivo sean siempre el mismo.
func round1(v float64) float64 {
	return math.Round(v*10) / 10
}

func numText(v float64) string {
	return strconv.FormatFloat(v, 'f', -1, 64)
}
