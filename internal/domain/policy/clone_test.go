package policy

import "testing"

func TestCopiaProfundaNoEsSoloMapaExterior(t *testing.T) {
	params := map[string]any{"list": []any{map[string]any{"value": "original"}}}
	out, ok := cloneActions([]Action{{Params: params}})
	if !ok {
		t.Fatal("copia falló")
	}
	out[0].Params["list"].([]any)[0].(map[string]any)["value"] = "changed"
	if params["list"].([]any)[0].(map[string]any)["value"] != "original" {
		t.Fatal("Params anidados compartidos")
	}
	if out, ok := cloneActions(nil); !ok || out != nil {
		t.Fatal("nil alterado")
	}
	if _, ok := cloneActions([]Action{{Params: map[string]any{"invalid": func() {}}}}); ok {
		t.Fatal("copia inválida aceptada")
	}
}
