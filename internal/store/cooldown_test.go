package store

import (
	"os"
	"runtime"
	"sync"
	"testing"
	"time"

	"github.com/adrimg3196/lucidfence/internal/domain/action"
)

// El motor y el notificador de M2 consumen el store por estas dos interfaces
// estructurales (engine.CooldownStore y notify.Sink). store no puede importar
// ni engine ni notify, así que la conformidad se comprueba por firma.
type cooldownStoreLike interface {
	LastActionAt(deviceID string, a action.Action) (time.Time, bool)
	RecordActionAt(deviceID string, a action.Action, at time.Time) error
}

type sinkLike interface {
	AppendDelivery(v any) error
}

var (
	_ cooldownStoreLike = (*OrgStore)(nil)
	_ sinkLike          = (*OrgStore)(nil)
)

// cooldownT0 es el instante de referencia de los casos dorados.
var cooldownT0 = time.Date(2026, 9, 6, 10, 0, 0, 0, time.UTC)

// orgIn abre la organización "default" bajo una raíz de datos concreta;
// llamarlo dos veces con la misma raíz simula un reinicio del proceso.
func orgIn(t *testing.T, root string) *OrgStore {
	t.Helper()
	s, err := Open(root)
	if err != nil {
		t.Fatal(err)
	}
	o, err := s.Org("default")
	if err != nil {
		t.Fatal(err)
	}
	return o
}

func TestRecordActionAtYLastActionAt(t *testing.T) {
	o := orgIn(t, t.TempDir())
	if err := o.RecordActionAt("dev-destruct", action.Wipe, cooldownT0); err != nil {
		t.Fatal(err)
	}
	at, ok := o.LastActionAt("dev-destruct", action.Wipe)
	if !ok || !at.Equal(cooldownT0) {
		t.Fatalf("marca: %v %v", at, ok)
	}
	// La marca se normaliza a UTC aunque llegue con zona.
	madrid := time.FixedZone("CEST", 2*3600)
	if err := o.RecordActionAt("dev-zona", action.Lock, cooldownT0.In(madrid)); err != nil {
		t.Fatal(err)
	}
	if at, ok := o.LastActionAt("dev-zona", action.Lock); !ok || !at.Equal(cooldownT0) || at.Location() != time.UTC {
		t.Fatalf("zona: %v %v", at, ok)
	}
	// Una segunda ejecución sustituye la marca, no acumula.
	later := cooldownT0.Add(2 * time.Hour)
	if err := o.RecordActionAt("dev-destruct", action.Wipe, later); err != nil {
		t.Fatal(err)
	}
	if at, ok := o.LastActionAt("dev-destruct", action.Wipe); !ok || !at.Equal(later) {
		t.Fatalf("segunda marca: %v %v", at, ok)
	}
}

func TestCooldownPersisteTrasReinicio(t *testing.T) {
	root := t.TempDir()
	primera := orgIn(t, root)
	if err := primera.RecordActionAt("dev-destruct", action.Wipe, cooldownT0); err != nil {
		t.Fatal(err)
	}
	// "cooldown not persisted across restart" de tests/test_cooldown.py: una
	// instancia nueva sobre el mismo directorio sigue viendo la marca.
	segunda := orgIn(t, root)
	if segunda == primera {
		t.Fatal("el caso dorado exige una instancia distinta de OrgStore")
	}
	at, ok := segunda.LastActionAt("dev-destruct", action.Wipe)
	if !ok || !at.Equal(cooldownT0) {
		t.Fatalf("tras reinicio: %v %v", at, ok)
	}
}

func TestAccionSinRegistrarNoTieneMarca(t *testing.T) {
	o := orgIn(t, t.TempDir())
	at, ok := o.LastActionAt("dev-destruct", action.Notify)
	if ok {
		t.Fatal("una acción nunca ejecutada no tiene marca")
	}
	if !at.IsZero() {
		t.Fatalf("sin marca el instante es el cero de time.Time, no una fecha: %v", at)
	}
	if err := o.RecordActionAt("dev-destruct", action.Wipe, cooldownT0); err != nil {
		t.Fatal(err)
	}
	// "test_non_destructive_action_never_cooled" de 1.x: registrar wipe no
	// contamina notify ni la marca del mismo wipe en otro dispositivo.
	if _, ok := o.LastActionAt("dev-destruct", action.Notify); ok {
		t.Fatal("notify no debe heredar la marca de wipe")
	}
	if _, ok := o.LastActionAt("dev-otro", action.Wipe); ok {
		t.Fatal("la marca es por dispositivo y acción")
	}
}

func TestPruneCooldownsBorraLoViejoYRespetaLoReciente(t *testing.T) {
	o := orgIn(t, t.TempDir())
	corte := cooldownT0.Add(time.Hour)
	if err := o.RecordActionAt("dev-1", action.Wipe, cooldownT0); err != nil {
		t.Fatal(err)
	}
	reciente := cooldownT0.Add(90 * time.Minute)
	if err := o.RecordActionAt("dev-2", action.Lock, reciente); err != nil {
		t.Fatal(err)
	}
	// El corte se conserva: una marca exactamente en before no se borra.
	if err := o.RecordActionAt("dev-3", action.Reboot, corte); err != nil {
		t.Fatal(err)
	}
	if err := o.PruneCooldowns(corte); err != nil {
		t.Fatal(err)
	}
	if _, ok := o.LastActionAt("dev-1", action.Wipe); ok {
		t.Fatal("lo anterior al corte se borra")
	}
	if at, ok := o.LastActionAt("dev-2", action.Lock); !ok || !at.Equal(reciente) {
		t.Fatalf("lo posterior al corte se conserva: %v %v", at, ok)
	}
	if _, ok := o.LastActionAt("dev-3", action.Reboot); !ok {
		t.Fatal("la marca exactamente en el corte se conserva")
	}
}

func TestPruneCooldownsSinFicheroNoLoCrea(t *testing.T) {
	o := orgIn(t, t.TempDir())
	if err := o.PruneCooldowns(cooldownT0); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(o.Path("cooldowns.json")); !os.IsNotExist(err) {
		t.Fatalf("prune no debe crear el fichero: %v", err)
	}
}

func TestFicheroDeCooldownsFormatoYPermisos(t *testing.T) {
	o := orgIn(t, t.TempDir())
	if err := o.RecordActionAt("dev-1", action.Wipe, cooldownT0); err != nil {
		t.Fatal(err)
	}
	var raw struct {
		SchemaVersion int               `json:"schema_version"`
		Entries       map[string]string `json:"entries"`
	}
	if err := ReadJSON(o.Path("cooldowns.json"), &raw); err != nil {
		t.Fatal(err)
	}
	if raw.SchemaVersion != 1 {
		t.Fatalf("schema_version: %d", raw.SchemaVersion)
	}
	if raw.Entries["dev-1|wipe"] != "2026-09-06T10:00:00Z" {
		t.Fatalf("clave \"<device>|<action>\" y valor RFC 3339: %+v", raw.Entries)
	}
	if runtime.GOOS != "windows" {
		info, err := os.Stat(o.Path("cooldowns.json"))
		if err != nil {
			t.Fatal(err)
		}
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("permisos %o", info.Mode().Perm())
		}
	}
}

func TestCooldownsCorruptoSeIgnoraYSeRepara(t *testing.T) {
	o := orgIn(t, t.TempDir())
	if err := os.WriteFile(o.Path("cooldowns.json"), []byte("{no es json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, ok := o.LastActionAt("dev-1", action.Wipe); ok {
		t.Fatal("un fichero corrupto equivale a sin marcas")
	}
	if err := o.RecordActionAt("dev-1", action.Wipe, cooldownT0); err != nil {
		t.Fatal(err)
	}
	if at, ok := o.LastActionAt("dev-1", action.Wipe); !ok || !at.Equal(cooldownT0) {
		t.Fatalf("tras reparar: %v %v", at, ok)
	}
}

func TestMarcaIlegibleSeIgnoraYSePoda(t *testing.T) {
	o := orgIn(t, t.TempDir())
	if err := WriteJSON(o.Path("cooldowns.json"), map[string]any{
		"schema_version": 1,
		"entries":        map[string]string{"dev-1|wipe": "ayer"},
	}); err != nil {
		t.Fatal(err)
	}
	if _, ok := o.LastActionAt("dev-1", action.Wipe); ok {
		t.Fatal("una marca ilegible no cuenta como ejecución")
	}
	if err := o.PruneCooldowns(cooldownT0); err != nil {
		t.Fatal(err)
	}
	var raw struct {
		Entries map[string]string `json:"entries"`
	}
	if err := ReadJSON(o.Path("cooldowns.json"), &raw); err != nil {
		t.Fatal(err)
	}
	if len(raw.Entries) != 0 {
		t.Fatalf("la marca ilegible debe podarse: %+v", raw.Entries)
	}
}

func TestCooldownsConcurrentesNoPierdenMarcas(t *testing.T) {
	o := orgIn(t, t.TempDir())
	const n = 20
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func(i int) {
			defer wg.Done()
			id := "dev-" + string(rune('a'+i))
			if err := o.RecordActionAt(id, action.Wipe, cooldownT0); err != nil {
				t.Error(err)
			}
		}(i)
	}
	wg.Wait()
	for i := 0; i < n; i++ {
		id := "dev-" + string(rune('a'+i))
		if _, ok := o.LastActionAt(id, action.Wipe); !ok {
			t.Fatalf("se perdió la marca de %s: el fichero se reescribe entero bajo lock", id)
		}
	}
}
