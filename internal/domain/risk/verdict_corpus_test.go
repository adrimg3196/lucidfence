package risk

import (
	"bufio"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"reflect"
	"strconv"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/device"
)

type roundingRow struct {
	ID               string  `json:"id"`
	Bits             string  `json:"bits"`
	Kind             string  `json:"kind"`
	Base             float64 `json:"base"`
	Credit           float64 `json:"credit"`
	RawBits          string  `json:"raw_bits"`
	PythonBits       string  `json:"python_bits"`
	PipelineBits     string  `json:"pipeline_bits"`
	PipelineSeverity string  `json:"pipeline_severity"`
}

func corpusRows(t *testing.T, name string) []roundingRow {
	t.Helper()
	f, err := os.Open("testdata/" + name + ".jsonl.gz")
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := f.Close(); err != nil {
			t.Error(err)
		}
	}()
	gz, err := gzip.NewReader(f)
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := gz.Close(); err != nil {
			t.Error(err)
		}
	}()
	rows := []roundingRow{}
	scan := bufio.NewScanner(gz)
	for scan.Scan() {
		var row roundingRow
		if err := json.Unmarshal(scan.Bytes(), &row); err != nil {
			t.Fatal(err)
		}
		rows = append(rows, row)
	}
	if err := scan.Err(); err != nil {
		t.Fatal(err)
	}
	if len(rows) != 43347 {
		t.Fatalf("%s rows=%d", name, len(rows))
	}
	return rows
}

func bitsValue(t *testing.T, s string) float64 {
	t.Helper()
	bits, err := strconv.ParseUint(s, 16, 64)
	if err != nil {
		t.Fatal(err)
	}
	return math.Float64frombits(bits)
}

func TestPythonCorpusBinary64(t *testing.T) {
	inputs, wants := corpusRows(t, "inputs"), corpusRows(t, "python-results")
	domain, away, scaledEven, zones := 0, 0, 0, 0
	for i, row := range wants {
		in := inputs[i]
		checkCorpusIdentity(t, in, row)
		raw := bitsValue(t, row.RawBits)
		if row.Kind == "zone" {
			testCorpusEvaluate(t, row)
			zones++
		}
		want := checkCorpusRounding(t, row, raw)
		if !finite(raw) || raw < 0 || raw > 100 {
			continue
		}
		domain++
		if math.Round(raw*10)/10 != want {
			away++
		}
		if math.RoundToEven(raw*10)/10 != want {
			scaledEven++
		}
	}
	if domain != 43323 || away != 1222 || scaledEven != 922 || zones != 78 {
		t.Fatalf("domain=%d away=%d scaledEven=%d zones=%d", domain, away, scaledEven, zones)
	}
	t.Logf("43347 input/output rows; domain=%d; product accumulators=%d; rejected Round=%d RoundToEven=%d", domain, zones, away, scaledEven)
}

func checkCorpusIdentity(t *testing.T, in, row roundingRow) {
	t.Helper()
	if row.Kind == "raw" && row.Bits != row.RawBits {
		t.Fatalf("raw input drift: %s", row.ID)
	}
	if in.ID != row.ID || in.Bits != row.Bits || in.Kind != row.Kind || in.Base != row.Base || in.Credit != row.Credit {
		t.Fatalf("source mismatch row %s", row.ID)
	}
}

func checkCorpusRounding(t *testing.T, row roundingRow, raw float64) float64 {
	t.Helper()
	got, want := roundTenth(raw), bitsValue(t, row.PythonBits)
	if !math.IsNaN(want) && math.Float64bits(got) != math.Float64bits(want) {
		t.Fatalf("%s rounded %016x want %s", row.ID, math.Float64bits(got), row.PythonBits)
	}
	if math.IsNaN(want) && !math.IsNaN(got) {
		t.Fatalf("%s NaN lost", row.ID)
	}
	return want
}

func corpusDevice(base float64) (device.Device, Signals, []string) {
	d := device.Device{}
	sig := Signals{}
	reasons := []string{}
	if base == 20 {
		d.FenceState = device.Unknown
		reasons = append(reasons, "ubicación desconocida (señal perdida)")
	}
	if base >= 35 {
		d.FenceState = device.Outside
		reasons = append(reasons, "fuera de geocerca permitida")
	}
	if base >= 60 {
		sig["device_health"] = Signal{"compliant": false}
		reasons = append(reasons, "dispositivo no conforme")
	}
	if base == 80 {
		sig["shift_match"] = Signal{"shift_known": true, "shift_match": false}
		reasons = append(reasons, "dispositivo fuera de su turno asignado")
	}
	return d, sig, reasons
}

func testCorpusEvaluate(t *testing.T, row roundingRow) {
	t.Helper()
	d, sig, reasons := corpusDevice(row.Base)
	zone := bitsValue(t, row.Bits)
	sig["zone_risk"] = Signal{"zone_risk": zone}
	if finite(zone) && zone > 0 {
		reasons = append(reasons, "zona de riesgo elevado ("+strconv.FormatFloat(zone, 'f', -1, 64)+")")
	}
	if row.Credit == 5 {
		sig["route_state"] = Signal{"route_state": "on_route"}
	}
	raw, rawReasons := accumulate(d, sig)
	if fmt.Sprintf("%016x", math.Float64bits(raw)) != row.RawBits || !reflect.DeepEqual(rawReasons, reasons) {
		t.Fatalf("%s raw=%016x want=%s reasons=%v want=%v", row.ID, math.Float64bits(raw), row.RawBits, rawReasons, reasons)
	}
	got := Evaluate(d, sig, time.Time{})
	if fmt.Sprintf("%016x", math.Float64bits(*got.Score)) != row.PipelineBits || got.Severity != row.PipelineSeverity || !reflect.DeepEqual(got.Reasons, reasons) {
		t.Fatalf("%s got=%+v score=%016x", row.ID, got, math.Float64bits(*got.Score))
	}
}
