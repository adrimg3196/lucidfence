// La API es la fuente de verdad: /auth/me devuelve las capacidades del rol.
// La UI solo oculta lo que el rol no puede hacer; el servidor lo rechaza igualmente.
export function can(capabilities: readonly string[] | undefined, cap: string): boolean {
  return Array.isArray(capabilities) && capabilities.includes(cap);
}
