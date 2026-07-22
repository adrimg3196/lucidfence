# Multi-UEM Geofencing — Diseño aprobado

Fecha: 2026-07-22
Estado: aprobado por el usuario
Método: obra/superpowers d884ae04edebef577e82ff7c4e143debd0bbec99 (MIT)

## 1. Objetivo

Convertir LucidFence de un producto con varios adapters registrables pero una sola fuente/acción UEM activa por motor en un producto Multi-UEM real por tenant. Un mismo tenant podrá sincronizar simultáneamente varios UEM, consolidar su flota sin perder procedencia, evaluar geofencing con evidencia de ubicación confiable y dirigir cada acción al proveedor propietario correcto.

La entrega debe preservar el modo local-first, el servidor Python 3.11 stdlib-first, el contrato `MDMAdapter.execute()` existente y la compatibilidad con instalaciones de un solo proveedor.

## 2. Decisiones de arquitectura

### 2.1 Enfoque elegido

Se implementará un orquestador Multi-UEM dentro del monolito local existente. No se limitará el cambio a añadir nombres al registro y no se introducirán microservicios.

Motivos:

- el registro actual cubre acciones, pero `Engine` construye una sola `source` y un solo `adapter`;
- el monolito conserva soberanía, operación offline y despliegue simple;
- un orquestador aislado permite evolucionar conectores sin reescribir geocercas, riesgo o políticas;
- evita añadir red interna, colas o infraestructura que no aportan valor al siguiente slice.

### 2.2 Compatibilidad

`MDMAdapter` seguirá congelado. El contrato Multi-UEM será aditivo y vivirá en módulos nuevos. Un adapter antiguo seguirá siendo utilizable mediante un wrapper de compatibilidad. La configuración de un único proveedor seguirá produciendo el mismo comportamiento observable salvo por los nuevos campos de procedencia y calidad.

## 3. Modelo de dominio

### 3.1 Capacidades

Cada proveedor declara capacidades explícitas y estables:

- inventario;
- ubicación;
- geocercas nativas;
- acciones admitidas;
- modo live o simulado.

La ausencia de una capacidad es un dato normal, no un error. El UI y el motor no ofrecerán acciones que el proveedor no soporte.

### 3.2 Dispositivo normalizado

La identidad canónica separará:

- `canonical_id`: identidad interna estable;
- `provider`: nombre del UEM;
- `provider_device_id`: identificador remoto;
- identificadores de correlación normalizados: serial, IMEI y otros valores válidos;
- inventario normalizado;
- `location_evidence` opcional;
- procedencia por campo cuando varias fuentes contribuyan.

Los placeholders (`N/A`, `unknown`, vacío, `0`) nunca se usarán para fusionar dispositivos. Una coincidencia ambigua no se resolverá automáticamente: se conservarán registros separados y se expondrá el conflicto.

### 3.3 Evidencia de ubicación

La ubicación se modelará con:

- latitud y longitud;
- instante observado;
- precisión en metros cuando exista;
- proveedor y tipo de fuente;
- clasificación de calidad;
- motivo de rechazo cuando no sea apta.

La evidencia es apta para geofencing solo si:

- las coordenadas son válidas;
- el timestamp puede interpretarse y no está en el futuro fuera de tolerancia;
- no supera la edad máxima configurada;
- la precisión no supera el umbral configurado cuando está disponible.

Si una ubicación no es apta, el estado es `unknown`; no se infiere `outside` y no se dispara una acción destructiva.

## 4. Orquestador Multi-UEM

`MultiUEMOrchestrator` será tenant-local y recibirá instancias ya construidas; no leerá credenciales globales por su cuenta.

Responsabilidades:

1. sincronizar cada proveedor con aislamiento de errores;
2. normalizar resultados al modelo común;
3. consolidar identidades determinísticamente;
4. seleccionar la mejor evidencia de ubicación por frescura, precisión y prioridad declarada;
5. mantener el mapa `canonical_id -> provider/provider_device_id`;
6. enrutar acciones al proveedor propietario;
7. devolver salud y cobertura por proveedor sin exponer secretos.

Un proveedor caído no vaciará la flota de los demás ni impedirá el ciclo. El resultado distinguirá éxito, degradación parcial y fallo total.

No se ejecutarán proveedores en paralelo en el primer slice: el aislamiento secuencial es más simple y reproducible. La concurrencia queda fuera hasta que perfiles reales demuestren necesidad.

## 5. Integración con el motor de geofencing

El motor consumirá una colección de reportes normalizados. La lógica geométrica de círculos, polígonos y rutas seguirá en `core/fences.py`, `core/geo.py` y `core/routes.py`.

Antes de evaluar geometría se aplicará el gate de evidencia. Las transiciones válidas serán:

- `unknown -> inside|outside`: observación inicial, sin falsificar una transición histórica;
- `inside <-> outside`: transición real con evidencia apta;
- `inside|outside -> unknown`: degradación de datos; puede notificar, pero no ejecutar acciones destructivas;
- `unknown -> unknown`: sin acción.

El dedupe y cooldown seguirán siendo por dispositivo canónico y acción. La acción se ejecutará con el `provider_device_id`, nunca con el identificador canónico.

Las acciones `wipe`, `lock`, `clear_passcode` y `reboot` se mantendrán human-gated. El orquestador puede construir un dry-run/handoff, pero no convertirá una aprobación en ejecución implícita.

## 6. Configuración y aislamiento tenant

La configuración aceptará `uem.providers[]`, con nombre, enabled, mode y opciones no secretas. Los secretos seguirán en la integración tenant-local existente con permisos restrictivos y nunca aparecerán en:

- Git;
- `.env.example` con valores reales;
- respuestas API;
- logs;
- Pages o Service Worker;
- documentos de diseño/plan.

No habrá fallback silencioso desde credenciales del tenant a credenciales de proceso para un proveedor configurado explícitamente. La compatibilidad legacy de Applivery se adaptará de forma explícita y comprobable.

### 6.1 Dos modos de producto, un único motor Multi-UEM

Multi-UEM es obligatorio tanto en SaaS como en local; no se mantendrá una edición
local degradada a un solo UEM.

- `hosted`: el usuario entra con login, pertenece a una organización y toda
  lectura/configuración se autoriza contra ese tenant. No existe acceso demo
  anónimo en un bind público.
- `local`: no exige cuenta ni identidad cloud. En loopback se permite el
  bootstrap de un propietario local y todas las sesiones, datos y credenciales
  permanecen en el directorio local. Si se intenta exponer fuera de loopback,
  el arranque falla cerrado salvo que se haya configurado autenticación local.

Ambos modos usan `MultiUEMOrchestrator`, el mismo contrato de capacidades y el
mismo gate de evidencia. Cambiar de despliegue no cambia la semántica de
identidad, geofencing ni acciones.

### 6.2 SSO para hosted, opcional en local

El modo hosted ofrecerá contraseña local y SSO OIDC. Google será el preset
primario; Microsoft Entra ID, Okta y otros se habilitarán mediante configuración
OIDC estándar, no mediante flujos propietarios.

- Authorization Code con PKCE S256, `state` y `nonce` de un solo uso y TTL corto.
- El ID Token firmado es la prueba primaria de autenticación. Se validan JWS/JWKS con algoritmos asimétricos permitidos, `iss`, `aud`, `azp`, `exp`, `iat` y `nonce`; `alg=none`, confusión HS/RS y claves inesperadas fallan cerrado.
- Redirect URI exacta y HTTPS en hosted; loopback se admite solo en desarrollo/local.
- Discovery, authorization, token, JWKS y userinfo parten únicamente de configuración administrativa. Cada URL y cada A/AAAA deben pasar una política de egress pública; se revalida al conectar, no se siguen redirects y se limitan tamaños.
- Cada state queda ligado atómicamente al navegador pre-auth, provider, issuer, client ID, redirect URI, nonce, verifier y purpose. El callback deriva el provider del flow consumido y valida `iss`, evitando mix-up.
- La identidad durable es `(issuer, sub)`, nunca el email por sí solo. Si se consulta UserInfo, su `sub` debe coincidir con el ID Token validado.
- `email_verified=true`, dominio permitido e invitación/política explícita son requisitos de aprovisionamiento; no se crea un owner arbitrario por poseer un correo Google.
- Client secrets, access tokens e ID tokens permanecen server-side, con permisos `0600`, y nunca entran en API, logs, URLs de frontend o Service Worker.
- Tras SSO se destruye la pre-sesión, se rota la sesión y se responde 303 a una URL limpia con `Cache-Control: no-store` y `Referrer-Policy: no-referrer`.
- El modo local conserva login/owner local y no depende de disponibilidad de Google. SSO local es opt-in, usa un public client separado y solo admite loopback IP literal.

## 7. API y UX

El API añadirá una vista tenant-authenticated de salud Multi-UEM que exponga:

- proveedores configurados y habilitados;
- estado de la última sincronización;
- número de dispositivos aportados;
- capacidades;
- errores sanitizados;
- cobertura de ubicación apta/no apta.

La consola mostrará procedencia y calidad en la ficha de dispositivo y evitará presentar una flota parcialmente sincronizada como completa. Los botones de acción se derivarán de capacidades y mantendrán dry-run/aprobación.

El primer slice no incluye un editor universal de credenciales ni onboarding OAuth para todos los proveedores. Se reutiliza la configuración tenant-local existente y se prioriza que la ejecución sea correcta y observable.

## 8. Seguridad de red

Toda URL configurable de proveedor debe ser HTTPS, sin credenciales embebidas, sin host local/privado/reservado y sin redirecciones autenticadas. Los enlaces de paginación deben permanecer en el origen validado. Si un conector existente no puede demostrar estas propiedades, se mantendrá en simulación o se corregirá antes de incluirlo como live.

Los errores remotos se sanitizarán: se podrá mostrar etapa, proveedor y código HTTP, nunca headers, tokens, client secrets ni cuerpos arbitrarios completos.

## 9. Pruebas y evidencia

La implementación seguirá RED-GREEN-REFACTOR por comportamiento:

1. contrato y modelos;
2. consolidación y conflicto de identidad;
3. selección/rechazo de evidencia;
4. aislamiento de proveedor caído;
5. enrutado de acciones;
6. integración del motor;
7. aislamiento tenant/API;
8. login hosted y bootstrap local loopback;
9. paridad Multi-UEM entre hosted y local;
10. UX y E2E vivo.

Cada test nuevo debe observarse fallar por la ausencia del comportamiento antes de escribir producción. Además se ejecutarán:

- tests focalizados tras cada tarea;
- `python3 tests/run_tests.py` completo;
- chequeos de sintaxis frontend;
- `git diff --check`;
- Gitleaks sobre archivos rastreables, con fixtures explícitamente falsos;
- server real en un puerto limpio;
- login y recorrido Multi-UEM/geofencing en navegador;
- consola y peticiones sin errores;
- limpieza de servidor y puerto al finalizar.

## 10. Criterios de aceptación

1. Un tenant puede activar al menos dos proveedores simultáneos en un mismo ciclo.
2. La caída de uno conserva los dispositivos y salud de los demás.
3. El mismo dispositivo correlacionado por identificador válido aparece una vez con procedencia múltiple.
4. Placeholders o identidad ambigua no provocan fusiones.
5. Se elige la mejor ubicación apta de forma determinista.
6. Ubicación obsoleta, imprecisa o futura produce `unknown`, no `outside`.
7. Las acciones se enrutan al proveedor e ID remoto correctos.
8. Capacidades no soportadas fallan de forma estructurada y nunca hacen raise.
9. Credenciales y errores permanecen aislados por tenant y sanitizados.
10. El modo legacy de un proveedor sigue funcionando.
11. El modo hosted exige login y aísla organizaciones.
12. El modo local funciona sin cuenta cloud en loopback y falla cerrado si se expone sin autenticación local.
13. Hosted y local ejecutan el mismo orquestador Multi-UEM, no ediciones funcionalmente distintas.
14. Google SSO completa Authorization Code + PKCE y crea sesión solo para una identidad OIDC autorizada.
15. Un proveedor OIDC genérico permite configurar Entra ID/Okta sin cambiar código, manteniendo `issuer + sub` como vínculo.
16. Suite completa, E2E vivo, seguridad y revisión independiente terminan en PASS.

## 11. Fuera de alcance

- microservicios o message bus;
- sincronización concurrente;
- ejecución destructiva autónoma;
- validación live con credenciales reales que el usuario no haya configurado;
- certificar precisión que el proveedor no informa;
- billing, adquisición o campañas;
- reescritura general de `saas_server.py` o `core/engine.py` no necesaria para este objetivo.

## 12. Riesgos y mitigaciones

- Compatibilidad: contrato aditivo y tests legacy.
- Fusión incorrecta: identificadores fuertes normalizados, placeholders rechazados y conflictos visibles.
- Falsos exits: gate de calidad antes de geometría.
- Proveedor lento: timeout por conector, resultado parcial y métricas; concurrencia solo con evidencia de necesidad.
- Filtración: configuración tenant-local, sanitización y pruebas adversariales.
- Árbol previo sin commit: checkpoint local tras retirar telemetría generada y pasar tests/secret scan; trabajo nuevo en worktree aislado.
