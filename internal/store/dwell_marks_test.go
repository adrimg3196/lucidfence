package store

import (
	"bytes"
	"os"
	"reflect"
	"strings"
	"testing"
)

// dwellSince es un valor como el que escribe el motor: el fence_state_since de
// la estancia, formateado por engine.stayOf en RFC 3339 con nanosegundos.
const dwellSince = "2026-09-06T09:00:00Z"

func TestMarcasDeEstanciaSobrevivenAlReinicio(t *testing.T) {
	root := t.TempDir()
	o := orgIn(t, root)
	if got := o.DwellMarks(); len(got) != 0 {
		t.Fatalf("sin fichero no hay marcas: %+v", got)
	}
	want := map[string]string{"dev-a|almacen": dwellSince}
	if err := o.SaveDwellMarks(want); err != nil {
		t.Fatal(err)
	}
	// Reabrir la raíz es lo más cerca de un reinicio del proceso que hay aquí.
	if got := orgIn(t, root).DwellMarks(); !reflect.DeepEqual(got, want) {
		t.Fatalf("la marca debe sobrevivir al reinicio: %+v", got)
	}
	// Guardar el mapa ya sin la clave es lo que hace el ciclo en el que el
	// dispositivo sale de la geocerca: la estancia siguiente vuelve a disparar.
	if err := o.SaveDwellMarks(map[string]string{}); err != nil {
		t.Fatal(err)
	}
	if got := orgIn(t, root).DwellMarks(); len(got) != 0 {
		t.Fatalf("salir borra la marca también en disco: %+v", got)
	}
}

func TestMarcasDeEstanciaNulasSeGuardanComoMapaVacio(t *testing.T) {
	o := orgIn(t, t.TempDir())
	if err := o.SaveDwellMarks(nil); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(o.Path(dwellMarksFile))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(raw), `"entries": {}`) {
		t.Fatalf("un mapa nulo se guarda como objeto vacío, no como null: %s", raw)
	}
	if got := o.DwellMarks(); got == nil || len(got) != 0 {
		t.Fatalf("y se relee como un mapa vacío usable: %+v", got)
	}
}

func TestFicheroDeEstanciasAusenteNoAvisa(t *testing.T) {
	var logs bytes.Buffer
	o := orgConLogger(t, &logs)
	if got := o.DwellMarks(); len(got) != 0 {
		t.Fatalf("sin fichero no hay marcas: %+v", got)
	}
	// El primer arranque es el caso normal, no una anomalía.
	if logs.Len() != 0 {
		t.Fatalf("el fichero ausente no debe avisar: %q", logs.String())
	}
}

func TestMarcasDeEstanciaCorruptasSeIgnoranYDejanRastro(t *testing.T) {
	var logs bytes.Buffer
	o := orgConLogger(t, &logs)
	if err := os.WriteFile(o.Path(dwellMarksFile), []byte("{no es json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if got := o.DwellMarks(); len(got) != 0 {
		t.Fatalf("un fichero corrupto equivale a sin marcas: %+v", got)
	}
	// Falla en abierto, pero no en silencio (ruling M2-R21): sin rastro, el
	// operador no tiene forma de saber por qué se ha repetido un on_enter por
	// permanencia después de un arranque.
	if aviso := logs.String(); !strings.Contains(aviso, "level=WARN") || !strings.Contains(aviso, dwellMarksFile) {
		t.Fatalf("un fichero ilegible debe dejar rastro: %q", aviso)
	}
	if err := o.SaveDwellMarks(map[string]string{"dev-a|almacen": dwellSince}); err != nil {
		t.Fatal(err)
	}
	trasReparar := logs.String()
	if got := o.DwellMarks(); len(got) != 1 {
		t.Fatalf("tras reparar el fichero vuelve a leerse: %+v", got)
	}
	// Reparado el fichero, el aviso deja de repetirse: la anomalía es ruidosa
	// mientras dura, no para siempre.
	if logs.String() != trasReparar {
		t.Fatalf("tras reparar no debe seguir avisando: %q", strings.TrimPrefix(logs.String(), trasReparar))
	}
}
