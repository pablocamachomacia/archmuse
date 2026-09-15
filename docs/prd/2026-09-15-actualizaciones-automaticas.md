# PRD — Actualizaciones automáticas por canal, firmadas

**Estado:** Aprobado para implementar · **Fecha:** 2026-09-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, en el encargo del 2026-09-15 («Escribe el PRD y después impleméntalo»), con sus requisitos. Las decisiones que no venían en el encargo están marcadas **[decisión]**.

---

## 1. Problema que resuelve

Cada versión nueva se reparte a mano: se construye un `.archmuse` (o un `.exe`), se manda y se instala con doble clic. Pablo, 2026-09-15: «Actualizar con el .exe completo cada vez es inviable, para mí y para el arquitecto». Con el `.archmuse` es menos pesado, pero sigue siendo descargar a mano, y el arquitecto se queda en la versión que tenga si nadie se lo recuerda. Además, hoy nada garantiza que un `.archmuse` lo haya construido ArchMuse: `validar_paquete` sólo mira su forma.

## 2. Usuario afectado

- **El arquitecto de la beta** (canal «estable»): no sabe de informática; tiene que enterarse de que hay versión nueva y poder instalarla sin descargar nada.
- **Pablo** (canal «prueba»): prueba cada versión antes que el arquitecto, con exactamente el mismo mecanismo.

## 3. Objetivo de negocio

Que las correcciones lleguen a la beta el mismo día sin coste de soporte, y que la beta mida siempre con una versión conocida (D-2: las cifras llevan la versión). Un canal de prueba protege al arquitecto de un build roto.

## 4. Objetivo técnico

1. `construir.py` pone solo el número de versión (siguiente al último usado) y firma el `.archmuse`.
2. Un solo comando publica en GitHub Releases como prerelease («prueba»); un solo comando lo promueve a release («estable»). Ninguno se ejecuta sin Pablo.
3. Al arrancar la sesión, el servidor comprueba en segundo plano si hay versión nueva en su canal, la descarga y **verifica la firma**. Si todo cuadra, deja la actualización pendiente en un fichero local.
4. Al abrir AutoCAD, el comando lee ese fichero (sin red) y pregunta «Hay una actualización (x.y.z). ¿Instalar?». Un clic la instala con el mecanismo actual, con vuelta atrás.
5. Nada sin firma válida se instala, ni por aviso ni con doble clic.

## 5. Casos de uso

1. **Pablo publica 0.3.9 en prueba.** Su servidor, al iniciar sesión, la encuentra, la descarga y la verifica. Al abrir AutoCAD le pregunta; dice que sí; se instala; reabre AutoCAD.
2. **Pablo la promueve a estable.** La del arquitecto hace lo mismo en su próxima sesión.
3. **El arquitecto dice que no.** No se le vuelve a preguntar en esa sesión de AutoCAD; en la siguiente, sí. Siempre puede teclear `ARCHMUSE-ACTUALIZAR`.
4. **La versión nueva va peor.** Menú Inicio → «volver a la versión anterior», como hoy.

## 6. Casos límite

| Caso | Comportamiento |
|---|---|
| Sin internet, GitHub caído o lento | Plazo corto (5 s) en un hilo del servidor; AutoCAD no espera nada. Motivo al registro. **Sin aviso**, y se borra el pendiente anterior **[decisión: literal del encargo]**. |
| Versión igual o más vieja que la instalada | No hay aviso. |
| Prerelease con el canal «estable» | Se ignora. «Prueba» ve prereleases **y** releases **[decisión]**. |
| Firma mala, fichero manipulado, fichero de más o de menos | Se descarta y se borra; motivo al registro; sin aviso. |
| El paquete dice otra versión que la etiqueta | Se descarta. |
| `S::STARTUP` definido por otro programa sin `defun-q` | No se engancha y no rompe la carga; queda `ARCHMUSE-ACTUALIZAR`. |
| AutoCAD en mitad de un comando | No se pregunta (`CMDACTIVE`). |
| Instalación de desarrollo, sin versión activa | No se comprueba nada. |
| `.archmuse` de antes de la firma (≤ 0.3.8) con doble clic | Se rechaza y se dice por qué. La **primera** 0.3.9 se instala con el actualizador viejo, que no comprueba firmas. |

## 7. Flujo del usuario

1. Inicia sesión en Windows. El servidor arranca y, en segundo plano, comprueba su canal.
2. Abre AutoCAD. Si hay una actualización verificada, sale una ventana: «Hay una actualización (0.3.9). ¿Instalar?» [Sí] [No]. Se cierra sola a los 60 s con «No».
3. Sí → la línea de comandos dice «Instalando ArchMuse 0.3.9. Cuando termine, cierra y vuelve a abrir AutoCAD», y el actualizador avisa al acabar.
4. Reabre AutoCAD: el comando ya es el nuevo (D-2 impide usar el viejo contra el servidor nuevo).

## 8. Criterios de aceptación

1. `construir.py` sin argumentos construye la **0.3.9**, la anota como usada y firma el `.archmuse`.
2. `publicar.py 0.3.9` y `publicar.py --promover 0.3.9` son una orden cada uno, y `--mostrar` enseña la orden sin ejecutarla.
3. Tests en verde para: versión nueva, igual y más vieja; canal equivocado; firma mala; fichero manipulado; sin red; GitHub caído; GitHub lento.
4. Prueba de punta a punta en local, con un GitHub simulado: comprobar → pendiente → instalar pendiente → versión activa nueva → volver atrás.
5. La clave privada está fuera del repositorio, `.gitignore` la cubre y un test comprueba que no hay ninguna versionada.
6. Guardianes rotos a propósito: sin verificar la firma, los tests de firma fallan.

## 9. Riesgos

- **Sin ejecutar en AutoCAD:** `S::STARTUP` con un paquete de AutoCAD cargado por el autoloader, `WScript.Shell.Popup` desde AutoLISP y el valor que devuelve. Se prueba en la VM antes de publicar en estable.
- **Clave privada:** si se pierde, no se pueden publicar más actualizaciones (hará falta un instalador nuevo con otra pública). Si se filtra, alguien podría firmar. Vive fuera del repo y hay que copiarla a un sitio seguro.
- **Arranque:** la primera 0.3.9 no llega sola a las instalaciones de hoy; hay que instalarla una vez con doble clic.
- **Límite de la API de GitHub** sin autenticar: 60 peticiones por hora por IP; se hace una por sesión.
- **Implementación de Ed25519 en Python puro:** se valida contra los vectores de la RFC 8032 y contra `cryptography`.

## 10. Impacto sobre módulos existentes

- `empaquetado/capa_b/`: nuevos `firma.py` y `actualizaciones.py`; `actualizador.pyw` (firma al instalar, `--instalar-pendiente`, `--comprobar`, `--canal`); `lanzador.pyw` (comprobación en segundo plano).
- `empaquetado/construir.py` (número automático, firma, orden de publicación) y nuevo `empaquetado/publicar.py`; nuevo `empaquetado/versiones_usadas.txt`.
- `autocad/archmuse.lsp`: aviso al arrancar y `ARCHMUSE-ACTUALIZAR` (3.8.0).
- `tests/test_empaquetado.py`: sus paquetes de prueba pasan a ir firmados con una clave de test.
- `.gitignore`.

## 11. Plan de implementación

1. `firma.py`: Ed25519 (RFC 8032) + manifiesto firmado dentro del `.archmuse`. Tests con vectores.
2. Clave: generar fuera del repo; pública en `firma.py`; `.gitignore`.
3. `construir.py`: registro de versiones usadas, número automático, firma.
4. `actualizaciones.py`: canal, consulta a GitHub con plazo, elección, descarga, verificación, pendiente.
5. `actualizador.pyw` y `lanzador.pyw`.
6. `publicar.py`.
7. `.lsp`: aviso y comando.
8. Tests de todos los casos y la prueba de punta a punta con GitHub simulado.
9. Suite, `.archmuse` 0.3.9 sin publicar.

## 12. Plan de pruebas

`tests/test_actualizaciones.py` con un servidor HTTP local que imita la API de releases de GitHub y sirve los paquetes. Los casos del §8.3, la prueba de punta a punta del §8.4 sobre un árbol de mentira (`ARCHMUSE_BASE`), y romper a propósito la verificación. En AutoCAD, en la VM: aviso al arrancar, «Sí», reabrir, `ARCHMUSE-ACTUALIZAR`.

## 13. Métricas para medir el éxito

- Días entre publicar en estable y que el registro del arquitecto mida con esa versión.
- Líneas «actualización descartada» en los registros: tienen que ser cero salvo red caída.
- Instalaciones a mano de `.archmuse` después de la 0.3.9: cero.

## 14. Posibles motivos para NO implementar la idea

- Es la **primera conexión saliente** de ArchMuse: el PRD de la beta presumía de no llamar a casa («sin auto-actualización y sin llamar a casa»). El folio de una hoja del 2026-09-15 sólo dice «Todo ocurre en tu ordenador», que sigue siendo verdad para los planos, pero **conviene decirle al arquitecto** que ArchMuse consulta GitHub al iniciar sesión para ver si hay versión nueva, y nada más.
- Con un único usuario beta, publicar a mano sigue siendo barato. El valor real aparece con el segundo o tercer estudio.
- Firmar sin firma de código de Windows no quita el aviso de SmartScreen del instalador; sólo protege el canal de actualizaciones.

---

**Decisión:** implementar (encargo de Pablo del 2026-09-15). Pendiente de su revisión: el cambio del folio (§14) y la prueba en la VM (§9).
