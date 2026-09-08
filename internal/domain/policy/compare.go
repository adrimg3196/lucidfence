// Package policy compara condiciones puras sobre evidencia ya evaluada.
// No ejecuta acciones, consulta el reloj ni hace I/O.
package policy

import (
	"encoding/json"
	"reflect"
	"strings"
)

// Op identifica un comparador explícito.
type Op string

const (
	OpEq       Op = "eq"
	OpNe       Op = "ne"
	OpGt       Op = "gt"
	OpGte      Op = "gte"
	OpLt       Op = "lt"
	OpLte      Op = "lte"
	OpIn       Op = "in"
	OpContains Op = "contains"
)

func compare(a any, op Op, b any) bool {
	switch op {
	case OpEq, OpNe:
		equal, known := equality(a, b)
		return known && (equal == (op == OpEq))
	case OpGt, OpGte, OpLt, OpLte:
		return ordered(a, op, b)
	case OpIn:
		items, ok := listOf(b)
		if !ok {
			return false
		}
		for _, item := range items {
			if equal, known := equality(a, item); known && equal {
				return true
			}
		}
	case OpContains:
		text, ok := a.(string)
		needle, valid := b.(string)
		return ok && valid && strings.Contains(text, needle)
	}
	return false
}

// scalarFamily elimina nombres Go de bool/texto sin convertir números en texto.
func scalarFamily(v any) any {
	if _, ok := v.(json.Number); ok {
		return v
	}
	rv := reflect.ValueOf(v)
	switch rv.Kind() {
	case reflect.String:
		return rv.String()
	case reflect.Bool:
		return rv.Bool()
	}
	return v
}

func equality(a, b any) (bool, bool) {
	a, b = scalarFamily(a), scalarFamily(b)
	switch v := a.(type) {
	case bool:
		w, ok := b.(bool)
		return v == w, ok
	case string:
		w, ok := b.(string)
		return v == w, ok
	}
	x, ok := numberOf(a)
	y, valid := numberOf(b)
	return x == y, ok && valid
}

func ordered(a any, op Op, b any) bool {
	x, ok := numberOf(a)
	y, valid := numberOf(b)
	if !ok || !valid {
		return false
	}
	switch op {
	case OpGt:
		return x > y
	case OpGte:
		return x >= y
	case OpLt:
		return x < y
	case OpLte:
		return x <= y
	}
	return false
}

func listOf(v any) ([]any, bool) {
	switch v := v.(type) {
	case []any:
		return v, v != nil
	case []string:
		if v == nil {
			return nil, false
		}
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = item
		}
		return out, true
	}
	return nil, false
}
