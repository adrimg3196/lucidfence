package policy

import (
	"bytes"
	"encoding/json"
)

// UnmarshalJSON conserva los literales numéricos de Params, también anidados.
// Policy hereda esta decodificación en cada Action; Params no limita su rango.
func (a *Action) UnmarshalJSON(data []byte) error {
	type plain Action
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode((*plain)(a))
}

// UnmarshalJSON conserva Value antes de validar su rango, sin redondearlo.
// También se aplica a las condiciones anidadas en Policy.
func (c *Condition) UnmarshalJSON(data []byte) error {
	type plain Condition
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode((*plain)(c))
}
