// Package config carga y valida config.json (lo no secreto). Los secretos van
// en variables LUCIDFENCE_* o en <data>/secrets/ (spec §5.8).
package config

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"regexp"
	"strings"
	"time"
)

// DefaultTilesURL es el proveedor de tiles por defecto (OSM público).
const DefaultTilesURL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

var orgIDPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,39}$`)

// MapConfig configura el mapa del dashboard.
type MapConfig struct {
	Enabled  bool   `json:"enabled"`
	TilesURL string `json:"tiles_url"`
}

// EgressConfig es la allowlist de salida (M2 la aplica).
type EgressConfig struct {
	Hosts        []string `json:"hosts"`
	AllowPrivate bool     `json:"allow_private"`
}

// Config es la configuración del binario.
type Config struct {
	DataDir         string       `json:"data_dir"`
	Listen          string       `json:"listen"`
	IntervalSeconds int          `json:"interval_seconds"`
	Mode            string       `json:"mode"`
	Org             string       `json:"org"`
	Map             MapConfig    `json:"map"`
	Egress          EgressConfig `json:"egress"`
	LogLevel        string       `json:"log_level"`
}

// Default devuelve la configuración segura de fábrica.
func Default() Config {
	return Config{
		DataDir: "data", Listen: "127.0.0.1:8765", IntervalSeconds: 900, Mode: "simulation", Org: "default",
		Map: MapConfig{Enabled: true, TilesURL: DefaultTilesURL}, Egress: EgressConfig{Hosts: []string{}}, LogLevel: "info",
	}
}

// Load lee config.json; si no existe devuelve Default(). Rechaza campos desconocidos.
func Load(path string) (Config, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return Default(), nil
	}
	if err != nil {
		return Config{}, err
	}
	c := Default()
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&c); err != nil {
		return Config{}, fmt.Errorf("config %s: %w", path, err)
	}
	c.fillDefaults()
	return c, c.Validate()
}

func (c *Config) fillDefaults() {
	d := Default()
	if c.DataDir == "" {
		c.DataDir = d.DataDir
	}
	if c.Listen == "" {
		c.Listen = d.Listen
	}
	if c.IntervalSeconds == 0 {
		c.IntervalSeconds = d.IntervalSeconds
	}
	if c.Mode == "" {
		c.Mode = d.Mode
	}
	if c.Org == "" {
		c.Org = d.Org
	}
	if c.Map.Enabled && c.Map.TilesURL == "" {
		c.Map.TilesURL = d.Map.TilesURL
	}
	if c.LogLevel == "" {
		c.LogLevel = d.LogLevel
	}
	if c.Egress.Hosts == nil {
		c.Egress.Hosts = []string{}
	}
}

// Validate comprueba cada campo y nombra el que falla.
func (c Config) Validate() error {
	if c.DataDir == "" {
		return errors.New("data_dir: obligatorio")
	}
	if c.Mode != "simulation" && c.Mode != "live" {
		return fmt.Errorf("mode: %q no es simulation|live", c.Mode)
	}
	if c.IntervalSeconds < 10 || c.IntervalSeconds > 86400 {
		return fmt.Errorf("interval_seconds: %d fuera de [10, 86400]", c.IntervalSeconds)
	}
	if _, _, err := net.SplitHostPort(c.Listen); err != nil {
		return fmt.Errorf("listen: %q no es host:puerto", c.Listen)
	}
	if !orgIDPattern.MatchString(c.Org) {
		return fmt.Errorf("org: %q inválido (minúsculas, dígitos, guiones)", c.Org)
	}
	switch c.LogLevel {
	case "debug", "info", "warn", "error":
	default:
		return fmt.Errorf("log_level: %q no es debug|info|warn|error", c.LogLevel)
	}
	if c.Map.Enabled {
		for _, ph := range []string{"{z}", "{x}", "{y}"} {
			if !strings.Contains(c.Map.TilesURL, ph) {
				return fmt.Errorf("map.tiles_url: falta %s", ph)
			}
		}
	}
	return nil
}

// Save escribe la configuración con permisos 0600.
func (c Config) Save(path string) error {
	if err := c.Validate(); err != nil {
		return err
	}
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o600)
}

// Interval devuelve el intervalo del ciclo.
func (c Config) Interval() time.Duration { return time.Duration(c.IntervalSeconds) * time.Second }
