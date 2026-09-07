import { describe, expect, it } from 'vitest'
import type { components } from './schema'

type Integrity = components['schemas']['Integrity']
type DeviceIntegrity = components['schemas']['Device']['location_integrity']

describe('contrato de integridad D01b', () => {
  it('distingue sin evaluar, evaluado limpio y métricas conocidas', () => {
    const states: DeviceIntegrity[] = [
      undefined, // respuestas M1
      { suspicious: false, checks: null }, // dispositivo aún sin evaluar
      { suspicious: false, checks: [] },
      { suspicious: true, checks: ['impossible_speed'], speed_kmh: 40000, distance_km: 10050.5 },
    ]
    expect(JSON.parse(JSON.stringify(states))).toEqual([
      null,
      { suspicious: false, checks: null },
      { suspicious: false, checks: [] },
      { suspicious: true, checks: ['impossible_speed'], speed_kmh: 40000, distance_km: 10050.5 },
    ])
    // @ts-expect-error suspicious y checks siempre viajan si hay objeto
    const incomplete: Integrity = {}
    expect(incomplete).toEqual({})
  })
})
