package main

import (
	"flag"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/adrimg3196/lucidfence/internal/api"
	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/config"
	"github.com/adrimg3196/lucidfence/internal/engine"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/uem"
	"github.com/adrimg3196/lucidfence/internal/uem/simulation"
	"github.com/adrimg3196/lucidfence/internal/web"
)

type commonFlags struct {
	ConfigPath string
	DataDir    string
	Listen     string
}

func parseCommon(name string, args []string, stderr io.Writer, extra func(*flag.FlagSet)) (commonFlags, *flag.FlagSet, error) {
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	fs.SetOutput(stderr)
	var f commonFlags
	fs.StringVar(&f.ConfigPath, "config", "config.json", "ruta de config.json")
	fs.StringVar(&f.DataDir, "data", "", "directorio de datos (sobrescribe data_dir)")
	fs.StringVar(&f.Listen, "listen", "", "host:puerto (sobrescribe listen)")
	if extra != nil {
		extra(fs)
	}
	if err := fs.Parse(args); err != nil {
		return f, fs, err
	}
	return f, fs, nil
}

type app struct {
	cfg     config.Config
	store   *store.Store
	org     *store.OrgStore
	auth    *auth.Store
	engine  *engine.Engine
	handler http.Handler
	logger  *slog.Logger
}

func loadConfig(f commonFlags) (config.Config, error) {
	cfg, err := config.Load(f.ConfigPath)
	if err != nil {
		return cfg, err
	}
	if f.DataDir != "" {
		cfg.DataDir = f.DataDir
	}
	if f.Listen != "" {
		cfg.Listen = f.Listen
	}
	return cfg, cfg.Validate()
}

func buildAdapters(cfg config.Config, org *store.OrgStore) ([]uem.Adapter, error) {
	reg := uem.NewRegistry()
	reg.Register(simulation.Name, simulation.NewFromConfig)
	if cfg.Mode != "simulation" {
		return nil, fmt.Errorf("el modo %q llega en M3 (conectores reales); usa mode=simulation", cfg.Mode)
	}
	simCfg := map[string]any{}
	if _, err := os.Stat(org.Path("seed.json")); err == nil {
		simCfg["seed_path"] = org.Path("seed.json")
	}
	ad, err := reg.New(simulation.Name, simCfg, nil)
	if err != nil {
		return nil, err
	}
	return []uem.Adapter{ad}, nil
}

func buildApp(f commonFlags, logger *slog.Logger) (*app, error) {
	cfg, err := loadConfig(f)
	if err != nil {
		return nil, err
	}
	st, err := store.Open(cfg.DataDir)
	if err != nil {
		return nil, err
	}
	org, err := st.Org(cfg.Org)
	if err != nil {
		return nil, err
	}
	as, err := auth.Open(st.AuthDir(), time.Now)
	if err != nil {
		return nil, err
	}
	adapters, err := buildAdapters(cfg, org)
	if err != nil {
		return nil, err
	}
	eng := engine.New(org, adapters, engine.Options{Mode: cfg.Mode, Interval: cfg.Interval(), Logger: logger})
	dist := web.Dist()
	handler, _ := api.New(api.Deps{Engine: eng, Org: org, Auth: as, Web: web.Handler(dist), WebBuilt: web.IsBuilt(dist), Config: cfg, Logger: logger})
	return &app{cfg: cfg, store: st, org: org, auth: as, engine: eng, handler: handler, logger: logger}, nil
}

// appForServe construye la app para serve(): el nivel de log solo se conoce
// tras leer config.json, así que carga la config una vez para crear el
// logger con cfg.LogLevel y se la pasa a buildApp, que la vuelve a cargar
// (la doble carga es aceptable; buildApp conserva su firma sin logger
// propio).
func appForServe(f commonFlags, stderr io.Writer) (*app, error) {
	cfg, err := loadConfig(f)
	if err != nil {
		return nil, err
	}
	return buildApp(f, newLogger(cfg.LogLevel, stderr))
}

func newLogger(level string, w io.Writer) *slog.Logger {
	var lvl slog.Level
	_ = lvl.UnmarshalText([]byte(level))
	return slog.New(slog.NewTextHandler(w, &slog.HandlerOptions{Level: lvl}))
}
