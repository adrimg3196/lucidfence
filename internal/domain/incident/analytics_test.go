package incident

import (
	"strings"
	"testing"
	"time"
)

func TestAnalyzeSinIncidentesNoInventaNada(t *testing.T) {
	a := Analyze(nil, t0)
	if a.Total != 0 || a.Open != 0 || a.Ack != 0 || a.Closed != 0 {
		t.Fatalf("contadores: %+v", a)
	}
	if a.MTTRSeconds != nil {
		t.Fatalf("sin ningún cerrado el MTTR es nil, jamás 0: %v", *a.MTTRSeconds)
	}
	if len(a.BySeverity) != 4 || a.BySeverity["critical"] != 0 {
		t.Fatalf("las cuatro severidades salen a cero: %+v", a.BySeverity)
	}
	if len(a.ByKind) != len(Kinds) || a.ByKind[KindGeofenceExit] != 0 {
		t.Fatalf("los siete tipos salen a cero: %+v", a.ByKind)
	}
	if len(a.ByDay) != AnalyticsDays || a.ByDay[AnalyticsDays-1].Day != "2026-09-06" || a.ByDay[0].Day != "2026-08-08" {
		t.Fatalf("serie diaria de 30 días acabada hoy: %+v", a.ByDay)
	}
	if len(a.TopDevices) != 0 {
		t.Fatalf("sin incidentes no hay ranking: %+v", a.TopDevices)
	}
}

func TestAnalyzeMTTRSoloConCerradosSellados(t *testing.T) {
	a := Analyze([]Incident{
		sample("inc-open", StatusOpen),
		sample("inc-ack", StatusAck),
		sample("inc-sin-sello", StatusClosed),
	}, t0)
	if a.Total != 3 || a.Open != 1 || a.Ack != 1 || a.Closed != 1 {
		t.Fatalf("contadores por estado: %+v", a)
	}
	if a.MTTRSeconds != nil {
		t.Fatalf("un cerrado sin closed_at no es una medida: %v", *a.MTTRSeconds)
	}

	fast := sample("inc-fast", StatusClosed)
	fastEnd := t0.Add(10 * time.Minute)
	fast.ClosedAt = &fastEnd
	slow := sample("inc-slow", StatusClosed)
	slowEnd := t0.Add(30 * time.Minute)
	slow.ClosedAt = &slowEnd
	a = Analyze([]Incident{fast, slow}, t0)
	if a.MTTRSeconds == nil || *a.MTTRSeconds != 1200 {
		t.Fatalf("media de 600 s y 1800 s: %v", a.MTTRSeconds)
	}
}

func TestAnalyzeSerieDiariaYTopDispositivos(t *testing.T) {
	hoy := sample("inc-hoy", StatusOpen)
	ayer := sample("inc-ayer", StatusOpen)
	ayer.OpenedAt = t0.AddDate(0, 0, -1)
	viejo := sample("inc-viejo", StatusOpen)
	viejo.OpenedAt = t0.AddDate(0, 0, -60)
	otro := sample("inc-otro", StatusOpen)
	otro.DeviceID, otro.DeviceName = "dev-2", "Portátil"

	a := Analyze([]Incident{hoy, ayer, viejo, otro}, t0)
	if a.ByDay[AnalyticsDays-1].Count != 2 || a.ByDay[AnalyticsDays-2].Count != 1 {
		t.Fatalf("hoy dos y ayer uno: %+v", a.ByDay[AnalyticsDays-2:])
	}
	sum := 0
	for _, d := range a.ByDay {
		sum += d.Count
	}
	if sum != 3 {
		t.Fatalf("lo anterior a la ventana no se cuela en la serie: %d", sum)
	}
	if len(a.TopDevices) != 2 || a.TopDevices[0].DeviceID != "dev-1" || a.TopDevices[0].Count != 3 {
		t.Fatalf("ranking de dispositivos: %+v", a.TopDevices)
	}
	if a.TopDevices[1].DeviceName != "Portátil" || a.TopDevices[1].Count != 1 {
		t.Fatalf("segundo del ranking: %+v", a.TopDevices[1])
	}
}

func TestAnalyzeCuentaLaSeveridadAusenteComoDesconocida(t *testing.T) {
	sin := sample("inc-sin-sev", StatusOpen)
	sin.Severity = ""
	a := Analyze([]Incident{sin}, t0)
	if a.BySeverity["unknown"] != 1 || a.BySeverity["high"] != 0 {
		t.Fatalf("la severidad ausente jamás se pinta como buena: %+v", a.BySeverity)
	}
}

func TestToCSVEscapaComillasYComas(t *testing.T) {
	inc := sample("inc-a", StatusOpen)
	inc.Title = `Tablet "Uno", fuera de geocerca`
	inc.RiskScore = f64Ptr(91.5)
	acked, err := inc.Transition(StatusAck, "usr-1", "soc@acme.test", "Triaje, en curso", t0.Add(time.Minute))
	if err != nil {
		t.Fatal(err)
	}
	out := string(ToCSV([]Incident{acked}))
	lines := strings.Split(strings.TrimRight(out, "\n"), "\n")
	if len(lines) != 2 {
		t.Fatalf("cabecera más una fila: %q", out)
	}
	if !strings.HasPrefix(lines[0], "id,dispositivo_id,dispositivo,tipo,severidad,estado,titulo,geocerca,asignado,riesgo") {
		t.Fatalf("cabecera en español: %q", lines[0])
	}
	if !strings.Contains(lines[1], `"Tablet ""Uno"", fuera de geocerca"`) {
		t.Fatalf("comillas dobladas y campo entrecomillado: %q", lines[1])
	}
	if !strings.Contains(lines[1], `"usr-1: Triaje, en curso"`) {
		t.Fatalf("última nota de la auditoría: %q", lines[1])
	}
	if !strings.Contains(lines[1], "91.5") || !strings.Contains(lines[1], "2026-09-06T10:01:00Z") {
		t.Fatalf("riesgo y marcas en RFC 3339: %q", lines[1])
	}
}

func TestToCSVSinIncidentesSoloCabecera(t *testing.T) {
	out := string(ToCSV(nil))
	if strings.Count(out, "\n") != 1 || !strings.HasSuffix(out, "ultima_nota\n") {
		t.Fatalf("solo la cabecera: %q", out)
	}
}
