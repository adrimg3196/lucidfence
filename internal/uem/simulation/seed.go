// Package simulation es el conector de flota simulada: sin red, sin
// dispositivos reales. Mueve cada dispositivo por sus waypoints (un segmento
// cada 3 ciclos, semántica 1.x) y simula toda acción.
package simulation

import (
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/geo"
)

//go:embed default_seed.json
var defaultSeedJSON []byte

// SeedDevice es un dispositivo de la seed.
type SeedDevice struct {
	ID        string           `json:"id"`
	Name      string           `json:"name"`
	Platform  string           `json:"platform"`
	Status    string           `json:"status,omitempty"`
	Compliant *bool            `json:"compliant,omitempty"`
	Country   string           `json:"country,omitempty"`
	City      string           `json:"city,omitempty"`
	IP        string           `json:"ip,omitempty"`
	Waypoints []geo.Point      `json:"waypoints"`
	Inventory device.Inventory `json:"inventory"`
}

// Seed es la flota simulada.
type Seed struct {
	SchemaVersion int          `json:"schema_version"`
	Devices       []SeedDevice `json:"devices"`
}

// DefaultSeed devuelve la flota demo embebida (6 dispositivos en Madrid).
func DefaultSeed() Seed {
	var s Seed
	if err := json.Unmarshal(defaultSeedJSON, &s); err != nil {
		panic("default_seed.json inválida: " + err.Error())
	}
	return s
}

// Validate exige ids únicos, nombre, plataforma y al menos un waypoint válido.
func (s Seed) Validate() error {
	seen := map[string]bool{}
	for i, d := range s.Devices {
		if d.ID == "" || d.Name == "" || d.Platform == "" {
			return fmt.Errorf("dispositivo %d: id, nombre y plataforma obligatorios", i)
		}
		if seen[d.ID] {
			return fmt.Errorf("id duplicado %q", d.ID)
		}
		seen[d.ID] = true
		if len(d.Waypoints) == 0 {
			return fmt.Errorf("dispositivo %q sin waypoints", d.ID)
		}
		for j, w := range d.Waypoints {
			if err := w.Valid(); err != nil {
				return fmt.Errorf("dispositivo %q waypoint %d: %w", d.ID, j, err)
			}
		}
	}
	return nil
}

// LoadSeed lee una seed de disco.
func LoadSeed(path string) (Seed, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Seed{}, err
	}
	var s Seed
	if err := json.Unmarshal(data, &s); err != nil {
		return Seed{}, fmt.Errorf("seed %s: %w", path, err)
	}
	if err := s.Validate(); err != nil {
		return Seed{}, err
	}
	return s, nil
}

// SaveSeed escribe una seed (0600).
func SaveSeed(path string, s Seed) error {
	if err := s.Validate(); err != nil {
		return err
	}
	if s.SchemaVersion == 0 {
		s.SchemaVersion = 1
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}

var errNoSeed = errors.New("seed vacía")
