// Credenciales del asistente inicial, compartidas por demo.spec.ts y
// riesgo.spec.ts (M2-R69). Playwright (1.63) rechaza en tiempo de carga
// cualquier import estático entre dos ficheros que casan con el patrón de
// test ("test file X should not import test file Y"), así que las
// credenciales no pueden vivir exportadas desde demo.spec.ts: un
// `import ... from "./demo.spec"` en riesgo.spec.ts rompería la carga de
// `npm run e2e` entero, no solo ese test. Este fichero no casa con el
// testMatch por defecto de Playwright, así que no se colecciona como spec.
export const E2E_EMAIL = "e2e@lucidfence.local";
export const E2E_PASSWORD = "contraseña-e2e-2026";
