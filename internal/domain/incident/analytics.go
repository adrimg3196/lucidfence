package incident

import (
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/risk"
)

const (
	// AnalyticsDays es la ventana de la serie diaria.
	AnalyticsDays = 30
	// TopDevicesLimit es el tamaño del ranking de dispositivos.
	TopDevicesLimit = 5
	// DayLayout es el formato de los días de la serie (UTC).
	DayLayout = "2006-01-02"
)

// DayCount es un punto de la serie diaria.
type DayCount struct {
	Day   string `json:"day"`
	Count int    `json:"count"`
}

// DeviceCount es una fila del ranking de dispositivos.
type DeviceCount struct {
	DeviceID   string `json:"device_id"`
	DeviceName string `json:"device_name"`
	Count      int    `json:"count"`
}

// Analytics resume la cartera de incidentes para el panel.
type Analytics struct {
	Total       int            `json:"total"`
	Open        int            `json:"open"`
	Ack         int            `json:"ack"`
	Closed      int            `json:"closed"`
	BySeverity  map[string]int `json:"by_severity"`
	ByKind      map[string]int `json:"by_kind"`
	ByDay       []DayCount     `json:"by_day"`
	MTTRSeconds *float64       `json:"mttr_seconds"`
	TopDevices  []DeviceCount  `json:"top_devices"`
}

// Analyze calcula el resumen. Un contador a cero es una medida real; un MTTR
// sin ningún incidente cerrado no lo es, y sale nil en vez de 0: un "MTTR 0 s"
// en el panel es un falso verde que parece resolución instantánea.
func Analyze(is []Incident, now time.Time) Analytics {
	a := Analytics{
		Total:      len(is),
		BySeverity: emptyCounts(risk.Severities...),
		ByKind:     emptyCounts(Kinds...),
		ByDay:      emptyDays(now),
		TopDevices: []DeviceCount{},
	}
	days := make(map[string]int, AnalyticsDays)
	perDevice := make(map[string]DeviceCount, len(is))
	var totalSeconds float64
	var measured int
	for _, inc := range is {
		countStatus(&a, inc.Status)
		a.BySeverity[severityKey(inc.Severity)]++
		a.ByKind[inc.Kind]++
		days[inc.OpenedAt.UTC().Format(DayLayout)]++
		accumulateDevice(perDevice, inc)
		if secs, ok := resolution(inc); ok {
			totalSeconds += secs
			measured++
		}
	}
	for i := range a.ByDay {
		a.ByDay[i].Count = days[a.ByDay[i].Day]
	}
	if measured > 0 {
		mean := totalSeconds / float64(measured)
		a.MTTRSeconds = &mean
	}
	a.TopDevices = topDevices(perDevice)
	return a
}

func countStatus(a *Analytics, s Status) {
	switch s {
	case StatusOpen:
		a.Open++
	case StatusAck:
		a.Ack++
	case StatusClosed:
		a.Closed++
	}
}

// resolution mide la vida del incidente cerrado. Sin sello de cierre no hay
// medida: no se inventa una duración a partir del reloj actual.
func resolution(inc Incident) (float64, bool) {
	if inc.Status != StatusClosed || inc.ClosedAt == nil || inc.OpenedAt.IsZero() {
		return 0, false
	}
	secs := inc.ClosedAt.Sub(inc.OpenedAt).Seconds()
	if secs < 0 {
		secs = 0
	}
	return secs, true
}

func accumulateDevice(acc map[string]DeviceCount, inc Incident) {
	if inc.DeviceID == "" {
		return
	}
	cur := acc[inc.DeviceID]
	cur.DeviceID = inc.DeviceID
	if inc.DeviceName != "" {
		cur.DeviceName = inc.DeviceName
	}
	cur.Count++
	acc[inc.DeviceID] = cur
}

func topDevices(acc map[string]DeviceCount) []DeviceCount {
	out := make([]DeviceCount, 0, len(acc))
	for _, v := range acc {
		out = append(out, v)
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Count != out[j].Count {
			return out[i].Count > out[j].Count
		}
		return out[i].DeviceID < out[j].DeviceID
	})
	if len(out) > TopDevicesLimit {
		out = out[:TopDevicesLimit]
	}
	return out
}

// emptyDays devuelve los últimos AnalyticsDays días en UTC, del más antiguo al
// más reciente, con contador a cero, para que la gráfica no cambie de forma
// según haya o no incidentes.
func emptyDays(now time.Time) []DayCount {
	base := now.UTC().Truncate(24 * time.Hour)
	out := make([]DayCount, 0, AnalyticsDays)
	for i := AnalyticsDays - 1; i >= 0; i-- {
		out = append(out, DayCount{Day: base.AddDate(0, 0, -i).Format(DayLayout)})
	}
	return out
}

func emptyCounts(names ...string) map[string]int {
	out := make(map[string]int, len(names))
	for _, n := range names {
		out[n] = 0
	}
	return out
}

// severityKey manda la severidad ausente al cajón de lo desconocido en vez de
// repartirla entre las conocidas.
func severityKey(s string) string {
	if s == "" {
		return risk.SeverityUnknown
	}
	return s
}

// csvColumns es la cabecera en español y el extractor de cada columna.
var csvColumns = []struct {
	header string
	value  func(Incident) string
}{
	{"id", func(i Incident) string { return i.ID }},
	{"dispositivo_id", func(i Incident) string { return i.DeviceID }},
	{"dispositivo", func(i Incident) string { return i.DeviceName }},
	{"tipo", func(i Incident) string { return i.Kind }},
	{"severidad", func(i Incident) string { return i.Severity }},
	{"estado", func(i Incident) string { return string(i.Status) }},
	{"titulo", func(i Incident) string { return i.Title }},
	{"geocerca", func(i Incident) string { return i.FenceID }},
	{"asignado", func(i Incident) string { return i.Assignee }},
	{"riesgo", func(i Incident) string { return scoreText(i.RiskScore) }},
	{"veces", func(i Incident) string { return strconv.Itoa(i.Count) }},
	{"abierto_en", func(i Incident) string { return stampText(&i.OpenedAt) }},
	{"actualizado_en", func(i Incident) string { return stampText(&i.UpdatedAt) }},
	{"reconocido_en", func(i Incident) string { return stampText(i.AckedAt) }},
	{"cerrado_en", func(i Incident) string { return stampText(i.ClosedAt) }},
	{"evidencias", func(i Incident) string { return strings.Join(i.Evidence, " | ") }},
	{"eventos", func(i Incident) string { return strconv.Itoa(len(i.Timeline)) }},
	{"ultima_nota", func(i Incident) string { return lastNote(i) }},
}

// ToCSV exporta los incidentes con cabecera en español y comillas escapadas
// según RFC 4180 (Excel y LibreOffice lo abren sin tocar nada).
func ToCSV(is []Incident) []byte {
	var b strings.Builder
	for i, c := range csvColumns {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(c.header)
	}
	b.WriteByte('\n')
	for _, inc := range is {
		for i, c := range csvColumns {
			if i > 0 {
				b.WriteByte(',')
			}
			b.WriteString(escapeCSV(c.value(inc)))
		}
		b.WriteByte('\n')
	}
	return []byte(b.String())
}

func escapeCSV(s string) string {
	if !strings.ContainsAny(s, ",\"\n\r") {
		return s
	}
	return `"` + strings.ReplaceAll(s, `"`, `""`) + `"`
}

func lastNote(inc Incident) string {
	for i := len(inc.Timeline) - 1; i >= 0; i-- {
		if inc.Timeline[i].Note != "" {
			return inc.Timeline[i].Actor + ": " + inc.Timeline[i].Note
		}
	}
	return ""
}

func scoreText(v *float64) string {
	if v == nil {
		return ""
	}
	return numText(*v)
}

func stampText(t *time.Time) string {
	if t == nil || t.IsZero() {
		return ""
	}
	return t.UTC().Format(time.RFC3339)
}
