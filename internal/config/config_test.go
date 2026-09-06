package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestDefaultEsValido(t *testing.T) {
	c := Default()
	if err := c.Validate(); err != nil {
		t.Fatal(err)
	}
	if c.Listen != "127.0.0.1:8765" || c.IntervalSeconds != 900 || c.Mode != "simulation" || c.Org != "default" || !c.Map.Enabled || c.Map.TilesURL != DefaultTilesURL || c.Interval() != 15*time.Minute {
		t.Fatalf("%+v", c)
	}
}

func TestLoadAusenteYParcial(t *testing.T) {
	c, err := Load(filepath.Join(t.TempDir(), "nope.json"))
	if err != nil || c.Listen != "127.0.0.1:8765" {
		t.Fatalf("ausente → defaults: %v %+v", err, c)
	}
	path := filepath.Join(t.TempDir(), "config.json")
	_ = os.WriteFile(path, []byte(`{"listen":"127.0.0.1:9000","interval_seconds":60}`), 0o600)
	c, err = Load(path)
	if err != nil || c.Listen != "127.0.0.1:9000" || c.IntervalSeconds != 60 || c.Mode != "simulation" || c.Map.TilesURL != DefaultTilesURL {
		t.Fatalf("parcial rellena defaults: %v %+v", err, c)
	}
	_ = os.WriteFile(path, []byte(`{"listen":"127.0.0.1:9000","modo":"live"}`), 0o600)
	if _, err := Load(path); err == nil || !strings.Contains(err.Error(), "modo") {
		t.Fatalf("campo desconocido debe fallar nombrándolo: %v", err)
	}
}

func TestValidateErroresConCampo(t *testing.T) {
	cases := map[string]func(*Config){
		"mode":      func(c *Config) { c.Mode = "demo" },
		"interval":  func(c *Config) { c.IntervalSeconds = 5 },
		"listen":    func(c *Config) { c.Listen = "no-es-host-port" },
		"org":       func(c *Config) { c.Org = "Default Org" },
		"log_level": func(c *Config) { c.LogLevel = "loud" },
		"tiles_url": func(c *Config) { c.Map.TilesURL = "https://tiles.example/{z}/{x}.png" },
		"data_dir":  func(c *Config) { c.DataDir = "" },
	}
	for name, mut := range cases {
		c := Default()
		mut(&c)
		err := c.Validate()
		if err == nil || !strings.Contains(err.Error(), name) {
			t.Errorf("%s: esperaba error que nombre el campo, got %v", name, err)
		}
	}
	c := Default()
	c.Map.Enabled = false
	c.Map.TilesURL = ""
	if err := c.Validate(); err != nil {
		t.Fatal("mapa desactivado no exige tiles_url")
	}
}

func TestSaveRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.json")
	c := Default()
	c.Listen = "127.0.0.1:1234"
	if err := c.Save(path); err != nil {
		t.Fatal(err)
	}
	got, err := Load(path)
	if err != nil || got.Listen != "127.0.0.1:1234" {
		t.Fatal(err)
	}
}
