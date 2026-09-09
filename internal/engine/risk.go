package engine

import (
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
	"github.com/adrimg3196/lucidfence/internal/domain/integrity"
	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

// riskContext construye el contexto de riesgo del ciclo: el reloj es el del
// motor y los turnos, el riesgo de zona y la jornada salen de los ajustes que
// applySettings dejó vigentes al empezar el ciclo. Los mapas se copian: quien
// reciba el contexto no puede mutar la configuración viva del motor.
func (e *Engine) riskContext(now time.Time) risk.Context {
	e.stateMu.RLock()
	cfg := e.riskCfg
	e.stateMu.RUnlock()
	ctx := risk.DefaultContext(now)
	ctx.OffHoursStart, ctx.OffHoursEnd = cfg.OffHoursStart, cfg.OffHoursEnd
	ctx.ShiftZones = make(map[string]string, len(cfg.ShiftZones))
	for dev, zone := range cfg.ShiftZones {
		ctx.ShiftZones[dev] = zone
	}
	ctx.ZoneRisk = make(map[string]float64, len(cfg.ZoneRisk))
	for zone, value := range cfg.ZoneRisk {
		ctx.ZoneRisk[zone] = value
	}
	return ctx
}

// evaluateRisk fija la integridad de ubicación, las señales y el veredicto del
// dispositivo. El orden no es negociable: primero la integridad, que compara
// contra el estado previo persistido con NUESTRO reloj (nunca con el last_seen
// que controla el dispositivo, para que un spoofer no pueda diluir la
// velocidad entre reportes); después las señales, que leen esa integridad; y
// por último el veredicto, que solo puede afirmar lo que las señales
// atestiguan. Corre dentro del recover() por dispositivo de evaluateDevice: si
// algo revienta, el dispositivo queda con risk.Failed, jamás con un 0/low.
func (e *Engine) evaluateRisk(prev *device.Device, cur *device.Device, now time.Time) {
	cur.LocationIntegrity = integrity.Assess(*cur, prev, now)
	sig := risk.Compute(*cur, e.riskContext(now))
	cur.Signals = sig.Raw()
	cur.Risk = risk.Evaluate(*cur, sig, now)
}

// countRisk suma un dispositivo ya evaluado a las estadísticas del ciclo. Un
// veredicto sin score es un fallo, no un cero: cuenta en risk_failed y su
// severidad viaja como "unknown" en el reparto, nunca como low.
func countRisk(st *CycleStats, d device.Device) {
	if st.BySeverity == nil {
		st.BySeverity = map[string]int{}
	}
	severity := d.Risk.Severity
	if severity == "" {
		severity = risk.SeverityUnknown
	}
	st.BySeverity[severity]++
	if d.Risk.Score == nil {
		st.RiskFailed++
		return
	}
	st.RiskEvaluated++
}
