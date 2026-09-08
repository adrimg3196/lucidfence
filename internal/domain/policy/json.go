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

// UnmarshalJSON conserva los literales de evidencia antes de comprobar su rango.
// UseNumber en el consumidor no puede recuperar Signals ya redondeadas.
func (s *Subject) UnmarshalJSON(data []byte) error {
	type plain Subject
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode((*plain)(s))
}

// UnmarshalJSON conserva Value antes de validar su rango, sin redondearlo.
// También se aplica a las condiciones anidadas en Policy.
func (c *Condition) UnmarshalJSON(data []byte) error {
	type plain Condition
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	return decoder.Decode((*plain)(c))
}
