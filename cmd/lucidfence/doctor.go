package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/adrimg3196/lucidfence/internal/auth"
	"github.com/adrimg3196/lucidfence/internal/store"
	"github.com/adrimg3196/lucidfence/internal/version"
	"github.com/adrimg3196/lucidfence/internal/web"
)

type check struct {
	Name     string
	OK       bool
	Severity string // error | warning
	Detail   string
}

// healthReport es lo que doctor mira de /api/v1/health. persistence es un
// puntero para distinguir "el servidor dice que la persistencia está sana"
// de "el servidor no informa de la persistencia".
type healthReport struct {
	Persistence *struct {
		OK        bool   `json:"ok"`
		LastError string `json:"last_error"`
	} `json:"persistence"`
}

func fetchHealth(listen string, timeout time.Duration) (healthReport, bool) {
	var h healthReport
	c := http.Client{Timeout: timeout}
	res, err := c.Get("http://" + dialAddr(listen) + "/api/v1/health")
	if err != nil {
		return h, false
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode != 200 {
		return h, false
	}
	// Un cuerpo ilegible no invalida el sondeo: el servidor responde, que es
	// lo que comprueba la fila "servidor"; solo se queda sin datos de salud.
	_ = json.NewDecoder(io.LimitReader(res.Body, 1<<20)).Decode(&h)
	return h, true
}

func healthy(listen string, timeout time.Duration) bool {
	_, ok := fetchHealth(listen, timeout)
	return ok
}

// persistenceCheck traduce health.persistence a una fila de doctor: si el
// servidor no puede guardar, el operador tiene que verlo aquí y no solo en
// el log del motor (spec §11, "doctor lo explica").
func persistenceCheck(h healthReport) check {
	if h.Persistence == nil {
		return check{Name: "persistencia", Severity: "warning", Detail: "el servidor no informa del estado de persistencia"}
	}
	if h.Persistence.OK {
		return check{Name: "persistencia", OK: true, Detail: "el servidor guarda sin errores"}
	}
	detail := "el servidor no consigue guardar en el directorio de la organización"
	if h.Persistence.LastError != "" {
		detail += ": " + h.Persistence.LastError
	}
	return check{Name: "persistencia", Severity: "error", Detail: detail}
}

func doctorChecks(f commonFlags) []check {
	var out []check
	out = append(out, check{Name: "binario", OK: true, Detail: version.String()})
	cfg, err := loadConfig(f)
	if err != nil {
		return append(out, check{Name: "config.json", Severity: "error", Detail: err.Error()})
	}
	out = append(out, check{Name: "config.json", OK: true, Detail: fmt.Sprintf("%s (modo %s, intervalo %ds, listen %s)", f.ConfigPath, cfg.Mode, cfg.IntervalSeconds, cfg.Listen)})
	st, err := store.Open(cfg.DataDir)
	if err != nil {
		return append(out, check{Name: "directorio de datos", Severity: "error", Detail: err.Error()})
	}
	probe := filepath.Join(st.Root(), ".doctor-probe")
	if err := os.WriteFile(probe, []byte("ok"), 0o600); err != nil {
		out = append(out, check{Name: "directorio de datos", Severity: "error", Detail: "no escribible: " + err.Error()})
	} else {
		_ = os.Remove(probe)
		out = append(out, check{Name: "directorio de datos", OK: true, Detail: st.Root()})
	}
	if web.IsBuilt(web.Dist()) {
		out = append(out, check{Name: "dashboard embebido", OK: true, Detail: "compilado"})
	} else {
		out = append(out, check{Name: "dashboard embebido", Severity: "warning", Detail: "este binario no lleva el dashboard (make web build); la API funciona"})
	}
	if org, err := st.Org(cfg.Org); err == nil {
		if _, err := os.Stat(org.Path("seed.json")); err == nil {
			out = append(out, check{Name: "seed de simulación", OK: true, Detail: org.Path("seed.json")})
		} else {
			out = append(out, check{Name: "seed de simulación", Severity: "warning", Detail: "sin seed.json; se usará la flota demo embebida"})
		}
	} else {
		out = append(out, check{Name: "seed de simulación", Severity: "error", Detail: err.Error()})
	}
	if as, err := auth.Open(st.AuthDir(), time.Now); err == nil {
		if as.HasUsers() {
			out = append(out, check{Name: "usuarios", OK: true, Detail: "owner creado"})
		} else {
			out = append(out, check{Name: "usuarios", Severity: "warning", Detail: "pendiente el asistente inicial (abre el dashboard)"})
		}
	} else {
		out = append(out, check{Name: "usuarios", Severity: "error", Detail: err.Error()})
	}
	if h, ok := fetchHealth(cfg.Listen, 2*time.Second); ok {
		out = append(out, check{Name: "servidor", OK: true, Detail: "responde en http://" + dialAddr(cfg.Listen)}, persistenceCheck(h))
	} else {
		out = append(out, check{Name: "servidor", Severity: "warning", Detail: "no responde en http://" + dialAddr(cfg.Listen) + "; arranca con lucidfence serve"})
	}
	return out
}

func runDoctor(args []string, stdout, stderr io.Writer) int {
	f, fs, err := parseCommon("doctor", args, stderr, nil)
	if err != nil {
		return 2
	}
	if rejectPositional("doctor", fs, stderr) {
		return 2
	}
	code := 0
	for _, c := range doctorChecks(f) {
		mark := "OK  "
		if !c.OK {
			mark = "WARN"
			if c.Severity == "error" {
				mark, code = "FAIL", 1
			}
		}
		_, _ = fmt.Fprintf(stdout, "%s  %-22s %s\n", mark, c.Name, c.Detail)
	}
	return code
}
