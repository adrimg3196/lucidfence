# Aprendizajes Críticos de Descubrimiento de Producto (NOVA)

**Agente:** Jules (Visionary Product Lead)
**Fecha:** 2026-09-12
**Módulo:** Product Discovery & Roadmap Vision

---

## Principios de Diseño para las Nuevas Funciones Ultra Necesarias

1. **Local-First Sin Excepciones:**
   - La inferencia de predicción de rutas (NOVA-001) y la simulación Digital Twin (NOVA-004) deben ejecutarse localmente en la máquina del operador usando modelos ONNX/WASM o motores numéricos en Go, manteniendo el dato de ubicación estricta y soberanamente privado.

2. **Garantía Cero-Confianza (Zero-Trust Quorum):**
   - Las acciones de alto impacto (`wipe`, `lock`) en el marco de la doble llave criptográfica (NOVA-002) requieren firma WebAuthn/FIDO2 basada en la especificación W3C, evitando depender de servicios de identidad centralizados en la nube.

3. **Invarianza y Abstracción Multi-UEM:**
   - La traducción automática de políticas (NOVA-003) debe basarse en un AST (Abstract Syntax Tree) común que compile deterministamente hacia los dialectos específicos de Apple DDM, Windows DSC, Android AMAPI y scripts UEM.

4. **Auditoría Soberana con Privacidad Garantizada:**
   - La emisión del pasaporte de auditoría (NOVA-005) debe priorizar esquemas Zero-Knowledge Proof (ZKP) o pruebas de rango esférico para certificar que un dispositivo estuvo en una zona permitida sin persistir ni filtrar coordenadas exactas.

---

## Directiva para Hermes

Hermes consumirá las especificaciones en `docs/product/visionary-features-roadmap.md` y la matriz de ruta en `docs/roadmap/PRODUCT_ROADMAP.md` para implementar paulatinamente cada capacidad sin alterar las invariantes de arquitectura ni romper los tests de límites físicos (`internal/arch`).
