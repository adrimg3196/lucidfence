package battery

import "testing"

func TestChecksIncluyeRelojDwell(t *testing.T) {
	for _, c := range Checks() {
		if c.Name == "reloj de permanencia explícito sin señales inventadas" {
			return
		}
	}
	t.Fatal("falta check runtime D01c")
}
