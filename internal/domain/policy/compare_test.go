package policy

import (
	"encoding/json"
	"math"
	"testing"
)

func TestOperadoresPortadosDeCmp(t *testing.T) {
	tests := []struct {
		name string
		a    any
		op   Op
		b    any
		want bool
	}{
		{"eq numero JSON", 2, OpEq, float64(2), true},
		{"ne observado", "a", OpNe, "b", true},
		{"gt", 3, OpGt, 2.5, true}, {"gte borde", 2, OpGte, 2, true},
		{"lt", -1, OpLt, 0, true}, {"lte borde", 0, OpLte, 0, true},
		{"in", "es", OpIn, []any{"fr", "es"}, true},
		{"in strings", "es", OpIn, []string{"es"}, true},
		{"contains", "seguridad", OpContains, "guri", true},
		{"false explicito", false, OpEq, false, true},
		{"numero decoder", json.Number("2"), OpEq, 2, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := compare(tt.a, tt.op, tt.b); got != tt.want {
				t.Fatalf("compare(%v,%s,%v)=%v", tt.a, tt.op, tt.b, got)
			}
		})
	}
}

func TestComparacionImposibleNoEsDesigualdad(t *testing.T) {
	var pointer *float64
	invalid := []any{nil, pointer, math.NaN(), math.Inf(1), math.Inf(-1), []any(nil), map[string]any(nil), struct{}{}, json.Number("oops")}
	for _, a := range invalid {
		for _, op := range []Op{OpEq, OpNe, OpGt, OpGte, OpLt, OpLte, OpIn, OpContains} {
			if compare(a, op, 1) || compare(1, op, a) {
				t.Errorf("comparación imposible %T %s casa", a, op)
			}
		}
	}
	for _, pair := range [][2]any{{true, 1}, {"1", 1}, {false, 0}, {1, "1"}} {
		if compare(pair[0], OpNe, pair[1]) || compare(pair[0], OpEq, pair[1]) {
			t.Errorf("familias incompatibles %v", pair)
		}
	}
	if compare("abc", OpIn, "abc") || compare("1", OpGt, 0) || compare(1, "", 0) || compare(1, "wat", 0) {
		t.Fatal("coerción implícita")
	}
}

func TestNumerosSinPerdidaSilenciosa(t *testing.T) {
	// Rango interoperable: enteros exactos de JSON/binary64 hasta 2^53-1.
	safe := int64(9007199254740991)
	if !compare(safe, OpEq, json.Number("9007199254740991")) {
		t.Fatal("entero seguro no normalizado")
	}
	for _, a := range []any{int64(9007199254740992), uint64(9007199254740993), json.Number("9007199254740993"), 9007199254740992.0} {
		if compare(a, OpEq, a) || compare(a, OpNe, 0) {
			t.Fatalf("fuera de rango casa: %v", a)
		}
	}
	for _, a := range []any{int8(2), int16(2), int32(2), int64(2), uint(2), uint8(2), uint16(2), uint32(2), uint64(2), float32(2)} {
		if !compare(a, OpEq, 2) {
			t.Fatalf("familia numérica omitida %T", a)
		}
	}
}
