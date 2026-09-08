import { expect, it } from 'vitest'
import type { components } from './schema'

type Device = components['schemas']['Device']

it('D01c conserva reloj y señales pasivas sin exigirlos a M1', () => {
  const origins: Device['fence_state_since'][] = [undefined, '2026-09-08T08:00:00Z']
  const seconds: Device['dwell_seconds'][] = [undefined, 0, 90]
  const signals: Device['signals'][] = [undefined, { absent: null, posture: { rooted: false, score: 0, unknown: null, checks: ['dato'] } }]
  expect(JSON.parse(JSON.stringify({ origins, seconds, signals }))).toEqual({
    origins: [null, '2026-09-08T08:00:00Z'],
    seconds: [null, 0, 90],
    signals: [null, { absent: null, posture: { rooted: false, score: 0, unknown: null, checks: ['dato'] } }],
  })
})
