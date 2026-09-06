// Package action define las acciones UEM que LucidFence puede ordenar y el
// resultado normalizado que devuelve todo conector.
package action

import (
	"fmt"
	"time"
)

// Action es una orden al UEM.
type Action string

const (
	Lock          Action = "lock"
	Wipe          Action = "wipe"
	Message       Action = "message"
	Locate        Action = "locate"
	Reboot        Action = "reboot"
	ClearPasscode Action = "clear_passcode"
	SetCompliance Action = "set_compliance"
	Custom        Action = "custom"
	Notify        Action = "notify"
)

// All enumera las acciones válidas en orden estable.
var All = []Action{Lock, Wipe, Message, Locate, Reboot, ClearPasscode, SetCompliance, Custom, Notify}

// Parse valida una cadena.
func Parse(s string) (Action, error) {
	for _, a := range All {
		if string(a) == s {
			return a, nil
		}
	}
	return "", fmt.Errorf("acción desconocida %q", s)
}

// Destructive marca las acciones que exigen handoff humano en SOAR y
// guardarraíles en enforce (spec §6.5).
func (a Action) Destructive() bool {
	switch a {
	case Lock, Wipe, ClearPasscode, Reboot:
		return true
	}
	return false
}

// Result es el resultado normalizado de ejecutar una acción.
type Result struct {
	Adapter    string         `json:"adapter"`
	OK         bool           `json:"ok"`
	DeviceID   string         `json:"device_id"`
	DeviceName string         `json:"device_name"`
	Action     Action         `json:"action"`
	Params     map[string]any `json:"params,omitempty"`
	DryRun     bool           `json:"dry_run"`
	Simulated  bool           `json:"simulated"`
	Error      string         `json:"error,omitempty"`
	CommandID  string         `json:"command_id,omitempty"`
	Note       string         `json:"note,omitempty"`
	At         time.Time      `json:"at"`
	FenceID    string         `json:"fence_id,omitempty"`
	Trigger    string         `json:"trigger,omitempty"`
}
