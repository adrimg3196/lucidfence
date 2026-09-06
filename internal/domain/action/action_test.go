package action

import "testing"

func TestParseYDestructive(t *testing.T) {
	for _, s := range []string{"lock", "wipe", "message", "locate", "reboot", "clear_passcode", "set_compliance", "custom", "notify"} {
		if _, err := Parse(s); err != nil {
			t.Fatalf("Parse(%q): %v", s, err)
		}
	}
	if _, err := Parse("format_disk"); err == nil {
		t.Fatal("acción desconocida debe fallar")
	}
	for a, want := range map[Action]bool{Lock: true, Wipe: true, ClearPasscode: true, Reboot: true, Message: false, Locate: false, Notify: false, SetCompliance: false, Custom: false} {
		if a.Destructive() != want {
			t.Fatalf("%s.Destructive()=%v", a, !want)
		}
	}
}
