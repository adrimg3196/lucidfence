package policy

import (
	"bytes"
	"encoding/json"
	"errors"
)

// jsonCopy conserva las familias JSON y los decimales como json.Number,
// no los tipos concretos Go. Nunca comparte mapas/listas con la entrada.
func jsonCopy(v any) (any, error) {
	data, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var out any
	if err := decoder.Decode(&out); err != nil {
		return nil, err
	}
	return out, nil
}

func validateValue(value any, op Op) error {
	v, err := jsonCopy(value)
	if err != nil {
		return errors.New("'value' debe ser JSON finito")
	}
	if v == nil {
		return errors.New("sin 'value' (null no es evidencia)")
	}
	if !validNumbers(v) {
		return errors.New("'value' numérico fuera del intervalo JSON seguro [-9007199254740991,9007199254740991]")
	}
	switch op {
	case OpIn:
		if _, ok := listOf(value); !ok {
			return errors.New("'value' de in debe ser una lista")
		}
	case OpContains:
		if _, ok := scalarFamily(value).(string); !ok {
			return errors.New("'value' de contains debe ser texto")
		}
	case OpGt, OpGte, OpLt, OpLte:
		if _, ok := numberOf(value); !ok {
			return errors.New("'value' de umbral debe ser número finito")
		}
	}
	return nil
}

func validNumbers(v any) bool {
	switch v := v.(type) {
	case json.Number:
		_, ok := numberOf(v)
		return ok
	case []any:
		for _, item := range v {
			if !validNumbers(item) {
				return false
			}
		}
	case map[string]any:
		for _, item := range v {
			if !validNumbers(item) {
				return false
			}
		}
	}
	return true
}
