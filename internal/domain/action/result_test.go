package action

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestResultProcedenciaRoundTrip(t *testing.T) {
	assertResultJSON(t, `{
		"adapter":"simulation","ok":false,"device_id":"dev-1","device_name":"Tablet",
		"action":"wipe","params":{"reason":"prueba","nested":{"keep":false},"n":0},
		"dry_run":true,"simulated":true,"error":"bloqueado","command_id":"cmd-1",
		"note":"sin ejecución","at":"2026-09-07T12:00:00Z","fence_id":"f-1","trigger":"policy",
		"route_id":"r-1","policy_id":"p-1","playbook_id":"pb-1","severity":"high",
		"blocked":true,"error_type":"wipe_not_allowed"
	}`)
}

func assertResultJSON(t *testing.T, raw string) {
	t.Helper()
	var result Result
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(result)
	if err != nil {
		t.Fatal(err)
	}
	var want, got map[string]any
	if err := json.Unmarshal([]byte(raw), &want); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(encoded, &got); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("resultado perdió o inventó datos: got=%v want=%v", got, want)
	}
}

func TestResultM1NoInventaProcedencia(t *testing.T) {
	assertResultJSON(t, `{
		"adapter":"simulation","ok":true,"device_id":"dev-1","device_name":"Tablet",
		"action":"message","dry_run":true,"simulated":true,"at":"2026-09-07T12:00:00Z",
		"fence_id":"f-1","trigger":"on_enter"
	}`)
}

func TestResultCeroConservaContratoM1(t *testing.T) {
	assertResultJSON(t, `{
		"adapter":"","ok":false,"device_id":"","device_name":"","action":"",
		"dry_run":false,"simulated":false,"at":"0001-01-01T00:00:00Z"
	}`)
}
