package policy

import (
	"encoding/json"
	"math"
	"math/big"
	"reflect"
	"strconv"
)

// maxNumber limita las comparaciones al intervalo interoperable de enteros
// JSON/binary64. Fuera del intervalo la configuración es inválida, no se
// comparan enteros distintos tras redondearlos al mismo float64.
const maxNumber = 9007199254740991

func numberOf(v any) (float64, bool) {
	if n, ok := v.(json.Number); ok {
		return jsonNumber(n)
	}
	if v == nil {
		return 0, false
	}
	rv := reflect.ValueOf(v)
	var n float64
	switch rv.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		i := rv.Int()
		if i < -maxNumber || i > maxNumber {
			return 0, false
		}
		n = float64(i)
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		i := rv.Uint()
		if i > maxNumber {
			return 0, false
		}
		n = float64(i)
	case reflect.Float32:
		// encoding/json escribe la representación decimal corta de binary32.
		// Usar la misma evita que 0.1 cambie de comparación al rehidratarse.
		n, _ = strconv.ParseFloat(strconv.FormatFloat(rv.Float(), 'g', -1, 32), 64)
	case reflect.Float64:
		n = rv.Float()
	default:
		return 0, false
	}
	return n, !math.IsNaN(n) && !math.IsInf(n, 0) && math.Abs(n) <= maxNumber
}

func jsonNumber(n json.Number) (float64, bool) {
	// Comprueba el decimal original antes de perder precisión al convertirlo.
	if !json.Valid([]byte(n)) {
		return 0, false
	}
	r, ok := new(big.Rat).SetString(string(n))
	if !ok || new(big.Rat).Abs(r).Cmp(big.NewRat(maxNumber, 1)) > 0 {
		return 0, false
	}
	f, err := n.Float64()
	return f, err == nil && !math.IsNaN(f) && !math.IsInf(f, 0)
}
