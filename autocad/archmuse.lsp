;;; ===========================================================================
;;; ArchMuse — comando ARCHMUSE para AutoCAD
;;; ===========================================================================
;;;
;;; Mide las superficies útiles de la planta dibujada y **rellena el cuadro de
;;; superficies que el arquitecto ya tiene dibujado en su plano**.
;;;
;;; PRD: docs/prd/2026-09-10-rellenar-el-cuadro-del-arquitecto.md (APROBADO).
;;; Anterior: docs/prd/2026-09-08-integracion-autocad-autolisp.md (tareas 5 y 6).
;;; Checklist de la primera prueba: docs/design/checklist-primera-prueba-autocad.md
;;;
;;; ---------------------------------------------------------------------------
;;; CAMBIO DE OBJETIVO DEL 2026-09-10: SE RELLENA SU CUADRO, NO SE INSERTA OTRO
;;; ---------------------------------------------------------------------------
;;; Hasta hoy este comando insertaba una tabla nueva con formato de ArchMuse. El
;;; arquitecto pidió lo contrario: que le **rellenen la suya**, la que su estudio
;;; ya tiene maquetada, respetando sus filas y su redacción. No es un cambio de
;;; formato, es un cambio de a quién pertenece el entregable — una tabla nueva al
;;; lado de la suya no le ahorra el trabajo, se lo cambia por comparar dos tablas
;;; y copiar de una a otra.
;;;
;;; ---------------------------------------------------------------------------
;;; EJECUTADO POR PRIMERA VEZ EL 2026-09-09, EN AUTOCAD 2027
;;; ---------------------------------------------------------------------------
;;; Se escribió el 2026-09-09 sin AutoCAD instalado y se ejecutó ese mismo día en
;;; AutoCAD 2027. Cargó con APPLOAD sin un error de sintaxis, reconoció la capa,
;;; llamó al servidor y dibujó su tabla con las cifras correctas. **Pero lo que
;;; se ejecutó aquel día era el comando anterior**: de todo lo que hay debajo de
;;; esta línea, lo único probado en AutoCAD es la parte que no ha cambiado —la
;;; selección, el POST y la lectura de la respuesta—. El cuadro del arquitecto,
;;; `vla-GetText`, `vla-SetText` y la marca en su capa **no se han ejecutado
;;; nunca**. Ver `docs/PROGRESS.md`, 2026-09-10.
;;;
;;; ---------------------------------------------------------------------------
;;; TRES DECISIONES DE DISEÑO QUE CONVIENE LEER ANTES DE TOCAR NADA
;;; ---------------------------------------------------------------------------
;;;
;;; 1. **Este script no decide nada.** Manda las polilíneas y los textos EN
;;;    CRUDO y dibuja lo que le devuelven. Qué rótulo pertenece a qué recinto lo
;;;    resuelve `parser.match_label_to_room` en el servidor, donde ya está
;;;    probado. Reimplementar aquí ese criterio sería una segunda implementación
;;;    de un criterio profesional, que es lo que prohíbe `D-7`.
;;;
;;; 2. **No se usa `read` sobre la respuesta.** `read` tiene un tope de unos
;;;    2.300 caracteres y la respuesta de una planta de tres viviendas ocupa
;;;    6.564 (medido el 2026-09-09); la de seis viviendas pasa de 13.000. Así
;;;    que se extraen los pocos valores que la tabla necesita con búsqueda de
;;;    cadenas, sin construir listas. No es un parser: es un lector de cuatro
;;;    campos con nombre.
;;;
;;; 3. **La selección deja fuera polilíneas que el navegador sí mide, y se
;;;    dice.** `ssget` sólo sabe filtrar por el bit de «cerrada» del código 70.
;;;    El lector de Python además recupera las que tienen el flag mal puesto
;;;    pero cierran geométricamente (tolerancia del 1% de su diagonal), y en los
;;;    planos reales eso son 3 de 22 en `V5.dxf`, 2 de 10 en `v2s.dxf` y 9 de 53
;;;    en `ejemplo.dxf` — hasta un 17%. Aquí NO se replica esa tolerancia (es
;;;    criterio del parser, y duplicarlo repetiría el error de la decisión 1),
;;;    así que el comando **cuenta las que deja fuera y las anuncia antes de
;;;    enviar**. Una omisión silenciosa sería superficie que falta sin que nadie
;;;    lo sepa. La solución buena es de servidor: que el payload lleve el flag
;;;    de cerrada por recinto y decida `parser._esta_cerrada`. Está propuesta
;;;    en `PROGRESS.md` y no se ha hecho porque tocaría el endpoint.
;;;
;;; Uso:  APPLOAD este fichero, teclear ARCHMUSE.
;;; Requiere AutoCAD COMPLETO. En AutoCAD LT `vlax-create-object` devuelve nil
;;; siempre y no hay forma de hacer la petición.
;;; ===========================================================================

(vl-load-com)

;; **El puerto no se da por hecho** (D-1 del PRD de la beta). El servidor
;; instalado prueba 5000, 5001… y escribe el que ha cogido en
;; `%LOCALAPPDATA%\ArchMuse\servidor.json`. Sin ese fichero —la máquina de
;; desarrollo— vale 5000, que es lo de siempre. Ver `am:puerto`.
(setq *am:puerto-por-defecto* 5000)
;; **Dos formas de la misma versión, y las dos hacen falta.** La corta es la
;; que se coteja con la que declara el servidor (D-2 del PRD de la beta: si no
;; es la misma, no se escribe) y la que cabe en una línea de registro. La
;; larga es la que se le enseña a él al arrancar el comando. Un test comprueba
;; que la larga empieza por la corta, porque dos números que se separan son
;; peor que uno solo.
(setq *am:version-corta* "3.9.10")
(setq *am:version*  "3.9.10 (2026-09-17, abrir el dibujo de las habitaciones ya no falla con «stringp T»)")
;; **Cuánto espera la rama C a que el servidor conteste** (D-1). Eran 20 s, y
;; salían de una máquina rápida (`import app` en 2,75 s). Medido el 2026-09-14
;; en la VM de Windows 11 limpia: `import app` en 15,6 s en caliente y 21,5 s al
;; iniciar sesión tras reiniciar; el arranque en frío no se ha medido. 90 s son
;; unas cuatro veces la peor medida. El
;; actualizador espera más (`PLAZO_ARRANQUE_S`, 180 s) porque el primer arranque
;; tras instalar es el más frío. Cada arranque deja su tiempo real en el
;; registro del servidor («listo … s después de arrancar»).
(setq *am:plazo-arranque-s* 90)
(setq *am:capa-por-defecto* "00 areas")

;; Cuántas celdas del cuadro se mandaron en la última llamada. Es global porque
;; la escribe `am:recolectar` y la lee el comando cuando aquélla ya ha terminado:
;; el alcance dinámico de AutoLISP hace visible lo de fuera hacia dentro, nunca
;; al revés.
(setq *am:celdas-enviadas* 0)

;; Si la capa de recintos la nombró él o la propuso ArchMuse. Global por el
;; mismo motivo que la de arriba: la escribe `am:elegir-capa` y la lee el
;; comando cuando aquélla ya ha terminado.
(setq *am:capa-la-dijo-el-usuario* nil)
(setq *am:capa-elegida* nil)

;; La versión que ha dicho el servidor en la última respuesta. Hasta que
;; conteste una vez, no se sabe — y «desconocida» es la respuesta correcta, no
;; una cadena vacía que se leería como que no la declara.
(setq *am:version-del-servidor* "desconocida")

;; La capa de la marca de borrador. **Tiene que ser la misma que
;; `analyzer/marca_borrador.CAPA_DXF`**: si las dos vías marcan en capas
;; distintas, el mismo plano acaba con dos, y quien apague una seguirá viendo la
;; otra. Hay un test que compara las dos cadenas
;; (`tests/test_marca_borrador.py`), porque entre Python y LISP no hay forma de
;; compartir una constante — mientras no la declare el servidor, que es lo que
;; propone la deuda P2 del PRD.
(setq *am:capa-de-la-marca* "ARCHMUSE - BORRADOR")

;; Por qué no se ha podido dibujar la tabla, lo que se ha dibujado sin algo que
;; se pidió, y si llegó a dibujarse algo. Los rellena `am:dibujar-cuadro` y los
;; lee el comando. **Existen porque un fallo del que sólo se sabe que ocurrió no
;; se puede arreglar**: la 3.4.0 dijo en AutoCAD «No he podido dibujar la tabla»
;; y nada más, con el mensaje de AutoCAD ya capturado y tirado dentro del handler.
(setq *am:fallo-del-dibujo* nil)
(setq *am:avisos-del-dibujo* nil)
(setq *am:dibujo-empezado* nil)
;; Por qué no se han podido medir los textos de la tabla con `textbox` (3.5.0).
(setq *am:fallo-de-la-medida* nil)

;; Leyenda de `C3`, literal y sin opción de desactivarla. Es la misma frase que
;; `analyzer/marca_borrador.py` estampa en el resto de entregables: si cambia
;; allí, tiene que cambiar aquí.
(setq *am:leyenda-borrador*
  "BORRADOR PARA REVISIÓN DE UN COLEGIADO. ArchMuse asesora; el proyecto lo firma el arquitecto que lo redacta.")

;;; ---------------------------------------------------------------------------
;;; EL REGISTRO LOCAL — T6 DEL PRD DE LA BETA
;;; ---------------------------------------------------------------------------
;;; `docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`, §4.4.
;;;
;;; **Por qué el registro lo escribe el cliente y no el servidor.** Parece más
;;; cómodo que lo escriba Python —es donde hay tests y donde ya está la
;;; versión—, y es justo lo que no puede ser: **un registro que depende del
;;; servidor está mudo exactamente cuando el servidor es el problema**, que es
;;; el fallo nº 1 que va a tener esta beta. El `.lsp` es la única pieza que está
;;; siempre, así que es la que escribe.
;;;
;;; **Dónde vive: `%LOCALAPPDATA%\ArchMuse\registro`.** NO en `Documentos` ni en
;;; el `Escritorio`, porque los dos suelen estar sincronizados con OneDrive, y
;;; un registro que se sube a la nube contradice la única frase que le hemos
;;; prometido al arquitecto. Él no navega hasta ahí nunca: el informe se le deja
;;; en el escritorio y se le abre la carpeta.
;;;
;;; **QUÉ SE ESCRIBE:** fecha y hora · versión del `.lsp` · versión del servidor
;;; · versión de AutoCAD · **el nombre del dibujo, sin su ruta** · la capa
;;; elegida y quién la eligió · y el suceso, que siempre es un recuento o un
;;; mensaje de error.
;;;
;;; **QUÉ NO SE ESCRIBE NUNCA, y es la mitad importante de este bloque:** ni un
;;; vértice, ni un rótulo, ni el contenido de una celda del cuadro, ni la ruta
;;; del fichero. Los nombres de las estancias y los textos del cuadro **son el
;;; proyecto de su cliente**, y la ruta suele llevar el nombre del cliente
;;; dentro. Por eso `am:log` recibe UNA cadena ya construida por quien llama, y
;;; ninguna de las funciones que arman el payload (`am:recolectar`,
;;; `am:json-vertices`, `am:celdas-json`) la llama jamás. Hay un test que lo
;;; comprueba leyendo este fichero.
;;;
;;; **Nada de esto puede tumbar el comando.** Si no hay `%LOCALAPPDATA%`, si el
;;; disco está lleno o si el fichero está abierto por otro, `am:log` se calla y
;;; sigue. Perder una línea de registro es barato; perder la medición por no
;;; haber podido escribirla, no.

(setq *am:carpeta-de-archmuse* nil)

(defun am:carpeta ( / base)
  ;; `%LOCALAPPDATA%\ArchMuse`, creada si hace falta. nil si no se puede, y
  ;; entonces todo lo de abajo se degrada a no registrar nada.
  (if *am:carpeta-de-archmuse*
    *am:carpeta-de-archmuse*
    (progn
      (setq base (getenv "LOCALAPPDATA"))
      (if (null base)
        nil
        (progn
          (setq base (strcat base "\\ArchMuse"))
          (if (not (vl-file-directory-p base)) (vl-mkdir base))
          (if (vl-file-directory-p base)
            (setq *am:carpeta-de-archmuse* base)
            nil))))))


(defun am:carpeta-de-registro ( / base carpeta)
  (setq base (am:carpeta))
  (if (null base)
    nil
    (progn
      (setq carpeta (strcat base "\\registro"))
      (if (not (vl-file-directory-p carpeta)) (vl-mkdir carpeta))
      (if (vl-file-directory-p carpeta) carpeta nil))))


(defun am:ahora ()
  ;; `$(edtime)` de DIESEL, que es la única forma de formatear una fecha en
  ;; AutoLISP sin hacer aritmética sobre el real de `CDATE` — y la aritmética
  ;; sobre `CDATE` pierde los segundos por redondeo del coma flotante.
  (menucmd "M=$(edtime,$(getvar,date),YYYY-MO-DD HH:MM:SS)"))


(defun am:mes-actual ()
  (menucmd "M=$(edtime,$(getvar,date),YYYY-MO)"))


(defun am:fichero-de-registro ( / carpeta)
  (setq carpeta (am:carpeta-de-registro))
  (if carpeta
    (strcat carpeta "\\archmuse-" (am:mes-actual) ".log")
    nil))


(defun am:contexto ( / capa)
  ;; La cabecera de cada línea. Todo lo de aquí es una versión o un recuento,
  ;; menos el nombre del dibujo — que es `DWGNAME`, el nombre **sin la ruta**.
  ;; `DWGPREFIX` (la carpeta) no aparece en este fichero ni una vez, y no es un
  ;; olvido: ahí es donde vive el nombre del cliente.
  (setq capa (if *am:capa-elegida* *am:capa-elegida* "-"))
  (strcat "lsp " *am:version-corta*
          " | srv " *am:version-del-servidor*
          " | acad " (getvar "ACADVER")
          " | " (getvar "DWGNAME")
          " | capa " capa
          (if *am:capa-elegida*
            (if *am:capa-la-dijo-el-usuario* " (dicha)" " (propuesta)")
            "")))


(defun am:log (suceso / ruta f)
  ;; Una línea, y ni un error hacia fuera pase lo que pase.
  (setq ruta (am:fichero-de-registro))
  (if ruta
    (progn
      (setq f (vl-catch-all-apply 'open (list ruta "a")))
      (if (and f (not (vl-catch-all-error-p f)))
        (progn
          (vl-catch-all-apply
            'write-line (list (strcat (am:ahora) " | " (am:contexto) " | " suceso) f))
          (vl-catch-all-apply 'close (list f))))))
  (princ))


;;; ---------------------------------------------------------------------------
;;; Utilidades de cadena
;;; ---------------------------------------------------------------------------

(defun am:pos (patron cadena desde / p)
  ;; `vl-string-search` devuelve la posición (base 0) o nil.
  (if (< desde (strlen cadena))
    (vl-string-search patron cadena desde)
    nil))

(defun am:car-en (cadena i)
  ;; Carácter en la posición base 0 `i`. `substr` es base 1.
  (substr cadena (1+ i) 1))

(defun am:lee-cadena (cadena i / fin ch res escapado seguir)
  ;; Lee una cadena entrecomillada de LISP que EMPIEZA en la comilla de `i`.
  ;; Devuelve (texto . posicion-tras-la-comilla-final), o nil.
  ;; Se hace a mano y no con `read` por el tope de longitud, y porque los
  ;; motivos traen paréntesis de verdad («el reparto de 2 pieza(s)…»): contar
  ;; paréntesis sin saber si se está dentro de una cadena daría un fin falso.
  (if (/= (am:car-en cadena i) "\"")
    nil
    (progn
      (setq fin (1+ i) res "" escapado nil seguir T)
      (while (and seguir (< fin (strlen cadena)))
        (setq ch (am:car-en cadena fin))
        (cond
          (escapado          (setq res (strcat res ch) escapado nil))
          ((= ch "\\")       (setq escapado T))
          ((= ch "\"")       (setq seguir nil))
          (T                 (setq res (strcat res ch))))
        (setq fin (1+ fin)))
      (cons res fin))))

(defun am:valor-tras (cadena clave desde / marca p ini fin ch)
  ;; El átomo que sigue a `("clave" . ` a partir de `desde`.
  ;; Devuelve la cadena tal cual («45.0», «nil», «VT1/3»), o nil si no está.
  ;; Los tres campos que la tabla necesita son átomos, nunca listas.
  (setq marca (strcat "(\"" clave "\" . "))
  (setq p (am:pos marca cadena desde))
  (if (null p)
    nil
    (progn
      (setq ini (+ p (strlen marca)))
      (if (= (am:car-en cadena ini) "\"")
        (car (am:lee-cadena cadena ini))
        (progn
          (setq fin ini)
          (while (and (< fin (strlen cadena))
                      (setq ch (am:car-en cadena fin))
                      (/= ch ")")
                      (/= ch " "))
            (setq fin (1+ fin)))
          (substr cadena (1+ ini) (- fin ini)))))))




;;; ---------------------------------------------------------------------------
;;; Serialización a JSON — sólo lo que hay que mandar
;;; ---------------------------------------------------------------------------

(defun am:esc (s / i ch res)
  ;; Escapa comilla y barra invertida. Un rótulo con comillas partiría el JSON
  ;; en el servidor, y ese fallo sólo aparecería con el plano de alguien.
  (setq i 0 res "")
  (while (< i (strlen s))
    (setq ch (am:car-en s i))
    (setq res
      (cond ((= ch "\"") (strcat res "\\\""))
            ((= ch "\\") (strcat res "\\\\"))
            ((= ch "\n") (strcat res "\\n"))
            ((= ch "\r") (strcat res "\\r"))
            ((= ch "\t") (strcat res "\\t"))
            (T           (strcat res ch))))
    (setq i (1+ i)))
  res)

(defun am:json-num (x)
  ;; Seis decimales: la geometría de un DXF no tiene más, y `rtos` en modo 2
  ;; no usa notación científica, que el JSON del servidor no aceptaría.
  (rtos x 2 6))

(defun am:json-cad (s) (strcat "\"" (am:esc s) "\""))

(defun am:json-vertices (puntos / res primero)
  (setq res "[" primero T)
  (foreach p puntos
    (if (not primero) (setq res (strcat res ",")))
    (setq res (strcat res "[" (am:json-num (car p)) "," (am:json-num (cadr p)) "]"))
    (setq primero nil))
  (strcat res "]"))

;;; ---------------------------------------------------------------------------
;;; Lectura del dibujo
;;; ---------------------------------------------------------------------------

(defun am:vertices-de (ename / datos res)
  ;; Todos los códigos 10 de una LWPOLYLINE. `assoc` sólo daría el primero.
  (setq datos (entget ename) res nil)
  (foreach par datos
    (if (= 10 (car par))
      (setq res (cons (list (cadr par) (caddr par)) res))))
  (reverse res))

(defun am:texto-de (ename / datos res)
  ;; El contenido de un TEXT o un MTEXT.
  ;;
  ;; **Un MTEXT de mas de 250 caracteres parte su contenido**: los trozos van en
  ;; codigos 3, en orden, y el ultimo en el codigo 1. Leer solo el 1 devolveria
  ;; el final del rotulo y perderia el principio, y el servidor buscaria una
  ;; estancia llamada como la cola de otra. Rotulos asi son raros, pero el fallo
  ;; seria mudo y solo aparecería en el plano de alguien.
  (setq datos (entget ename) res "")
  (foreach par datos
    (if (= 3 (car par)) (setq res (strcat res (cdr par)))))
  (foreach par datos
    (if (= 1 (car par)) (setq res (strcat res (cdr par)))))
  res)

(defun am:punto-de-texto (ename / datos tipo halign valign alineado)
  ;; El punto de inserción EFECTIVO, con la misma regla que
  ;; `parser._punto_de_texto`: un TEXT alineado guarda su posición real en el
  ;; código 11, y el 11 sólo cuenta si halign (72) o valign (73) no son cero.
  ;; Ignorarlo deja el rótulo donde no está y el servidor lo asociaría a la
  ;; habitación equivocada. No es criterio: es la especificación del DXF.
  (setq datos (entget ename)
        tipo  (cdr (assoc 0 datos))
        halign (cdr (assoc 72 datos))
        valign (cdr (assoc 73 datos)))
  (setq alineado (and (= tipo "TEXT")
                      (or (and halign (/= halign 0))
                          (and valign (/= valign 0)))
                      (assoc 11 datos)))
  (if alineado
    (list (cadr (assoc 11 datos)) (caddr (assoc 11 datos)))
    (list (cadr (assoc 10 datos)) (caddr (assoc 10 datos)))))

(defun am:capas-con-recintos ( / ss i ename datos capa capas par flags con-flag)
  ;; Capas con polilíneas, y cuántas de cada una llevan el flag de cerrada.
  ;;
  ;; **Cuenta TODAS, no sólo las que llevan el flag**, y por un motivo que costó
  ;; una sesión de depuración: hasta el 2026-09-10 este recuento filtraba por el
  ;; bit del código 70 y era el que se imprimía al elegir capa. Sobre
  ;; `v1plantas.dxf` decía «8 polilíneas cerradas» cuando la capa tiene **10**,
  ;; y las 2 que no salían eran justo las del flag mal puesto — una de ellas el
  ;; salón. El mensaje no era el fallo, pero mandó la búsqueda al sitio
  ;; equivocado, que es lo que hace un mensaje que cuenta una cosa distinta de
  ;; la que se manda.
  ;;
  ;; Ahora los dos números viajan juntos: lo que hay y lo que `ssget` sabría
  ;; reconocer como cerrado. La diferencia entre los dos es exactamente lo que
  ;; el servidor tiene que recuperar.
  (setq ss (ssget "_X" '((0 . "LWPOLYLINE"))))
  (setq capas nil i 0)
  (if ss
    (while (< i (sslength ss))
      (setq ename (ssname ss i)
            datos (entget ename)
            capa  (cdr (assoc 8 datos))
            flags (if (assoc 70 datos) (cdr (assoc 70 datos)) 0)
            con-flag (if (= 1 (logand flags 1)) 1 0)
            par   (assoc capa capas))
      (if par
        (setq capas (subst (list capa (1+ (cadr par)) (+ con-flag (caddr par)))
                           par capas))
        (setq capas (cons (list capa 1 con-flag) capas)))
      (setq i (1+ i))))
  (reverse capas))

(defun am:describe-capa (par)
  ;; «10 polilíneas, 8 con el flag de cerrada». Los dos números, siempre: el
  ;; segundo es lo que `ssget` reconocería por su cuenta y el primero lo que se
  ;; manda de verdad.
  (strcat (itoa (cadr par)) " polilínea(s), " (itoa (caddr par))
          " con el flag de cerrada"))


(defun am:mete-ordenado (par lista)
  ;; Inserción ordenada por número de polilíneas, de más a menos. Se escribe a
  ;; mano en vez de usar `vl-sort` porque `vl-sort` **elimina los elementos que
  ;; su función de comparación considera iguales**, y dos capas con el mismo
  ;; recuento son exactamente el caso en el que hay que enseñárselas las dos.
  (cond
    ((null lista) (list par))
    ((> (cadr par) (cadr (car lista))) (cons par lista))
    (T (cons (car lista) (am:mete-ordenado par (cdr lista))))))


(defun am:ordena-capas (capas / res)
  (setq res nil)
  (foreach par capas (setq res (am:mete-ordenado par res)))
  res)


(defun am:capa-por-nombre (texto capas / objetivo encontrada)
  ;; La capa que se llama así, sin distinguir mayúsculas: «00 Areas» y
  ;; «00 areas» son la misma capa para un arquitecto. Mismo criterio que
  ;; `parser._buscar_capa` en el servidor — que las dos vías acepten lo mismo
  ;; escrito igual es parte de `C-9`.
  ;;
  ;; Devuelve el nombre TAL COMO ESTÁ EN EL DIBUJO, no lo que él tecleó: es lo
  ;; que va al `ssget` y lo que se escribe en los mensajes.
  (setq objetivo (strcase texto) encontrada nil)
  (foreach par capas
    (if (and (null encontrada) (= (strcase (car par)) objetivo))
      (setq encontrada (car par))))
  encontrada)


(defun am:capa-por-numero (texto capas / n)
  ;; «3» -> la tercera de la lista que se acaba de imprimir.
  ;;
  ;; `atoi` devuelve 0 para lo que no es un número, y 0 nunca es un índice
  ;; válido porque la lista se numera desde 1: el mismo cero sirve de rechazo,
  ;; sin necesidad de comprobar aparte si el texto era un número.
  (setq n (atoi texto))
  (if (and (> n 0) (<= n (length capas)))
    (car (nth (1- n) capas))
    nil))


;;; ---------------------------------------------------------------------------
;;; C-15 · LOS RECINTOS EN UNA REFERENCIA EXTERNA: SE DICE DÓNDE, Y NO SE MIDE
;;; ---------------------------------------------------------------------------
;;; Firmado por Pablo el 2026-09-15. Criterio en
;;; `docs/design/2026-09-08-criterios-firmados-de-medicion.md` (`C-15`); las
;;; mediciones, en `docs/PROGRESS.md` del mismo día.
;;;
;;; **El caso.** Un estudio monta sus hojas referenciando un plano maestro
;;; (`plantas base.dwg`): al pinchar una habitación, AutoCAD cambia a la pestaña
;;; «Referencia externa». `ssget "_X"` no ve nada de lo que hay dentro de una
;;; xref —medido con AutoCAD Core Console—, así que en una hoja el comando no
;;; encontraba la capa de recintos, **culpaba a su nombre** y ofrecía elegir
;;; otra de la lista. Elegir otra ahí acaba en una cifra falsa.
;;;
;;; **Lo que hace ahora, antes de buscar el cuadro y antes de ofrecer capa:**
;;; · si una xref CARGADA tiene polilíneas en la capa de recintos, dice qué
;;;   fichero es, que los recintos —y el cuadro, si también está— están ahí, y
;;;   que lo abra. **No ofrece otra capa** y no mide.
;;; · si además hay recintos en este dibujo, tampoco mide: medir sólo los de
;;;   aquí daría una cifra de menos, y ésa no se ve (firmado por Pablo: «una
;;;   cifra de menos es peor que no medir»).
;;; · con la capa que él elija, si es otra, se repite la comprobación.
;;; · si hay xrefs SIN CARGAR y ningún recinto en la capa por defecto, avisa de
;;;   que pueden estar ahí y **sigue ofreciendo la lista**: de una xref sin
;;;   cargar no se puede saber qué tiene, así que no hay detección. Decidido así
;;;   por Pablo, por ahora. **RIESGO ABIERTO:** si elige una capa cualquiera,
;;;   puede salir una cifra falsa igual.
;;;
;;; **Leer una xref cargada sí se puede** (medido): su contenido vive en la
;;; definición de su bloque y se recorre con `tblobjname` + `entnext`. Sus capas
;;; llegan como «plantas base|00 areas». Aquí sólo se cuenta: medir dentro
;;; exigiría transformar las coordenadas por la inserción, y eso no se ha probado.
;;;
;;; **Alcance, dicho:** medido en UN estudio (70 DWG), donde el cuadro vive con
;;; sus recintos en el maestro y el caso es molesto. Otro estudio que ponga el
;;; cuadro en la hoja y los recintos en la xref caerá aquí cada vez.

(defun am:capa-sin-xref (nombre / p)
  ;; «plantas base|00 areas» -> «00 areas». Con xrefs anidadas hay más de un
  ;; prefijo, y la capa es siempre lo que va tras la última barra.
  (while (setq p (vl-string-search "|" nombre))
    (setq nombre (substr nombre (+ p 2))))
  nombre)

(defun am:fichero-de-xref (ruta / ext)
  ;; Sólo el nombre del fichero, nunca la carpeta: la carpeta de un proyecto
  ;; suele llevar el nombre del cliente (la misma regla que el registro).
  (setq ext (vl-filename-extension ruta))
  (strcat (vl-filename-base ruta) (if ext ext "")))

(defun am:textos-de-entidad (datos / res)
  ;; Todas las cadenas de una entidad (códigos 1, 3, 302 y 303), juntas. Sirve
  ;; para reconocer el título de un cuadro dentro de una xref, donde se lee con
  ;; `entget` y no con el objeto ActiveX de la tabla.
  (setq res "")
  (foreach g datos
    (if (and (member (car g) '(1 3 302 303)) (= (type (cdr g)) 'STR))
      (setq res (strcat res " " (cdr g)))))
  res)

(defun am:xrefs ( / b fl res)
  ;; Las referencias externas del dibujo: ((bloque fichero cargada) ...). En la
  ;; tabla de bloques, el bit 4 del código 70 es «xref» y el 32 «cargada».
  (setq res nil b (tblnext "BLOCK" T))
  (while b
    (setq fl (cdr (assoc 70 b)))
    (if (= 4 (logand 4 fl))
      (setq res (cons (list (cdr (assoc 2 b))
                            (am:fichero-de-xref (if (assoc 1 b) (cdr (assoc 1 b)) (cdr (assoc 2 b))))
                            (= 32 (logand 32 fl))
                            (if (assoc 1 b) (cdr (assoc 1 b)) (cdr (assoc 2 b))))
                      res)))
    (setq b (tblnext "BLOCK")))
  (reverse res))

(defun am:contenido-de-xref (bloque capa / e datos recintos cuadros titulo)
  ;; (polilíneas-en-la-capa cuadros) dentro de una xref cargada. Una xref
  ;; anidada es otro bloque de la tabla con su propio bit 4: `am:xrefs` la
  ;; lista aparte, así que aquí no se baja por las inserciones.
  (setq recintos 0 cuadros 0
        titulo (am:mayusculas-sin-tildes *am:titulo-del-cuadro*)
        e (tblobjname "BLOCK" bloque))
  (if e
    (while (setq e (entnext e))
      (setq datos (entget e))
      (cond
        ((and (= (cdr (assoc 0 datos)) "LWPOLYLINE")
              (= (strcase (am:capa-sin-xref (cdr (assoc 8 datos)))) (strcase capa)))
          (setq recintos (1+ recintos)))
        ((and (= (cdr (assoc 0 datos)) "ACAD_TABLE")
              (vl-string-search titulo (strcase (am:textos-de-entidad datos))))
          (setq cuadros (1+ cuadros))))))
  (list recintos cuadros))

(defun am:xrefs-con-recintos (capa / res c)
  ;; Las xref CARGADAS con polilíneas en `capa`: ((fichero recintos cuadros ruta) ...).
  (setq res nil)
  (foreach x (am:xrefs)
    (if (caddr x)
      (progn
        (setq c (am:contenido-de-xref (car x) capa))
        (if (> (car c) 0)
          (setq res (cons (list (cadr x) (car c) (cadr c) (nth 3 x)) res))))))
  (reverse res))

(defun am:ruta-de-xref (ruta / prefijo encontrada)
  ;; `(encontrada mostrada)`: la ruta del dibujo referenciado si existe, o nil, y la
  ;; ruta completa que se le enseña si no está. La guardada puede ser relativa a la
  ;; carpeta de este dibujo, o estar sólo por su nombre.
  ;; `cond` y no `or`: en AutoLISP `or` devuelve T, no la ruta (3.9.9: «stringp T»).
  (setq prefijo (getvar "DWGPREFIX")
        encontrada (cond ((findfile ruta))
                         ((findfile (strcat prefijo ruta)))
                         ((findfile (strcat prefijo (am:fichero-de-xref ruta))))))
  (list encontrada
        (if (or (wcmatch ruta "?:*") (wcmatch ruta "\\\\*")) ruta (strcat prefijo ruta))))

(defun am:abrir-dibujo (ruta / docs doc abierto)
  ;; Abre `ruta` en AutoCAD **sin cerrar el dibujo actual** (Pablo, 2026-09-17). Si ya
  ;; está abierto, lo pone delante. No cambia ninguna variable (`C-16`).
  (setq docs (vla-get-Documents (vlax-get-acad-object)) abierto nil)
  (vlax-for d docs
    (if (= (strcase (vla-get-FullName d)) (strcase ruta)) (setq abierto d)))
  (setq doc (if abierto
              abierto
              (vl-catch-all-apply
                '(lambda () (vla-Open (vla-get-Documents (vlax-get-acad-object)) ruta :vlax-false)))))
  (if (vl-catch-all-error-p doc)
    (progn
      (princ (strcat "\nNo he podido abrir «" (am:fichero-de-xref ruta) "»: "
                     (vl-catch-all-error-message doc)))
      (am:log "C-15: no se ha podido abrir el dibujo referenciado"))
    (progn
      (vl-catch-all-apply 'vla-Activate (list doc))
      (princ "\nAbierto. Escribe ARCHMUSE allí.")
      (am:log "C-15: abierto el dibujo referenciado"))))

(defun am:xrefs-sin-cargar ( / res)
  ;; Las xref que AutoCAD no ha podido cargar, `((fichero ruta) ...)`: de ésas no se
  ;; puede saber qué tienen.
  (setq res nil)
  (foreach x (am:xrefs)
    (if (not (caddr x)) (setq res (cons (list (cadr x) (nth 3 x)) res))))
  (reverse res))

(defun am:polilineas-en-capa (capa / ss)
  ;; Las del propio dibujo, con la misma selección que `am:recolectar`.
  (setq ss (ssget "_X" (list '(0 . "LWPOLYLINE") (cons 8 capa))))
  (if ss (sslength ss) 0))

(defun am:recintos-en-xref-p (capa / en-xref propios x fichero ruta respuesta n)
  ;; `C-15`. Si los recintos de `capa` están, todos o en parte, en una xref
  ;; cargada, lo dice y devuelve T: el comando se para sin ofrecer otra capa y sin
  ;; dibujar nada, conteste lo que conteste.
  ;;
  ;; **En lenguaje de arquitecto** (Pablo, 2026-09-17): hasta la 3.9.8 decía «NO MIDO
  ;; ESTE DIBUJO», «referencia externa», «677 polilínea(s)» y «No te ofrezco medir otra
  ;; capa». Ahora dice dónde están las habitaciones y ofrece abrir ese dibujo. El
  ;; detalle técnico (cuántas polilíneas, en la referencia y en el dibujo) va sólo al
  ;; registro, con cifras y sin nombres. Con varias referencias con habitaciones, las
  ;; nombra y no ofrece abrir ninguna.
  (setq en-xref (am:xrefs-con-recintos capa))
  (if (null en-xref)
    nil
    (progn
      (setq propios (am:polilineas-en-capa capa) n 0)
      (foreach x en-xref (setq n (+ n (cadr x))))
      (am:log (strcat "C-15: habitaciones en " (itoa (length en-xref)) " referencia(s); " (itoa n) " polilineas en ellas y " (itoa propios) " en el dibujo"))
      (if (> (length en-xref) 1)
        (progn
          (princ "\nArchMuse no puede medir este plano: las habitaciones están dibujadas en varios dibujos:")
          (foreach x en-xref (princ (strcat "\n  · " (car x))))
          (princ "\nÁbrelos uno a uno y escribe ARCHMUSE en cada uno."))
        (progn
          (setq x (car en-xref) fichero (car x))
          (princ (strcat "\nArchMuse no puede medir este plano: las habitaciones están dibujadas en «"
                         fichero "»."))
          (initget "Si No")
          (setq respuesta (getkword (strcat "\n¿Abro «" fichero "»? [Si/No] <Si>: ")))
          (if (/= respuesta "No")
            (progn
              (setq ruta (am:ruta-de-xref (nth 3 x)))
              (if (car ruta)
                (am:abrir-dibujo (car ruta))
                (progn
                  (princ (strcat "\nNo encuentro «" fichero "». Debería estar en: " (cadr ruta)))
                  (am:log "C-15: el dibujo referenciado no se encuentra"))))
            (princ "\nDe acuerdo: no dibujo nada."))))
      T)))

(defun am:avisar-xrefs-sin-cargar ( / sin-cargar)
  ;; `C-15`, la parte que NO para. Xrefs sin cargar y ningún recinto en la capa
  ;; por defecto: pueden estar ahí, pero no se puede saber. Se avisa y se sigue.
  ;; En lenguaje de arquitecto y con la ruta completa de lo que no encuentra (Pablo,
  ;; 2026-09-17): medido en Core Console, un dibujo referenciado que no está en su
  ;; sitio no se carga, y ésta es la única forma de decírselo.
  (setq sin-cargar (am:xrefs-sin-cargar))
  (if (and sin-cargar (= 0 (am:polilineas-en-capa *am:capa-por-defecto*)))
    (progn
      (princ "\n\nAVISO — No encuentro estos dibujos que usa el plano:")
      (foreach f sin-cargar
        (princ (strcat "\n  · «" (car f) "», que debería estar en: " (cadr (am:ruta-de-xref (cadr f))))))
      (princ "\n  Si las habitaciones están dibujadas en uno de ellos, ábrelo y escribe ARCHMUSE allí.")
      (princ "\n  Si están en este plano, sigue.")
      T)
    nil))


;;; ---------------------------------------------------------------------------
;;; QUÉ CAPA SE MIDE, Y QUIÉN LO DECIDE
;;; ---------------------------------------------------------------------------
;;; Hasta el 2026-09-11 esto pedía **el nombre de la capa escrito a mano** y no
;;; comprobaba nada: lo que él tecleara se mandaba tal cual al `ssget`, y una
;;; errata o una tilde de más no se veía aquí — se veía tres pasos después,
;;; como «no hay ninguna polilínea en la capa «00 áreas»», que parece un
;;; problema del plano y es un problema de la respuesta.
;;;
;;; Ahora se enseña la lista numerada SIEMPRE y se admiten las dos formas, el
;;; número y el nombre, **y nada más**: lo que no esté en la lista se rechaza en
;;; el sitio donde se escribió. Es la diferencia entre preguntar y obedecer.
;;;
;;; **El número gana sobre el nombre sólo si el nombre no casa.** Si hay una
;;; capa que de verdad se llama «3», teclear 3 elige esa capa, no la tercera de
;;; la lista: el nombre es lo que él ve en su AutoCAD.
;;;
;;; **Lo que este chooser NO es: el heurístico del servidor.** `ssget "_X"` sólo
;;; ve el primer nivel del modelspace, así que aquí se ordena por número de
;;; polilíneas y nada más. El servidor puntúa además por tamaño de estancia y
;;; por rótulos dentro (`parser.capas_candidatas`) y **entra en los bloques**.
;;; Sobre `plantasimple.dxf` la diferencia es visible: el servidor ve 9 capas
;;; candidatas y el comando ve 2. Duplicar aquí esa puntuación sería una segunda
;;; implementación de un criterio profesional, que es lo que prohíbe `D-7`.
;;;
;;; **Divergencia declarada (`C-9`), sin arreglar en esta tarea:** un plano que
;;; dibuje sus recintos DENTRO de un bloque lo mide la vía web y no lo mide el
;;; comando, porque `ssget "_X"` no baja a las referencias de bloque. En los
;;; cinco planos disponibles no pasa —los recintos están siempre en el
;;; modelspace—, pero es un hueco real entre las dos vías, no una suposición.
;;;
;;; **Las referencias externas son otro problema, no éste** (`C-15`, arriba). En
;;; un bloque la geometría está en este fichero y el servidor la ve; en una xref
;;; está en otro fichero y no la ve ninguna de las dos vías.

(defun am:elegir-capa ( / capas por-defecto intentos respuesta elegida i par)
  (setq capas (am:ordena-capas (am:capas-con-recintos)))
  (if (null capas)
    (progn
      (princ "\nArchMuse: este dibujo no tiene ni una polilínea, así que no hay")
      (princ "\nrecintos que medir. ¿Es el plano que querías abrir?")
      nil)
    (progn
      (setq por-defecto (am:capa-por-nombre *am:capa-por-defecto* capas))

      (princ "\nCapas con polilíneas en este dibujo, de más a menos:")
      (setq i 1)
      (foreach par capas
        (princ (strcat "\n  " (itoa i) ") " (car par)
                       "   (" (am:describe-capa par) ")"
                       (if (= (car par) por-defecto) "   <- la que ArchMuse propone" "")))
        (setq i (1+ i)))

      (if (null por-defecto)
        (progn
          (princ "\nNinguna se llama como la capa de áreas que ArchMuse conoce")
          (princ (strcat " («" *am:capa-por-defecto* "»),"))
          (princ "\nasí que no la doy por sabida: dime cuál es la de los recintos.")))

      ;; Tres intentos y no más. Un bucle sin salida delante de alguien que no
      ;; sabe qué contestar es peor que rendirse diciendo por qué.
      (setq intentos 3 elegida nil)
      (while (and (null elegida) (> intentos 0))
        (setq respuesta
          (getstring T
            (if por-defecto
              (strcat "\nNúmero o nombre de la capa de recintos <" por-defecto ">: ")
              "\nNúmero o nombre de la capa de recintos (INTRO para dejarlo): ")))
        (if (= respuesta "")
          (setq elegida por-defecto intentos 0)
          (progn
            (setq elegida (am:capa-por-nombre respuesta capas))
            (if (null elegida) (setq elegida (am:capa-por-numero respuesta capas)))
            (if (null elegida)
              (progn
                (setq intentos (1- intentos))
                (princ (strcat "\n«" respuesta "» no es ninguna de las de arriba."))
                (if (> intentos 0)
                  (princ "\n  Escribe su número, o el nombre tal y como aparece en la lista.")
                  (princ "\n  Lo dejo aquí, sin tocar tu plano.")))))))

      ;; **Quién eligió la capa viaja con la elección.** Una capa que él ha
      ;; nombrado es un dato declarado; una que sale de que se llamaba como
      ;; esperábamos es una suposición nuestra, y las dos no valen lo mismo
      ;; cuando luego hay que explicar de dónde salió una cifra. El servidor
      ;; hace la misma distinción (`PlanoLeido.capa_elegida_por_heuristico`).
      (if elegida
        (progn
          (setq *am:capa-la-dijo-el-usuario* (/= respuesta ""))
          (setq *am:capa-elegida* elegida)
          (princ (strcat "\nMido «" elegida "»"
                         (if *am:capa-la-dijo-el-usuario*
                           ", que me has dicho tú."
                           ", que es la que ArchMuse proponía.")))))
      elegida)))


(defun am:con-alineado (cuerpo / p)
  ;; El mismo cuerpo, con `"alinear_rotulos": true` metido delante. Se inserta
  ;; tras la primera llave en vez de rehacer el JSON: volver a recorrer el
  ;; dibujo costaria otro `ssget` de todo y, sobre todo, mandaria una geometria
  ;; distinta de la que el servidor acaba de medir. La segunda medicion tiene
  ;; que ser la MISMA planta con una instruccion mas, no otra lectura.
  (strcat "{\"alinear_rotulos\":true," (substr cuerpo 2)))


(defun am:cuadros-json (cuadros / res primero celdas n)
  ;; Los N cuadros del plano: `[{"celdas":[...]}, ...]`, y cuantas celdas van.
  ;;
  ;; Se mandan TODOS. Hasta el 2026-09-12 se mandaba uno y los demas no existian
  ;; para el servidor; con 25 cuadros en el plano eso es no entregar 24.
  (setq res "[" primero T n 0)
  (foreach tabla cuadros
    (setq celdas (am:celdas-json tabla))
    (setq n (+ n (am:cuenta-celdas celdas)))
    (if (not primero) (setq res (strcat res ",")))
    (setq res (strcat res "{\"celdas\":" celdas "}"))
    (setq primero nil))
  (setq *am:celdas-enviadas* n)
  (strcat res "]"))

(defun am:en-cuatros (lista / res)
  ;; `(x0 y0 x1 y1 x0 y0 …)` -> `((x0 y0 x1 y1) …)`.
  (setq res nil)
  (while (and lista (nth 3 lista))
    (setq res   (cons (list (nth 0 lista) (nth 1 lista) (nth 2 lista) (nth 3 lista)) res)
          lista (cdr (cdr (cdr (cdr lista))))))
  (reverse res))

(defun am:en-la-lista-p (texto lista / res)
  ;; ¿Está `texto` en `lista`, sin mirar mayúsculas?
  (setq res nil)
  (foreach elemento lista
    (if (= (strcase elemento) (strcase texto)) (setq res T)))
  res)

(defun am:caja-corta-zona-p (datos zonas / x0 x1 y0 y1 res)
  ;; ¿La caja de los vértices (código 10) de `datos` corta alguna zona? La misma
  ;; prueba que `vivienda_en_punto.corta_alguna_zona` en el servidor.
  (setq x0 nil res nil)
  (foreach par datos
    (if (= 10 (car par))
      (if x0
        (progn
          (if (< (cadr par) x0) (setq x0 (cadr par)))
          (if (> (cadr par) x1) (setq x1 (cadr par)))
          (if (< (caddr par) y0) (setq y0 (caddr par)))
          (if (> (caddr par) y1) (setq y1 (caddr par))))
        (setq x0 (cadr par) x1 (cadr par) y0 (caddr par) y1 (caddr par)))))
  (if x0
    (foreach z zonas
      (if (and (<= x0 (nth 2 z)) (>= x1 (nth 0 z)) (<= y0 (nth 3 z)) (>= y1 (nth 1 z)))
        (setq res T))))
  res)

(defun am:caja-de-datos (datos / tipo x0 y0 x1 y1 c r h largo)
  ;; `(x0 y0 x1 y1)` aproximada de una entidad con sus códigos del DXF, o nil.
  ;; Sólo para no dibujar la tabla encima (2026-09-15): no mide nada.
  (setq tipo (cdr (assoc 0 datos)) x0 nil)
  (cond
    ((member tipo '("CIRCLE" "ARC"))
      (setq c (cdr (assoc 10 datos)) r (cdr (assoc 40 datos)))
      (if (and c r) (list (- (car c) r) (- (cadr c) r) (+ (car c) r) (+ (cadr c) r))))
    ((member tipo '("TEXT" "MTEXT"))
      (setq c (cdr (assoc 10 datos)) h (cdr (assoc 40 datos))
            largo (if (= (type (cdr (assoc 1 datos))) 'STR) (strlen (cdr (assoc 1 datos))) 1))
      (if (and c (numberp h))
        (list (car c) (- (cadr c) h) (+ (car c) (* 0.8 h (max largo 1))) (+ (cadr c) h))))
    (T
      (foreach par datos
        (if (and (member (car par) '(10 11 12 13 14)) (listp (cdr par)) (numberp (cadr par)))
          (if x0
            (progn
              (if (< (cadr par) x0) (setq x0 (cadr par)))
              (if (> (cadr par) x1) (setq x1 (cadr par)))
              (if (< (caddr par) y0) (setq y0 (caddr par)))
              (if (> (caddr par) y1) (setq y1 (caddr par))))
            (setq x0 (cadr par) x1 (cadr par) y0 (caddr par) y1 (caddr par)))))
      (if x0 (list x0 y0 x1 y1)))))

(defun am:caja-de-insert (ename datos / obj caja)
  ;; La extensión real de un bloque la sabe AutoCAD; si no la da, su punto.
  (setq obj (vl-catch-all-apply 'vlax-ename->vla-object (list ename)))
  (setq caja (if (vl-catch-all-error-p obj) nil (am:caja-de obj)))
  (if caja
    (list (car (car caja)) (cadr (car caja)) (car (cadr caja)) (cadr (cadr caja)))
    (am:caja-de-datos (list (assoc 0 '((0 . "POINT"))) (assoc 10 datos)))))

(defun am:mas-caja (json caja)
  (strcat json (if (= json "") "" ",")
          "[" (am:json-num (nth 0 caja)) "," (am:json-num (nth 1 caja)) ","
          (am:json-num (nth 2 caja)) "," (am:json-num (nth 3 caja)) "]"))

(defun am:capa-visible-p (capa / fila)
  ;; ¿Se ve lo que hay en `capa`? No, si está apagada (color negativo) o inutilizada
  ;; (bit 1 de 70). Una capa que no está en la tabla se da por visible.
  (setq fila (if capa (tblsearch "LAYER" capa)))
  (or (null fila)
      (not (or (minusp (cdr (assoc 62 fila)))
               (= 1 (logand 1 (cdr (assoc 70 fila))))))))

(defun am:dentro-de-zona-p (p zona)
  (and (>= (car p) (nth 0 zona)) (<= (car p) (nth 2 zona))
       (>= (cadr p) (nth 1 zona)) (<= (cadr p) (nth 3 zona))))

(defun am:polilinea-cruza-zona-p (datos zona / puntos a b esquinas res i)
  ;; ¿Pasa alguna línea de la polilínea por debajo de `zona`? Un vértice dentro, o un
  ;; tramo que corta uno de sus cuatro lados (3.9.7). Hasta la 3.9.6 bastaba con que la
  ;; CAJA de la polilínea cortara la zona: el marco que rodea todas las plantas «quedaba
  ;; tapado» con la tabla en un hueco de dentro. Los tramos con arco se miran por su
  ;; cuerda: un arco que entra sin que su cuerda entre no se cuenta.
  (setq puntos nil)
  (foreach par datos
    (if (= 10 (car par)) (setq puntos (cons (list (cadr par) (caddr par)) puntos))))
  (setq puntos (reverse puntos))
  (if (and puntos (= 1 (logand 1 (cdr (assoc 70 datos)))))
    (setq puntos (append puntos (list (car puntos)))))
  (setq esquinas (list (list (nth 0 zona) (nth 1 zona)) (list (nth 2 zona) (nth 1 zona))
                       (list (nth 2 zona) (nth 3 zona)) (list (nth 0 zona) (nth 3 zona))
                       (list (nth 0 zona) (nth 1 zona)))
        res nil)
  (foreach p puntos
    (if (am:dentro-de-zona-p p zona) (setq res T)))
  (setq a (car puntos) puntos (cdr puntos))
  (while (and (not res) puntos)
    (setq b (car puntos) i 0)
    (while (and (not res) (< i 4))
      (if (inters a b (nth i esquinas) (nth (1+ i) esquinas) T) (setq res T))
      (setq i (1+ i)))
    (setq a b puntos (cdr puntos)))
  res)

(defun am:obstaculos (zona propios / zonas ss i ename datos caja res n)
  ;; **Lo que hay dibujado bajo la tabla** (3.9.4). Cajas `[x0,y0,x1,y1]` en JSON de
  ;; lo que corta `zona` —`(x0 y0 x1 y1)`, la huella de la tabla donde se ha hecho
  ;; el segundo clic—. Sólo sirve para avisar de lo que tapa: la tabla no se mueve
  ;; (dos clics, Pablo, 2026-09-16). Aquí se leen coordenadas. `propios` es lo que
  ;; acaba de dibujar el comando (3.9.6): la tabla no se tapa a sí misma.
  ;;
  ;; Dos pasadas: todas las LWPOLYLINE mirando su caja (0,44 s en un maestro de
  ;; 9.220), y el resto preseleccionado por su punto de inserción dentro de la
  ;; zona. **Lo que no ve:** una línea larga que cruza la zona con los dos
  ;; extremos fuera, y los sombreados. Sin ejecutar en la interfaz de AutoCAD.
  (setq res "" n 0)
  (if (and zona (= (length zona) 4))
    (progn
      (setq zonas (list zona)
            ss    (ssget "_X" '((0 . "LWPOLYLINE") (410 . "Model")))
            i     0)
      (if ss
        (while (< i (sslength ss))
          (setq ename (ssname ss i)
                datos (entget ename))
          (if (and (not (and propios (ssmemb ename propios)))
                   (am:caja-corta-zona-p datos zonas)
                   (am:capa-visible-p (cdr (assoc 8 datos)))
                   (am:polilinea-cruza-zona-p datos zona))
            (setq res (am:mas-caja res (am:caja-de-datos datos)) n (1+ n)))
          (setq i (1+ i))))
      (setq ss (ssget "_X" (list '(-4 . "<NOT") '(0 . "LWPOLYLINE,HATCH") '(-4 . "NOT>")
                                 '(410 . "Model")
                                 '(-4 . ">,>,*") (list 10 (nth 0 zona) (nth 1 zona) 0.0)
                                 '(-4 . "<,<,*") (list 10 (nth 2 zona) (nth 3 zona) 0.0)))
            i  0)
      (if ss
        (while (< i (sslength ss))
          (setq ename (ssname ss i)
                datos (entget ename)
                caja  (if (or (and propios (ssmemb ename propios))
                              (not (am:capa-visible-p (cdr (assoc 8 datos)))))
                        nil
                        (if (= (cdr (assoc 0 datos)) "INSERT")
                          (am:caja-de-insert ename datos)
                          (am:caja-de-datos datos))))
          (if caja (setq res (am:mas-caja res caja) n (1+ n)))
          (setq i (1+ i))))))
  (setq *am:obstaculos-enviados* n)
  (strcat "[" res "]"))

(defun am:otras-polilineas (capa zonas enteras / ss i ename datos flags cerrada json primero n)
  ;; `C-12` (firmado el 2026-09-13): la superficie construida cerrada es la
  ;; polilínea que el arquitecto ROTULA, y puede estar en otra capa que la de
  ;; recintos. Se mandan LWPOLYLINE del espacio modelo que no son de esa capa,
  ;; en crudo: capa, flag y vértices. **Sin color**: la construida no se reconoce
  ;; por color, ni como respaldo. Cuál es la rotulada lo decide el servidor
  ;; (`plantilla_cuadro.medir_construida`), no este script.
  ;;
  ;; **Sólo las que pide el servidor** (3.9.0, un clic una tabla, `C-17`
  ;; propuesto): las que cortan alguna de sus `zonas` —`((x0 y0 x1 y1) …)`, en
  ;; unidades de dibujo— y todas las de las capas `enteras`. Qué zonas son lo
  ;; decide el servidor; aquí se comparan números. Medido el 2026-09-15 en un
  ;; maestro de 9.220 polilíneas: 4,9 s mandándolas todas, 0,44 s mirando su caja.
  ;; Devuelve (json . cuántas).
  (setq ss (ssget "_X" '((0 . "LWPOLYLINE") (410 . "Model")))
        json "" primero T i 0 n 0)
  (if ss
    (while (< i (sslength ss))
      (setq ename (ssname ss i)
            datos (entget ename))
      (if (and (/= (strcase (cdr (assoc 8 datos))) (strcase capa))
               (or (am:en-la-lista-p (cdr (assoc 8 datos)) enteras)
                   (am:caja-corta-zona-p datos zonas)))
        (progn
          (setq flags (if (assoc 70 datos) (cdr (assoc 70 datos)) 0)
                cerrada (if (= 1 (logand flags 1)) "true" "false"))
          (if (not primero) (setq json (strcat json ",")))
          (setq json (strcat json
                             "{\"handle\":" (am:json-cad (cdr (assoc 5 datos)))
                             ",\"capa\":" (am:json-cad (cdr (assoc 8 datos)))
                             ",\"cerrada\":" cerrada
                             ",\"vertices\":" (am:json-vertices (am:vertices-de ename)) "}")
                primero nil
                n (1+ n))))
      (setq i (1+ i))))
  (cons json n))

(defun am:recolectar (capa cuadros / ss i ename recintos textos datos tipo txt pt
                                    primero json color cerrada flags enviadas
                                    sin-flag celdas-cuadro n-celdas)
  ;; Devuelve el cuerpo JSON, o nil si no hay nada que medir. **Sin las
  ;; polilíneas de otras capas** (3.9.0): ésas se piden después, sólo las de las
  ;; zonas que diga el servidor (`am:otras-polilineas`, `am:con-vivienda`).
  ;;
  ;; **Se mandan TODAS las polilíneas de la capa, cerradas o no, y decide el
  ;; servidor.** Antes se filtraba aquí con `(-4 . "&") (70 . 1)`, que es lo
  ;; único que `ssget` sabe hacer: mirar el bit de «cerrada» del código 70. Ese
  ;; bit está mal puesto en los planos reales —2 de 10 en `v1plantas.dxf`, y una
  ;; de ellas es el salón—, así que filtrar aquí borraba superficie antes de que
  ;; nadie pudiera recuperarla: 21,90 m² de salón que llegaban al cuadro del
  ;; arquitecto convertidos en un `0,00 m²`, con la medición aparentemente
  ;; limpia. Ahora el flag viaja en `cerrada` y quien decide es
  ;; `parser._esta_cerrada`, que además sabe recuperar la que cierra
  ;; geométricamente.
  ;;
  ;; **El color también viaja, y tampoco es cosmético.** El servidor distingue
  ;; una habitación de un contorno agrupador por si lleva color propio o el de
  ;; su capa. Sin él, el contorno de la zona exterior entra como una habitación
  ;; más y su superficie se cuenta dos veces.
  (setq ss (ssget "_X" (list '(0 . "LWPOLYLINE") (cons 8 capa))))
  (if (null ss)
    (progn (princ (strcat "\nArchMuse: no hay ninguna polilínea en la capa «" capa "»."))
           nil)
    (progn
      (setq recintos "" primero T i 0 enviadas 0 sin-flag 0)
      (while (< i (sslength ss))
        (setq ename (ssname ss i)
              datos (entget ename)
              ;; Sin código 62 la entidad va con el color de su capa (BYLAYER),
              ;; que es 256 y es justo lo que significa «esto es una habitación
              ;; normal, no un contorno dibujado aparte».
              color (if (assoc 62 datos) (cdr (assoc 62 datos)) 256)
              flags (if (assoc 70 datos) (cdr (assoc 70 datos)) 0)
              cerrada (if (= 1 (logand flags 1)) "true" "false"))
        (if (not primero) (setq recintos (strcat recintos ",")))
        (setq recintos
          (strcat recintos
                  "{\"handle\":" (am:json-cad (cdr (assoc 5 datos)))
                  ",\"capa\":"   (am:json-cad capa)
                  ",\"color\":"  (itoa color)
                  ",\"cerrada\":" cerrada
                  ",\"vertices\":" (am:json-vertices (am:vertices-de ename)) "}"))
        (setq enviadas (1+ enviadas))
        (if (= cerrada "false") (setq sin-flag (1+ sin-flag)))
        (setq primero nil i (1+ i)))

      ;; **Lo que se manda, dicho en voz alta.** Sin esto no se puede saber si
      ;; una superficie que falta se perdió aquí o allí, y esa distinción costó
      ;; una sesión entera el 2026-09-10.
      (princ (strcat "\nEnvío " (itoa enviadas) " polilínea(s) de «" capa "»"))
      (if (> sin-flag 0)
        (princ (strcat ", " (itoa sin-flag) " de ellas con el flag de cerrada "
                       "SIN poner (las recupera el servidor si cierran)")))
      (princ ".")

      ;; TODOS los textos del dibujo, sin filtrar por capa y sin emparejar. El
      ;; servidor decide de qué capas puede salir un rótulo (`_capas_de_rotulo`)
      ;; y a qué recinto va cada uno. Filtrar aquí por la capa de recintos
      ;; perdería los planos que rotulan en una capa de texto aparte, que es la
      ;; convención del propio plano de referencia del proyecto.
      (setq ss (ssget "_X" '((0 . "TEXT,MTEXT"))))
      (setq textos "" primero T i 0)
      (if ss
        (while (< i (sslength ss))
          (setq ename (ssname ss i)
                datos (entget ename)
                tipo  (cdr (assoc 0 datos))
                txt   (am:texto-de ename)
                pt    (am:punto-de-texto ename))
          ;; Un MTEXT viaja con sus códigos de formato («{\fArial|b0;Salón}»).
          ;; No se limpian aquí: el servidor lo escribe en un MTEXT y ezdxf los
          ;; quita al leerlo con `plain_text()`. Una limpieza en LISP sería otra
          ;; implementación de lo mismo, y peor.
          ;;
          ;; **El tipo viaja, y no es un dato de adorno.** El servidor
          ;; materializa un DXF con lo que llega, y su lector da prioridad al
          ;; MTEXT sobre el TEXT para desempatar dos rotulos que caigan dentro
          ;; del mismo recinto. Si aqui no se dice de que tipo es cada texto,
          ;; el servidor los escribe todos iguales y ese desempate se queda sin
          ;; dato: medido sobre `plantasimple.dxf`, 16 viviendas con superficie
          ;; por la via web contra 3 por esta. El criterio no se decide aqui --
          ;; solo se declara lo que el arquitecto tiene dibujado.
          (if (and txt (/= txt "") (car pt))
            (progn
              (if (not primero) (setq textos (strcat textos ",")))
              (setq textos
                (strcat textos
                        "{\"handle\":" (am:json-cad (cdr (assoc 5 datos)))
                        ",\"capa\":"   (am:json-cad (cdr (assoc 8 datos)))
                        ",\"texto\":"  (am:json-cad txt)
                        ",\"tipo\":"   (am:json-cad tipo)
                        ",\"x\":"      (am:json-num (car pt))
                        ",\"y\":"      (am:json-num (cadr pt))
                        ;; La altura, en crudo (código 40 de TEXT y de MTEXT).
                        ;; De ella saca el servidor la altura mínima legible de
                        ;; la tabla cuando el plano no tiene cuadro (`D-14`).
                        ",\"altura\":" (if (numberp (cdr (assoc 40 datos)))
                                         (am:json-num (cdr (assoc 40 datos)))
                                         "null")
                        ;; El estilo, en crudo (código 7; sin él es «Standard»).
                        ;; De los rótulos saca el servidor el estilo con el que
                        ;; se dibuja la tabla si el plano no tiene cuadro (3.5.0).
                        ",\"estilo\":" (am:json-cad (if (cdr (assoc 7 datos))
                                                      (cdr (assoc 7 datos))
                                                      "Standard"))
                        "}"))
              (setq primero nil)))
          (setq i (1+ i))))

      ;; Las celdas de TODOS sus cuadros. Si no hay ninguno, no es un fallo:
      ;; ArchMuse dibuja el suyo igual, con su propio formato, y lo dice.
      (setq celdas-cuadro (am:cuadros-json cuadros)
            n-celdas *am:celdas-enviadas*)
      (if cuadros
        (progn
          (princ (strcat "\nLeo " (itoa n-celdas) " celda(s) de "
                         (itoa (length cuadros)) " cuadro(s) tuyo(s)."))
          (if (= n-celdas 0)
            (progn
              (princ "\n  AVISO: no se ha podido leer ni una celda.")
              (princ "\n  Dibujare mi cuadro con MI formato, no con el tuyo."))))
        (princ "\nNo tienes ningun cuadro en el plano: dibujare el mio."))

      (setq json
        (strcat "{\"insunits\":" (itoa (getvar "INSUNITS"))
                ",\"capa_de_recintos\":" (am:json-cad capa)
                ",\"recintos\":[" recintos "]"
                ",\"textos\":[" textos "]"
                ",\"cuadros\":" celdas-cuadro "}"))
      json)))

;;; ---------------------------------------------------------------------------
;;; La petición
;;; ---------------------------------------------------------------------------

;;; ---------------------------------------------------------------------------
;;; Dónde está el servidor, y levantarlo si no está (T4 y T5 del PRD de la beta)
;;; ---------------------------------------------------------------------------
;;;
;;; **NADA DE ESTE BLOQUE SE HA EJECUTADO EN AUTOCAD TODAVÍA** (2026-09-13). Lo
;;; que tiene más riesgo de comportarse distinto de lo escrito: `_.DELAY` dentro
;;; de un comando con `CMDECHO` a 0, y `WScript.Shell` `Run` lanzando un
;;; `pythonw.exe` con espacios en la ruta.

(defun am:lee-fichero (ruta / f linea texto)
  ;; El fichero entero en una cadena, o nil. Nunca un error hacia fuera.
  (setq f (vl-catch-all-apply 'open (list ruta "r")))
  (if (or (null f) (vl-catch-all-error-p f))
    nil
    (progn
      (setq texto "")
      (while (setq linea (read-line f))
        (setq texto (strcat texto linea)))
      (close f)
      texto)))


(defun am:puerto ( / base texto p ini fin n)
  ;; El puerto de `servidor.json`, o 5000. **Se relee en cada llamada**: si el
  ;; servidor se ha levantado mientras tanto, puede haber cogido otro. El
  ;; fichero lo escribe `json.dump` de Python, con un espacio tras los dos
  ;; puntos: se saltan los espacios que haya, sean cuantos sean.
  (setq base (getenv "LOCALAPPDATA"))
  (if base
    (setq texto (am:lee-fichero (strcat base "\\ArchMuse\\servidor.json"))))
  (if texto
    (progn
      (setq p (vl-string-search "\"puerto\":" texto))
      (if p
        (progn
          (setq ini (+ p 9))
          (while (= (am:car-en texto ini) " ")
            (setq ini (1+ ini)))
          (setq fin ini)
          (while (and (< fin (strlen texto)) (wcmatch (am:car-en texto fin) "#"))
            (setq fin (1+ fin)))
          (if (> fin ini)
            (setq n (atoi (substr texto (1+ ini) (- fin ini)))))))))
  (if (and n (> n 0) (< n 65536)) n *am:puerto-por-defecto*))


(defun am:url-base ()
  ;; 127.0.0.1 y no `localhost`: el servidor escucha sólo en la loopback de
  ;; IPv4, y `localhost` puede resolverse primero a ::1.
  (strcat "http://127.0.0.1:" (itoa (am:puerto))))


(defun am:url ()
  (strcat (am:url-base) "/api/medicion-geometria?formato=lisp"))


(defun am:url-vivienda ()
  ;; La primera petición de un clic (3.9.0): de qué vivienda es.
  (strcat (am:url-base) "/api/vivienda-en-punto?formato=lisp"))


(defun am:verdadero-p (v)
  ;; Un booleano de COM: `vlax-invoke-method` puede devolverlo tal cual o
  ;; envuelto en una variante.
  (if (= (type v) 'VARIANT) (setq v (vlax-variant-value v)))
  (eq v :vlax-true))


(defun am:peticion (metodo url cuerpo recibir-ms / http estado respuesta listo
                                                  espera aviso larga)
  ;; Una petición HTTP. Devuelve:
  ;;   (estado . texto)   si el servidor ha contestado, bien o mal;
  ;;   0                  si no se puede crear el objeto HTTP (AutoCAD LT);
  ;;   una cadena         con el error, si no ha contestado nadie.
  ;; COM es la única vía: AutoLISP no tiene HTTP.
  ;;
  ;; **Asíncrona, y se espera a trozos de un segundo** (3.8.1, 2026-09-15).
  ;; Hasta la 3.8.0 `Send` bloqueaba AutoCAD hasta la respuesta: sobre un plano
  ;; de 677 recintos, más de cinco minutos con la línea de comandos parada en
  ;; «Midiendo…», y quien cree que se ha colgado pulsa Esc. Ahora, en una
  ;; petición larga, cada cinco segundos se dice que sigue midiendo.
  ;; **Sin ejecutar en AutoCAD todavía**: que la línea se repinte con el
  ;; `_.DELAY` es lo que hay que ver allí.
  (setq http (vl-catch-all-apply 'vlax-create-object (list "WinHttp.WinHttpRequest.5.1")))
  (if (or (vl-catch-all-error-p http) (null http))
    0
    (progn
      (setq larga (> recibir-ms 30000)
            respuesta
        (vl-catch-all-apply
          '(lambda ()
            (vlax-invoke-method http 'Open metodo url :vlax-true)
            (if cuerpo
              (vlax-invoke-method http 'SetRequestHeader "Content-Type"
                                  "application/json; charset=utf-8"))
            ;; Resolver, conectar, enviar, recibir. El de recibir de una
            ;; medición es de cinco minutos a propósito: seis viviendas tardan
            ;; unos doce segundos, y el valor por defecto de WinHttp (30 s)
            ;; dejaría un plano grande a medias con un error que parecería de red.
            (vlax-invoke-method http 'SetTimeouts 10000 10000 30000 recibir-ms)
            (vlax-invoke-method http 'Send (if cuerpo cuerpo ""))
            T)))
      (if (not (vl-catch-all-error-p respuesta))
        (progn
          (setq espera 0 aviso 0
                listo (vl-catch-all-apply 'vlax-invoke-method (list http 'WaitForResponse 1)))
          ;; La espera va FUERA de `vl-catch-all-apply`: un Esc durante el
          ;; `_.DELAY` tiene que llegar al *error* del comando, que dice
          ;; «Cancelado», y no convertirse aquí en «el servidor no responde».
          (while (and (not (vl-catch-all-error-p listo))
                      (not (am:verdadero-p listo))
                      (< espera (/ recibir-ms 1000)))
            (setq espera (1+ espera) aviso (1+ aviso))
            (if larga
              (progn
                (if (= aviso 5)
                  (progn
                    (princ (strcat "\n  Sigo midiendo… " (itoa espera) " s"))
                    (setq aviso 0)))
                ;; Devuelve el control a AutoCAD un instante: repinta la línea
                ;; de comandos y atiende el Esc.
                (command "_.DELAY" 1)))
            (setq listo (vl-catch-all-apply 'vlax-invoke-method
                                            (list http 'WaitForResponse 1))))
          (setq respuesta
            (cond
              ((vl-catch-all-error-p listo) listo)
              ((am:verdadero-p listo)
                (vl-catch-all-apply
                  '(lambda ()
                    (setq estado (vlax-get-property http 'Status))
                    (vlax-get-property http 'ResponseText))))
              (T
                (vl-catch-all-apply 'vlax-invoke-method (list http 'Abort))
                (strcat "el servidor no ha contestado en " (itoa espera) " s"))))))
      (vl-catch-all-apply 'vlax-release-object (list http))
      (cond
        ((vl-catch-all-error-p respuesta) (vl-catch-all-error-message respuesta))
        ((= (type respuesta) 'STR) (if estado (cons estado respuesta) respuesta))
        (T "sin respuesta")))))


(defun am:salud-responde ( / r)
  ;; `GET /api/salud`: no mide nada y contesta en cuanto Flask acepta conexiones.
  (setq r (am:peticion "GET" (strcat (am:url-base) "/api/salud") nil 2000))
  (and (listp r) (= (car r) 200) (am:pos "\"ok\"" (cdr r) 0)))


(defun am:servidor-instalado ( / base pythonw lanzador)
  ;; (pythonw . lanzador) si la beta está instalada en este ordenador, o nil.
  ;; Las rutas son las que deja `empaquetado/ArchMuse-Beta.iss`; un test
  ;; compara las dos. **`lanzar.pyw` y no `app\actual\lanzador.pyw`** (3.6.2):
  ;; la versión activa ya no es una unión de directorios, porque un proceso con
  ;; RedirectionGuard no puede atravesarla (VM limpia, 2026-09-14).
  (setq base (getenv "LOCALAPPDATA"))
  (if base
    (progn
      (setq pythonw  (strcat base "\\ArchMuse\\runtime\\pythonw.exe")
            lanzador (strcat base "\\ArchMuse\\lanzar.pyw"))
      ;; `vl-file-size` y no `findfile`: devuelve nil si el fichero no está, y
      ;; ya está en la lista de primitivas verificadas del test.
      (if (and (vl-file-size pythonw) (vl-file-size lanzador))
        (cons pythonw lanzador)
        nil))
    nil))


(defun am:lanzar-sin-ventana (orden / shell r)
  ;; `WScript.Shell` y no `startapp`: con `Run` las comillas de la orden son
  ;; exactamente las que se escriben aquí, y la ventana es 0 (ninguna).
  (setq shell (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
  (if (or (vl-catch-all-error-p shell) (null shell))
    nil
    (progn
      (setq r (vl-catch-all-apply 'vlax-invoke-method (list shell 'Run orden 0 :vlax-false)))
      (vl-catch-all-apply 'vlax-release-object (list shell))
      (not (vl-catch-all-error-p r)))))


;;; ---------------------------------------------------------------------------
;;; Actualizaciones (PRD 2026-09-15)
;;; ---------------------------------------------------------------------------
;;;
;;; El servidor comprueba el canal al arrancar la sesión, descarga la versión
;;; nueva y verifica su firma (`empaquetado/capa_b/actualizaciones.py`). Si todo
;;; cuadra, deja `%LOCALAPPDATA%\ArchMuse\actualizacion.json`. **Aquí sólo se lee
;;; ese fichero: ni una conexión**, así que sin internet AutoCAD no espera nada.
;;;
;;; Va aquí, antes de los comandos, y no al final: un test mira las variables que
;;; usa el comando desde su `defun` hasta el final del fichero.
;;;
;;; **Sin ejecutar en AutoCAD** (3.8.0): `S::STARTUP` con el paquete cargado por
;;; el autoloader, `WScript.Shell.Popup` y el valor que devuelve, `vl-bb-ref` y
;;; `vl-bb-set`. Hay que probarlo en la VM antes de publicar en «estable».

(defun am:hoy ()
  (menucmd "M=$(edtime,$(getvar,date),YYYY-MO-DD)"))

(defun am:valor-json (texto clave / p ini fin)
  ;; El valor de cadena de `"clave": "…"` en un JSON plano del servidor, o nil.
  ;; El servidor no escribe nulos en estos ficheros: un `null` haría leer aquí la
  ;; clave siguiente como valor.
  (setq p (vl-string-search (strcat "\"" clave "\"") texto))
  (if p (setq ini (vl-string-search "\"" texto (+ p (strlen clave) 2))))
  (if ini (setq fin (vl-string-search "\"" texto (1+ ini))))
  (if fin (substr texto (+ ini 2) (- fin ini 1)) nil))

(defun am:escribe-fichero (ruta texto / f)
  ;; `texto` en `ruta`, sustituyendo lo que hubiera. Ni un error hacia fuera.
  (setq f (vl-catch-all-apply 'open (list ruta "w")))
  (if (and f (not (vl-catch-all-error-p f)))
    (progn
      (vl-catch-all-apply 'write-line (list texto f))
      (vl-catch-all-apply 'close (list f))))
  (princ))

(defun am:actualizacion-pendiente-en (base / texto version)
  ;; La versión descargada y verificada que espera instalarse en `base`
  ;; (`%LOCALAPPDATA%\ArchMuse`), o nil.
  (if base (setq texto (am:lee-fichero (strcat base "\\actualizacion.json"))))
  (if texto (setq version (am:valor-json texto "version")))
  (if (and version (wcmatch version "#*.#*.#*")) version nil))

(defun am:actualizaciones-al-cargar (base / pendiente texto resultado instalada clave
                                             fichero ultimo)
  ;; **Al cargar, como mucho un aviso al día** (3.9.1; corrección de Pablo,
  ;; 2026-09-15: «el aviso sale como mucho una vez al día. Si no hay versión
  ;; nueva, no muestra nada en pantalla; solo lo deja escrito en el log»).
  ;;
  ;; Lee lo que ha dejado el servidor —`actualizacion.json` si hay versión nueva,
  ;; `comprobacion.json` con el resultado de la última comprobación— y lo compara
  ;; con lo último avisado, que vive en `aviso-de-actualizaciones.txt` con la
  ;; fecha delante. Si hoy ya se dijo lo mismo, nada. Sin red.
  (setq pendiente (am:actualizacion-pendiente-en base)
        texto     (am:lee-fichero (strcat base "\\comprobacion.json"))
        resultado (if texto (am:valor-json texto "resultado"))
        instalada (if texto (am:valor-json texto "instalada")))
  (if (null resultado) (setq resultado "sin_comprobar"))
  (if (null instalada) (setq instalada "?"))
  (setq clave   (strcat (am:hoy) " "
                        (if pendiente
                          (strcat "actualizacion " pendiente)
                          (strcat resultado " " instalada)))
        fichero (strcat base "\\aviso-de-actualizaciones.txt")
        ultimo  (am:lee-fichero fichero))
  (if (/= ultimo clave)
    (progn
      (if pendiente
        (progn
          (princ (strcat "\nHay una actualización de ArchMuse (" pendiente
                         "). Teclea ARCHMUSE-ACTUALIZAR para instalarla."))
          (am:log (strcat "actualizaciones: hay una actualizacion (" pendiente "); aviso del dia")))
        (am:log (strcat "actualizaciones: "
                        (cond
                          ((= resultado "al_dia") (strcat "al dia (" instalada ")"))
                          ((= resultado "error")
                            (strcat "no se ha podido comprobar el canal (" instalada
                                    "); el motivo esta en el registro del servidor"))
                          (T "todavia no se han comprobado")))))
      (am:escribe-fichero fichero clave)))
  (princ))

(defun am:ejecutar-y-esperar (orden / shell r)
  ;; Como `am:lanzar-sin-ventana`, pero ESPERA a que termine (`Run` con
  ;; bWaitOnReturn). Devuelve T si se ha podido lanzar y ha terminado, nil si no.
  (setq shell (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
  (if (or (vl-catch-all-error-p shell) (null shell))
    nil
    (progn
      (setq r (vl-catch-all-apply 'vlax-invoke-method (list shell 'Run orden 0 :vlax-true)))
      (vl-catch-all-apply 'vlax-release-object (list shell))
      (not (vl-catch-all-error-p r)))))


(defun am:ofrecer-actualizacion ( / instalado base resultado-busqueda lanzado texto resultado
                                    instalada version)
  ;; **ARCHMUSE-ACTUALIZAR busca en ese momento** (2026-09-16). Hasta ese día sólo
  ;; leía `actualizacion.json`, lo que dejó una búsqueda anterior del servidor, y con
  ;; la 0.3.17 publicada decía «No hay ninguna actualización descargada» (medido: la
  ;; última búsqueda había sido 22 minutos antes de publicarla).
  ;;
  ;; Ahora lanza `actualizador --comprobar` —la misma búsqueda del servidor: lista de
  ;; GitHub, descarga y firma— y ESPERA a que termine. Para no leer una búsqueda vieja,
  ;; borra antes el fichero de resultado y exige que exista después. Dice lo que ha
  ;; encontrado. Teclear el comando ya es decir que sí: si hay versión nueva, instala.
  ;; La red la usa el actualizador, no este fichero. **Sin probar en AutoCAD:** `Run`
  ;; con espera.
  (cond
    ((null (setq instalado (am:servidor-instalado)))
      (princ "\nEste ArchMuse no está instalado con el instalador: no se actualiza solo."))
    (T
      (setq base (strcat (getenv "LOCALAPPDATA") "\\ArchMuse")
            resultado-busqueda (strcat base "\\resultado-de-la-busqueda.txt"))
      (vl-file-delete resultado-busqueda)
      (princ "\nBuscando actualizaciones de ArchMuse…")
      (setq lanzado (am:ejecutar-y-esperar
                      (strcat "\"" (car instalado) "\" \"" (cdr instalado)
                              "\" actualizador --comprobar --silencioso --resultado \""
                              resultado-busqueda "\"")))
      (setq texto     (if (and lanzado (vl-file-size resultado-busqueda))
                        (am:lee-fichero (strcat base "\\comprobacion.json")))
            resultado (if texto (am:valor-json texto "resultado"))
            instalada (if texto (am:valor-json texto "instalada"))
            version   (if (= resultado "actualizacion") (am:actualizacion-pendiente-en base)))
      (cond
        (version
          (princ (strcat "\nInstalando " version ". Cuando termine, cierra y vuelve a abrir AutoCAD."))
          (am:log (strcat "actualizacion " version ": se instala"))
          (if (not (am:lanzar-sin-ventana
                     (strcat "\"" (car instalado) "\" \"" (cdr instalado)
                             "\" actualizador --instalar-pendiente")))
            (princ "\nNo he podido lanzar la instalación. Teclea ARCHMUSE-ACTUALIZAR para intentarlo otra vez.")))
        ((and (= resultado "al_dia") instalada)
          (princ (strcat "\nEstás al día (" instalada ")."))
          (am:log (strcat "actualizaciones: al dia (" instalada "), buscado desde el comando")))
        (T
          (princ "\nNo he podido comprobar si hay una versión nueva: sin conexión, o GitHub no responde.")
          (princ "\n  El motivo está en el registro de ArchMuse. Vuelve a intentarlo en un rato.")
          (am:log "actualizaciones: no se ha podido buscar desde el comando")))))
  (princ))

;; `c:ARCHMUSE-ACTUALIZAR` está al final del fichero, detrás de `c:ARCHMUSE`: un
;; test busca el primer «(defun c:ARCHMUSE» y mira desde ahí hasta el final.

;; 3.9.1: el aviso ya no cuelga del arranque de AutoCAD. Que ese enganche llegara
;; a ejecutarse con el paquete cargado por el autoloader nunca se midió, y sin
;; versión nueva no dejaba ni rastro. Se revisa al final de este fichero, al
;; cargar (`am:actualizaciones-al-cargar`).


(defun am:levantar-servidor ( / instalado i vivo punto)
  ;; **Rama C de D-1.** El servidor no responde: el comando lo levanta y espera
  ;; hasta `*am:plazo-arranque-s*` preguntando a `/api/salud` cada segundo. Sólo
  ;; si la beta está instalada; en la máquina de desarrollo no hay nada que
  ;; lanzar y se dice. Devuelve T si al final contesta.
  (setq instalado (am:servidor-instalado))
  (if (null instalado)
    nil
    (progn
      (princ (strcat "\nArchMuse no estaba en marcha. Lo pongo en marcha: puede tardar hasta "
                     (itoa *am:plazo-arranque-s*) " s"))
      (am:log "el servidor no responde: el comando lo levanta")
      (am:lanzar-sin-ventana (strcat "\"" (car instalado) "\" \"" (cdr instalado) "\""))
      (setq i 0 vivo nil punto 0)
      (while (and (not vivo) (< i *am:plazo-arranque-s*))
        (command "_.DELAY" 1000)
        (setq i (1+ i) punto (1+ punto))
        ;; Un punto cada cinco segundos: con un plazo largo, uno por segundo
        ;; llenaría la línea de comandos. Con un contador y no con `rem`, que no
        ;; está en la lista de primitivas verificadas.
        (if (= punto 5) (progn (princ ".") (setq punto 0)))
        (setq vivo (am:salud-responde)))
      (if vivo
        (progn
          (am:log (strcat "servidor levantado por el comando en " (itoa i) " s"))
          T)
        (progn
          (am:log (strcat "el servidor no se ha levantado en "
                          (itoa *am:plazo-arranque-s*) " s"))
          nil)))))


(defun am:post (cuerpo)
  (am:post-a (am:url) cuerpo))


(defun am:post-a (url cuerpo / r motivo)
  ;; POST a `url`. Devuelve el texto de la respuesta, o nil **después de decir
  ;; por qué**.
  (setq r (am:peticion "POST" url cuerpo 300000))
  ;; Nadie ha contestado: la rama C, una vez, y se vuelve a intentar.
  (if (and (= (type r) 'STR) (am:levantar-servidor))
    (setq r (am:peticion "POST" url cuerpo 300000)))
  (cond
    ((= r 0)
      ;; En AutoCAD LT `vlax-create-object` devuelve nil siempre: se dice, en
      ;; vez de salir con un error de LISP que no explica nada.
      (princ "\nArchMuse: no se ha podido crear el objeto HTTP.")
      (princ "\n  Si esto es AutoCAD LT, no hay solución: LT no permite crear objetos COM.")
      (princ "\n  Si es AutoCAD completo, revisa el antivirus o el cortafuegos.")
      nil)
    ((= (type r) 'STR)
      (princ (strcat "\nArchMuse no responde en " (am:url-base) "."))
      (if (am:servidor-instalado)
        (progn
          (princ "\n  He intentado ponerlo en marcha y no ha contestado en 20 segundos.")
          (princ "\n  Reinicia el ordenador. Si sigue igual, teclea ARCHMUSE-INFORME y mándamelo."))
        (princ "\n  ¿Está levantado el servidor? En desarrollo: doble clic en «ArchMuse» del escritorio."))
      (princ (strcat "\n  Detalle: " r))
      nil)
    ((= (car r) 404)
      ;; Un servidor anterior al comando no tiene la ruta: se dice eso, y no un
      ;; «error 404» con una página HTML detrás.
      (princ "\nTu servidor ArchMuse no conoce esta petición: es una versión anterior a este comando.")
      (princ "\n  Cierra AutoCAD y vuelve a abrirlo (o reinicia el servidor) y teclea ARCHMUSE otra vez.")
      nil)
    ((/= (car r) 200)
      (setq motivo (am:valor-tras (cdr r) "motivo" 0))
      (princ (strcat "\nArchMuse ha devuelto un error " (itoa (car r)) ":"))
      (princ (strcat "\n  " (if (and motivo (/= motivo "nil")) motivo (cdr r))))
      nil)
    (T (cdr r))))


(defun am:escala-de-dibujo ( / u)
  ;; Cuantas unidades de dibujo mide un metro, segun `$INSUNITS`.
  ;;
  ;; La marca de borrador se escribe en UNIDADES DE DIBUJO, no en metros. Un
  ;; texto de 0,25 unidades es legible en un plano dibujado en metros y es un
  ;; punto invisible en uno dibujado en milimetros, que es como viene la mitad
  ;; de los planos. Esto no es criterio: es la misma tabla de unidades que usa
  ;; `analyzer/escala.py`, aplicada aqui al tamaño del dibujo.
  (setq u (getvar "INSUNITS"))
  (cond ((= u 4) 1000.0)      ; milimetros
        ((= u 5) 100.0)       ; centimetros
        ((= u 14) 10.0)       ; decimetros
        (T 1.0)))             ; metros, o desconocido: no se escala

;;; ---------------------------------------------------------------------------
;;; El cuadro del arquitecto
;;; ---------------------------------------------------------------------------
;;;
;;; **Este comando ya no dibuja una tabla suya: rellena la del arquitecto.**
;;; Lo dijo él el 2026-09-10 y es un cambio de a quién pertenece el entregable:
;;; una tabla nueva al lado de la suya no le ahorra el trabajo, se lo cambia por
;;; comparar dos tablas y copiar de una a otra.
;;;
;;; **Lo que este fichero decide sobre el cuadro: NADA.** Lee las celdas, las
;;; manda, y escribe donde le dicen. Qué fila es «salón + cocina» y qué cifra le
;;; toca lo resuelve `analyzer/reparto_cuadro.py` en el servidor, que es donde
;;; vive el criterio profesional y donde está probado (`D-7`). Aquí sólo hay
;;; transporte.
;;;
;;; **Por qué la escritura tiene que ser desde AutoCAD y no desde Python.**
;;; Probado el 2026-09-10: `ezdxf` 1.4.4 carga un `ACAD_TABLE` como
;;; `AcadTableBlockContent` y **no expone forma de escribir en sus celdas** — se
;;; sustituyó el tag de una celda, se guardó y al reabrir estaba vacía otra vez.
;;; `vla-SetText` sobre la tabla que ya existe es una llamada de una línea. Ésta
;;; es la única pieza del flujo que AutoLISP hace mejor que el servidor.

(setq *am:titulo-del-cuadro* "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA")

;; **Lo que marca una tabla como DE ArchMuse** (2026-09-15). La que dibuja lleva
;; el mismo título que la del arquitecto, y en una segunda pasada contaba como
;; «cuadro tuyo»: su caja, sus alturas y su estilo entraban como del plano. Se
;; reconoce por dos marcas independientes que ya lleva desde la 3.3.0 —la capa y
;; el estilo de tabla, que pone el servidor (`maquetacion_cuadro.CAPA` y
;; `ESTILO_DE_TABLA`; un test las compara)— sin escribir nada nuevo en el dibujo.
(setq *am:capa-del-cuadro* "ARCHMUSE - CUADRO")
(setq *am:estilo-de-tabla-propio* "ARCHMUSE")
(setq *am:tablas-propias* 0)

(defun am:mayusculas-sin-tildes (s / i ch res)
  ;; Comparación tosca a propósito: sólo se usa para reconocer el título del
  ;; cuadro, y el criterio fino de qué es cada fila es del servidor. Convierte
  ;; las vocales acentuadas y la eñe a su letra base para que «Útil» y «UTIL»
  ;; se parezcan lo suficiente.
  (setq res "" i 0)
  (while (< i (strlen s))
    (setq ch (strcase (am:car-en s i)))
    (setq res
      (strcat res
        (cond ((member ch '("Á" "À" "Ä" "Â")) "A")
              ((member ch '("É" "È" "Ë" "Ê")) "E")
              ((member ch '("Í" "Ì" "Ï" "Î")) "I")
              ((member ch '("Ó" "Ò" "Ö" "Ô")) "O")
              ((member ch '("Ú" "Ù" "Ü" "Û")) "U")
              ((= ch "Ñ") "N")
              (T ch))))
    (setq i (1+ i)))
  res)

(defun am:texto-de-celda (tabla f c / r)
  ;; `vla-GetText` de una celda, o "" si esa celda no se puede leer. Con red
  ;; porque una tabla ajena puede traer celdas fusionadas o de tipo bloque, y
  ;; una de ésas no puede tumbar la lectura del cuadro entero.
  (setq r (vl-catch-all-apply 'vla-GetText (list tabla f c)))
  (if (or (vl-catch-all-error-p r) (null r)) "" r))

(defun am:es-el-cuadro (tabla / titulo)
  (setq titulo (am:mayusculas-sin-tildes (am:texto-de-celda tabla 0 0)))
  (/= nil (vl-string-search (am:mayusculas-sin-tildes *am:titulo-del-cuadro*) titulo)))

(defun am:cuantas-tablas ( / ss)
  ;; Cuántas `ACAD_TABLE` hay en el dibujo, sean lo que sean.
  ;;
  ;; Sirve para distinguir dos cosas que el comando confundía: **«no hay ninguna
  ;; tabla»** y **«hay tablas y ninguna es tu cuadro»**. El mensaje que las
  ;; mezclaba mandó a buscar en `V5.dxf` un cuadro dibujado con líneas sueltas
  ;; que no existe —ese plano no tiene cuadro de ninguna clase—, igual que el
  ;; mensaje de las celdas mandó a mirar `ssget` cuando el fallo era del
  ;; servidor. Un mensaje que da por supuesta la causa cuesta más que uno que
  ;; dice lo que sabe.
  (setq ss (ssget "_X" '((0 . "ACAD_TABLE"))))
  (if ss (sslength ss) 0))

(defun am:tabla-de-archmuse-p (tabla / capa estilo)
  ;; T si la tabla la dibujó ArchMuse: su capa o su estilo de tabla son los de
  ;; ArchMuse. Basta una de las dos: el arquitecto puede haberle cambiado la otra.
  ;; **Sin ejecutar en AutoCAD** (3.7.2): `vla-get-Layer` y `vla-get-StyleName`
  ;; contrastadas contra la referencia de ActiveX.
  (setq capa   (vl-catch-all-apply 'vla-get-Layer (list tabla))
        estilo (vl-catch-all-apply 'vla-get-StyleName (list tabla)))
  (or (and (= (type capa) 'STR)
           (= (strcase capa) (strcase *am:capa-del-cuadro*)))
      (and (= (type estilo) 'STR)
           (= (strcase estilo) (strcase *am:estilo-de-tabla-propio*)))))

(defun am:buscar-cuadros ( / ss i ename obj res)
  ;; TODAS las tablas que son un cuadro de superficies DEL ARQUITECTO, en orden
  ;; de dibujo.
  ;;
  ;; **Un plano real tiene varios.** `plantasimple.dxf` tiene 25, uno por
  ;; vivienda, y es el unico proyecto completo del lote; `ejemplo.dxf` tiene 6.
  ;; Hasta el 2026-09-12 este comando cogia el primero y los demas no existian.
  ;;
  ;; **Las que dibujó ArchMuse no** (2026-09-15): llevan el mismo título. Se
  ;; cuentan en `*am:tablas-propias*` para decirlo, y no se leen.
  (setq ss (ssget "_X" '((0 . "ACAD_TABLE"))))
  (setq i 0 res nil *am:tablas-propias* 0)
  (if ss
    (while (< i (sslength ss))
      (setq ename (ssname ss i)
            obj   (vlax-ename->vla-object ename))
      (if (am:es-el-cuadro obj)
        (if (am:tabla-de-archmuse-p obj)
          (setq *am:tablas-propias* (1+ *am:tablas-propias*))
          (setq res (cons obj res))))
      (setq i (1+ i))))
  (reverse res))

(defun am:celdas-json (tabla / filas cols f c res primero texto)
  ;; Las celdas del cuadro como JSON: `[[fila, columna, "texto"], ...]`.
  ;; Se mandan TODAS, también las vacías: el servidor necesita ver el hueco para
  ;; saber que esa fila está por rellenar y no ya rellena por el arquitecto.
  (setq filas (vla-get-Rows tabla)
        cols  (vla-get-Columns tabla)
        res "[" primero T f 0)
  (while (< f filas)
    (setq c 0)
    (while (< c cols)
      (setq texto (am:texto-de-celda tabla f c))
      (if (not primero) (setq res (strcat res ",")))
      (setq res (strcat res "[" (itoa f) "," (itoa c) "," (am:json-cad texto) "]"))
      (setq primero nil c (1+ c)))
    (setq f (1+ f)))
  (strcat res "]"))

(defun am:cuenta-celdas (json / i n)
  ;; Cuántas celdas lleva el JSON de `am:celdas-json`, contando sus corchetes de
  ;; apertura. Es tosco y sirve: lo único que hay que saber es si son cero.
  (setq n 0 i 1)
  (while (< i (strlen json))
    (if (= (am:car-en json i) "[") (setq n (1+ n)))
    (setq i (1+ i)))
  n)

;;; ---------------------------------------------------------------------------
;;; Lectura del reparto que devuelve el servidor
;;; ---------------------------------------------------------------------------

;;; `am:lista-de-motivos` se retiró en la 3.9.8: lo que no se ha medido llega ya en
;;; una frase del servidor (`geometria_descartada_aviso`).

;;; ---------------------------------------------------------------------------
;;; El cuadro propio de ArchMuse
;;; ---------------------------------------------------------------------------
;;;
;;; **Nunca se escribe en el cuadro del arquitecto. Nunca.** Desde el 2026-09-12
;;; ArchMuse dibuja el SUYO al lado, con sus mediciones, y el de el se queda
;;; intacto. Comparar los dos es cosa suya (PRD 2026-09-12).
;;;
;;; Lo que se dibuja lo decide entero el servidor: filas, columnas, que texto va
;;; en cada casilla y que notas van al pie, ya redactadas. Aqui no se compone ni
;;; un espacio -- componer es decidir.

(defun am:trozo (s ini fin)
  ;; El trozo de la respuesta entre dos posiciones, para no leer de otro cuadro.
  (if (and ini (> (strlen s) ini))
    (substr s (1+ ini) (if fin (- fin ini) (- (strlen s) ini)))
    ""))

(defun am:celdas-del-cuadro (s / p celdas fila columna texto)
  ;; Las casillas del cuadro a dibujar: `(fila columna texto)`.
  ;; Mismo patron que `am:reparto-celdas`: las tres claves llegan en orden.
  (setq celdas nil p (am:pos "(\"celdas\"" s 0))
  (if p
    (while (setq p (am:pos "(\"fila\" . " s p))
      (setq fila    (am:valor-tras s "fila" p)
            columna (am:valor-tras s "columna" p)
            texto   (am:valor-tras s "texto" p))
      (if (and fila columna texto)
        (setq celdas (cons (list (atoi fila) (atoi columna) texto) celdas)))
      (setq p (1+ p))))
  (reverse celdas))

;;; ---------------------------------------------------------------------------
;;; La tabla de ArchMuse: plantilla fija, un punto y medidas del servidor
;;; (PRD 2026-09-13, D-13, D-14 enmendado y C-13)
;;; ---------------------------------------------------------------------------
;;;
;;; **Ejecutado por primera vez el 2026-09-13, la 3.2.0, sobre `v1plantas.dxf`.**
;;; Dibujó, sin ceros, y la negativa por ventana pequeña funcionó. Salieron las
;;; notas encima de la tabla, filas desiguales, color heredado y «2 viviendas»
;;; donde había una: arreglado en la 3.2.1 y la 3.3.0.
;;;
;;; **Sin ejecutar todavía:** el estilo de tabla creado por ActiveX y la capa con
;;; su color (3.3.0), y el punto único con `getpoint` (3.4.0). Casillas 13 a 18
;;; del checklist.

(defun am:json-caja (caja)
  ;; `((xmin ymin) (xmax ymax))` -> `[[x,y],[x,y]]`.
  (strcat "[[" (am:json-num (car (car caja))) "," (am:json-num (cadr (car caja)))
          "],[" (am:json-num (car (cadr caja))) "," (am:json-num (cadr (cadr caja))) "]]"))


(defun am:alturas-de-cuadro (tabla / filas cols f c h res)
  ;; Las alturas de texto de TODAS sus celdas, en crudo. Cuál vale como umbral de
  ;; legibilidad lo decide el servidor (`maquetacion_cuadro.altura_minima`).
  (setq filas (vla-get-Rows tabla) cols (vla-get-Columns tabla) f 0 res nil)
  (while (< f filas)
    (setq c 0)
    (while (< c cols)
      (setq h (vl-catch-all-apply 'vla-GetCellTextHeight (list tabla f c)))
      (if (and (not (vl-catch-all-error-p h)) (numberp h) (> h 0.0))
        (setq res (cons h res)))
      (setq c (1+ c)))
    (setq f (1+ f)))
  res)


(defun am:estilos-de-cuadro (tabla / filas cols f c e res)
  ;; Los estilos de texto de TODAS sus casillas, en crudo. Cuál vale para dibujar
  ;; la tabla de ArchMuse lo decide el servidor (`maquetacion_cuadro.estilo_de_texto`).
  (setq filas (vla-get-Rows tabla) cols (vla-get-Columns tabla) f 0 res nil)
  (while (< f filas)
    (setq c 0)
    (while (< c cols)
      (setq e (vl-catch-all-apply 'vla-GetCellTextStyle (list tabla f c)))
      (if (and (not (vl-catch-all-error-p e)) (= (type e) 'STR) (/= e ""))
        (setq res (cons e res)))
      (setq c (1+ c)))
    (setq f (1+ f)))
  res)


(defun am:con-dibujo (geometria cuadros punto ambitos / cajas alturas estilos caja json)
  ;; El cuerpo de la geometría, con lo que el servidor necesita para dibujar y
  ;; las respuestas de interior/exterior. **Nada de esto se interpreta aquí**: el
  ;; punto es el que ha marcado él, las cajas y alturas se leen de sus cuadros
  ;; tal cual, y los ámbitos son sus respuestas.
  (setq cajas "" alturas "" estilos "" json "")
  (foreach tabla cuadros
    (setq caja (am:caja-de tabla))
    (if caja
      (progn
        (if (/= cajas "") (setq cajas (strcat cajas ",")))
        (setq cajas (strcat cajas (am:json-caja caja)))))
    (foreach h (am:alturas-de-cuadro tabla)
      (if (/= alturas "") (setq alturas (strcat alturas ",")))
      (setq alturas (strcat alturas (am:json-num h))))
    (foreach nombre (am:estilos-de-cuadro tabla)
      (if (/= estilos "") (setq estilos (strcat estilos ",")))
      (setq estilos (strcat estilos (am:json-cad nombre)))))
  (foreach par ambitos
    (if (/= json "") (setq json (strcat json ",")))
    (setq json (strcat json (am:json-cad (car par)) ":" (am:json-cad (cdr par)))))
  (strcat "{"
          (if punto
            (strcat "\"punto\":[" (am:json-num (car punto)) "," (am:json-num (cadr punto)) "],")
            "")
          "\"cajas_de_cuadros\":[" cajas "],"
          "\"alturas_texto_cuadro\":[" alturas "],"
          "\"estilos_de_cuadro\":[" estilos "],"
          "\"ambitos\":{" json "},"
          (substr geometria 2)))


(defun am:capas-del-dibujo ( / registro res)
  ;; Los nombres de las capas del dibujo, en JSON. El servidor mira si alguna es
  ;; de clasificación (`AM_*`) y la pide entera; aquí no se decide nada.
  (setq res "" registro (tblnext "LAYER" T))
  (while registro
    (if (/= res "") (setq res (strcat res ",")))
    (setq res      (strcat res (am:json-cad (cdr (assoc 2 registro))))
          registro (tblnext "LAYER")))
  (strcat "[" res "]"))


(defun am:con-clic (geometria punto capas enviadas otras)
  ;; El cuerpo de la primera petición: la geometría, el punto del clic y las
  ;; capas del dibujo. `otras` son las polilíneas de las capas que el servidor
  ;; haya pedido enteras, si las ha pedido.
  (strcat "{\"punto\":[" (am:json-num (car punto)) "," (am:json-num (cadr punto)) "],"
          "\"capas_del_dibujo\":" capas ","
          "\"capas_enteras_enviadas\":" (if enviadas "true" "false") ","
          "\"otras_polilineas\":[" otras "],"
          (substr geometria 2)))


(defun am:con-vivienda (geometria otras vivienda)
  ;; La geometría de la segunda petición: con las polilíneas de las zonas y la
  ;; vivienda que eligió la primera, tal como la redactó el servidor.
  (strcat "{\"otras_polilineas\":[" otras "],\"vivienda\":" vivienda ","
          (substr geometria 2)))


(defun am:elegir-por-clic (capa geometria punto / capas r enteras motivo aviso)
  ;; **Un clic, una tabla** (3.9.0; PRD 2026-09-15; `C-17`, PROPUESTO, PENDIENTE
  ;; DE FIRMA). Pregunta al servidor de qué vivienda es el clic. Devuelve su
  ;; respuesta si ha elegido una, o nil **después de decir por qué**: el
  ;; servidor redacta la duda, la distancia o `C-13`; aquí sólo se enseña.
  (setq capas (am:capas-del-dibujo))
  (princ "\nBusco qué vivienda has marcado…")
  (setq r (am:post-a (am:url-vivienda) (am:con-clic geometria punto capas nil "")))
  ;; Las capas de clasificación cambian de dónde salen los recintos: si el
  ;; servidor las pide, van enteras y se vuelve a preguntar, una vez.
  (if (and r (setq enteras (am:cadenas-tras r "pide_capas_enteras" 0)))
    (progn
      (setq motivo (am:valor-tras r "motivo" 0))
      (if motivo (princ (strcat "\n" motivo)))
      (setq r (am:post-a (am:url-vivienda)
                         (am:con-clic geometria punto capas T
                                      (car (am:otras-polilineas capa nil enteras)))))))
  (cond
    ((null r) nil)
    ((am:pos "(\"ok\" . T)" r 0)
      (setq aviso (am:valor-tras r "aviso" 0))
      (princ (strcat "\n" (if aviso aviso "El servidor ha elegido una vivienda.")))
      r)
    (T
      (setq motivo (am:valor-tras r "motivo" 0))
      (princ (strcat "\n\n" (if (and motivo (/= motivo "nil"))
                              motivo
                              "El servidor no ha elegido ninguna vivienda y no ha dicho por qué: avisa con esta línea.")))
      (am:log "C-17: no se mide por el clic")
      nil)))


(defun am:pedir-punto ( / p)
  ;; **El primer clic elige la vivienda** (3.9.4; dos clics, Pablo, 2026-09-16): la
  ;; que contiene el punto o la más cercana (`C-17` propuesto). Ya no decide dónde
  ;; va la tabla: eso es el segundo clic (`am:arrastrar-cuadro`). nil si cancela.
  (setq p (getpoint "\nHaz clic dentro de la vivienda que quieres medir: "))
  (if p (list (car p) (cadr p)) nil))


(defun am:huella-del-cuadro (m punto / ancho alto)
  ;; `(x0 y0 x1 y1)` que ocupan la tabla, sus notas y la marca con la esquina de
  ;; arriba a la izquierda en `punto`. Las medidas son las del servidor.
  (setq ancho (atof (am:valor-tras m "ancho_total" 0))
        alto  (atof (am:valor-tras m "alto_total" 0)))
  (list (car punto) (- (cadr punto) alto) (+ (car punto) ancho) (cadr punto)))


(defun am:entidades-desde (marca / ss e)
  ;; Las entidades creadas después de `marca` (lo que devolvió `entlast` antes de
  ;; dibujar; nil en un dibujo vacío), en un conjunto de selección. Es exactamente lo
  ;; que ha dibujado el comando: tabla, notas y marca de borrador.
  (setq ss (ssadd)
        e  (if marca (entnext marca) (entnext)))
  (while e
    (ssadd e ss)
    (setq e (entnext e)))
  ss)


(defun am:arrastre-libre ( / antes)
  ;; **El arrastre del segundo clic, sin ataduras** (3.9.7; Pablo con la 0.3.19, 2026-09-17):
  ;; con Orto (F8) la tabla sólo se movía en horizontal o vertical desde el primer clic, en
  ;; vez de ir pegada al cursor por su esquina. Se quitan también forzcursor (F9), las
  ;; referencias a objetos (F3, bit 16384 de OSMODE: las suspende sin perder cuáles son) y
  ;; el rastreo polar y de referencias (F10/F11, bits 8 y 16 de AUTOSNAP), que hacen saltar
  ;; el cursor. Devuelve cómo estaban, para `am:devolver-arrastre` y para *error* (`C-16`).
  (setq antes (list (cons "ORTHOMODE" (getvar "ORTHOMODE"))
                    (cons "SNAPMODE" (getvar "SNAPMODE"))
                    (cons "OSMODE" (getvar "OSMODE"))
                    (cons "AUTOSNAP" (getvar "AUTOSNAP"))))
  (setvar "ORTHOMODE" 0)
  (setvar "SNAPMODE" 0)
  (setvar "OSMODE" (logior (getvar "OSMODE") 16384))
  (setvar "AUTOSNAP" (logand (getvar "AUTOSNAP") (~ 24)))
  antes)


(defun am:devolver-arrastre (antes)
  ;; Los cuatro ajustes, como estaban antes del arrastre (`C-16`).
  (if antes
    (progn
      (setvar "ORTHOMODE" (cdr (assoc "ORTHOMODE" antes)))
      (setvar "SNAPMODE" (cdr (assoc "SNAPMODE" antes)))
      (setvar "OSMODE" (cdr (assoc "OSMODE" antes)))
      (setvar "AUTOSNAP" (cdr (assoc "AUTOSNAP" antes))))))


(defun am:arrastrar-cuadro (tabla propios nombre / base despues)
  ;; **El segundo clic, arrastrando la tabla de verdad** (3.9.6; Pablo, 2026-09-16).
  ;;
  ;; La 3.9.4 enseñaba un contorno con `grread` + `grvecs` y **no se veía** en AutoCAD
  ;; (probado por Pablo con la 0.3.17: nada hasta hacer clic). Hipótesis sin medir: el
  ;; `redraw` de cada movimiento repintaba después y lo borraba. En vez de depender de
  ;; cómo pinta AutoCAD los vectores temporales, la tabla se dibuja y se arrastra con la
  ;; orden MOVER, que enseña los objetos siguiendo al cursor con su propia vista previa.
  ;;
  ;; El punto base es la esquina de arriba a la izquierda de la tabla (su punto de
  ;; inserción). `_non` sólo en el punto base: el segundo punto se marca como en
  ;; cualquier orden de AutoCAD. Todo va dentro del grupo de deshacer del comando: un
  ;; Esc aquí llega a *error*, que cierra el grupo y deshace lo dibujado (`C-16`).
  ;;
  ;; Devuelve la esquina donde ha quedado, leída de la propia tabla, o nil si se ha
  ;; pulsado Enter sin marcar sitio: MOVER toma entonces el punto base como
  ;; desplazamiento y la tabla acabaría en el doble de sus coordenadas.
  (setq base (am:punto->lista (vla-get-InsertionPoint tabla)))
  (princ (strcat "\nVivienda " nombre " seleccionada. Mueve el cursor y haz clic donde quieres el cuadro de superficies."))
  (command "_.MOVE" propios "" "_non" base pause)
  (setq despues (am:punto->lista (vla-get-InsertionPoint tabla)))
  (if (and (not (equal (list (car base) (cadr base)) (list 0.0 0.0) 1e-9))
           (equal (car despues) (* 2.0 (car base)) 1e-6)
           (equal (cadr despues) (* 2.0 (cadr base)) 1e-6))
    nil
    (list (car despues) (cadr despues))))


(defun am:ultima-pos (patron s / p ultima)
  (setq p 0 ultima nil)
  (while (setq p (am:pos patron s p))
    (setq ultima p p (1+ p)))
  ultima)


(defun am:preguntar-ambitos (respuesta / ini bloque p familia texto r res)
  ;; Las preguntas de interior/exterior que ha decidido el SERVIDOR, una por
  ;; familia (decisión 4 de Pablo). Aquí se enseñan y se recoge la respuesta; no
  ;; se decide nada. Devuelve `((familia . "interior") ...)` con las contestadas.
  ;; La lista de arriba es la última clave de la respuesta: por eso la última.
  (setq ini (am:ultima-pos "(\"preguntas_de_ambito\"" respuesta) res nil)
  (if ini
    (progn
      (setq bloque (am:trozo respuesta ini nil) p 0)
      (while (setq p (am:pos "(\"familia\" . " bloque p))
        (setq familia (am:valor-tras bloque "familia" p)
              texto   (am:valor-tras bloque "texto" p))
        (if (and familia texto)
          (progn
            (princ (strcat "\n\n" texto))
            (initget "Interior Exterior")
            (setq r (getkword "\n[Interior/Exterior] <sin contestar>: "))
            (if r (setq res (cons (cons familia (strcase r T)) res)))))
        (setq p (1+ p)))))
  (reverse res))


(defun am:zona-de-repartos (respuesta / ini fin)
  ;; La lista `repartos` de la respuesta y nada más.
  ;;
  ;; **Por qué no se busca en toda la respuesta** (AutoCAD, 2026-09-13): el
  ;; servidor mandaba además `reparto`, una copia del primero, y contar
  ;; `cuadro_a_dibujar` en todo el texto ofreció «2 viviendas VT1/3» sobre un
  ;; plano con una. El servidor ya no la manda; esto protege también de uno
  ;; anterior que todavía la mande.
  (setq ini (am:pos "(\"repartos\"" respuesta 0))
  (if ini
    (progn
      (setq fin (am:pos "(\"reparto\" . " respuesta ini))
      (am:trozo respuesta ini fin))
    ""))


(defun am:viviendas-de (respuesta / zona p v res)
  ;; El nombre de la vivienda de cada tabla, en el orden del servidor, y SÓLO
  ;; de la lista `repartos` (ver `am:zona-de-repartos`).
  (setq zona (am:zona-de-repartos respuesta) p 0 res nil)
  (while (setq p (am:pos "(\"cuadro_a_dibujar\"" zona p))
    (setq v (am:valor-tras zona "vivienda" p))
    (setq res (cons (if v v "?") res) p (1+ p)))
  (reverse res))


(defun am:bloque-de-vivienda (respuesta n / zona p i)
  ;; El `cuadro_a_dibujar` de la vivienda n (base 0), sin leer el de otra y
  ;; sin salir de `repartos`.
  (setq zona (am:zona-de-repartos respuesta)
        p    (am:pos "(\"cuadro_a_dibujar\"" zona 0)
        i    0)
  (while (and p (< i n))
    (setq p (am:pos "(\"cuadro_a_dibujar\"" zona (1+ p)) i (1+ i)))
  (if p
    (am:trozo zona p (am:pos "(\"cuadro_a_dibujar\"" zona (1+ p)))
    nil))


(defun am:motivos-indistinguibles (respuesta / zona p m res)
  ;; `C-13`: las viviendas que el servidor NO ofrece porque hay varias con el
  ;; mismo rótulo. Su motivo viene redactado de allí y se enseña tal cual.
  (setq zona (am:zona-de-repartos respuesta) p 0 res nil)
  (while (setq p (am:pos "(\"indistinguible\" . T)" zona p))
    (if (setq m (am:valor-tras zona "motivo" p))
      (setq res (cons m res)))
    (setq p (1+ p)))
  (reverse res))


(defun am:elegir-vivienda (nombres / i n)
  ;; Con varias viviendas medidas, él elige de cuál es la tabla. Base 0, o nil.
  (if (< (length nombres) 2)
    0
    (progn
      (princ "\n\nHe medido varias viviendas. ¿De cuál dibujo el cuadro?")
      (setq i 0)
      (foreach nombre nombres
        (setq i (1+ i))
        (princ (strcat "\n  " (itoa i) ". " nombre)))
      (initget 6)
      (setq n (getint (strcat "\nNúmero (1-" (itoa (length nombres)) "): ")))
      (if (and n (<= n (length nombres))) (1- n) nil))))


(defun am:numeros-tras (s clave desde / marca p ini fin actual ch res)
  ;; La lista de números que sigue a `("clave" . (`. Sin `read`, que tiene un
  ;; tope de unos 2.300 caracteres: se recorre carácter a carácter.
  (setq marca (strcat "(\"" clave "\" . (") p (am:pos marca s desde) res nil)
  (if p
    (progn
      (setq ini (+ p (strlen marca)) fin (am:pos ")" s (+ p (strlen marca))) actual "")
      (while (and fin (< ini fin))
        (setq ch (am:car-en s ini))
        (if (= ch " ")
          (progn
            (if (/= actual "") (setq res (cons (atof actual) res)))
            (setq actual ""))
          (setq actual (strcat actual ch)))
        (setq ini (1+ ini)))
      (if (/= actual "") (setq res (cons (atof actual) res)))))
  (reverse res))


(defun am:notas-colocadas (m / p x y linea res)
  ;; `(x y linea)` de cada nota, **ya redactada y colocada por el servidor**.
  (setq res nil p (am:pos "(\"notas\"" m 0))
  (if p
    (while (setq p (am:pos "(\"x\" . " m p))
      (setq x (am:valor-tras m "x" p)
            y (am:valor-tras m "y" p)
            linea (am:valor-tras m "linea" p))
      (if (and x y linea)
        (setq res (cons (list (atof x) (atof y) linea) res)))
      (setq p (1+ p))))
  (reverse res))


(defun am:cadenas-tras (s clave desde / marca p par res)
  ;; La lista de cadenas que sigue a `("clave" . (`: `("a" "b")` -> ("a" "b").
  ;; Carácter a carácter con `am:lee-cadena`, sin `read` (tope de longitud).
  (setq marca (strcat "(\"" clave "\" . (") p (am:pos marca s desde) res nil)
  (if p
    (progn
      (setq p (+ p (strlen marca)))
      (while (= (am:car-en s p) "\"")
        (setq par (am:lee-cadena s p)
              res (cons (car par) res)
              p   (cdr par))
        (if (= (am:car-en s p) " ") (setq p (1+ p))))))
  (reverse res))


(defun am:textos-de-notas (bloque / ini fin zona p texto-nota res)
  ;; El texto de cada nota al pie de la tabla, tal como lo redactó el servidor.
  ;; Entre `notas` y `preguntas_de_ambito`: las preguntas también traen «texto».
  ;; La local no se llama `nota`: el comando usa `nota` en su propio `foreach`.
  (setq ini  (am:pos "(\"notas\" . (" bloque 0)
        fin  (if ini (am:pos "(\"preguntas_de_ambito\"" bloque ini) nil)
        zona (if ini (am:trozo bloque ini fin) "")
        p 0 res nil)
  (while (setq p (am:pos "(\"texto\" . " zona p))
    (if (setq texto-nota (am:valor-tras zona "texto" p))
      (setq res (cons texto-nota res)))
    (setq p (1+ p)))
  (reverse res))


(defun am:medir-textos (textos estilo / caja res)
  ;; **El ancho de cada texto lo mide AutoCAD** (3.5.0): con `textbox`, en el
  ;; estilo de texto del plano con el que se va a dibujar, y a altura 1. Qué se
  ;; mide lo decide el servidor (`textos_a_medir`); aquí sólo se mide.
  ;;
  ;; **Por qué** (AutoCAD, 2026-09-13): hasta la 3.4.1 el servidor medía con
  ;; `arial.ttf` y este fichero creaba un estilo con esa fuente para que lo
  ;; dibujado midiera lo mismo. Crearlo falló en `v1plantas.dxf` («Error de
  ;; automatización. Error de archivador»). Así no se depende de ninguna fuente.
  ;;
  ;; Devuelve la lista de anchos, en el orden de `textos`, o nil con el motivo en
  ;; `*am:fallo-de-la-medida*`. Un texto sin medir no se sustituye por nada.
  (setq *am:fallo-de-la-medida* nil res nil)
  (foreach texto textos
    (if (null *am:fallo-de-la-medida*)
      (progn
        (setq caja (vl-catch-all-apply
                     'textbox (list (list (cons 1 texto) (cons 7 estilo) (cons 40 1.0)))))
        (cond
          ((vl-catch-all-error-p caja)
            (setq *am:fallo-de-la-medida*
                   (strcat "al medir «" texto "» con el estilo «" estilo "»: "
                           (vl-catch-all-error-message caja))))
          ((null caja)
            (setq *am:fallo-de-la-medida*
                   (strcat "AutoCAD no ha devuelto la medida de «" texto
                           "» con el estilo «" estilo "»")))
          (T
            (setq res (cons (- (car (cadr caja)) (car (car caja))) res)))))))
  (if *am:fallo-de-la-medida* nil (reverse res)))


(defun am:json-cadenas (lista / res primero)
  (setq res "[" primero T)
  (foreach elemento lista
    (if (not primero) (setq res (strcat res ",")))
    (setq res (strcat res (am:json-cad elemento)) primero nil))
  (strcat res "]"))


(defun am:json-numeros (lista / res primero)
  (setq res "[" primero T)
  (foreach elemento lista
    (if (not primero) (setq res (strcat res ",")))
    (setq res (strcat res (am:json-num elemento)) primero nil))
  (strcat res "]"))


(defun am:json-celdas (celdas / res primero)
  ;; `((fila columna texto) …)` -> `[[fila,columna,"texto"],…]`.
  (setq res "[" primero T)
  (foreach celda celdas
    (if (not primero) (setq res (strcat res ",")))
    (setq res (strcat res "[" (itoa (car celda)) "," (itoa (cadr celda)) ","
                      (am:json-cad (caddr celda)) "]")
          primero nil))
  (strcat res "]"))


(defun am:post-maquetar (cuerpo / r)
  ;; `/api/maquetar-cuadro`. El servidor ya ha contestado a la medición, así que
  ;; aquí no se levanta nada: si falla, se dice con lo que haya contestado.
  (setq r (am:peticion "POST" (strcat (am:url-base) "/api/maquetar-cuadro?formato=lisp")
                       cuerpo 60000))
  (cond
    ((= r 0)
      (princ "\nArchMuse: no se ha podido crear el objeto HTTP para colocar la tabla.")
      nil)
    ((= (type r) 'STR)
      (princ (strcat "\nArchMuse no ha contestado al colocar la tabla: " r))
      nil)
    ((/= (car r) 200)
      (princ (strcat "\nArchMuse no ha podido colocar la tabla (error " (itoa (car r)) "):"))
      (princ (strcat "\n  " (cdr r)))
      nil)
    (T (cdr r))))


(defun am:maquetar (bloque textos anchos punto cuadros estilo obstaculos
                    / altura cajas caja)
  ;; La tabla colocada con los anchos que ha medido AutoCAD. **Aquí no se decide
  ;; nada**: se le devuelve al servidor lo que él mismo mandó —celdas, notas,
  ;; altura mínima, estilo— con las medidas y el punto, y él maqueta.
  (setq altura (am:valor-tras bloque "altura_minima" 0) cajas "")
  (foreach tabla cuadros
    (setq caja (am:caja-de tabla))
    (if caja
      (progn
        (if (/= cajas "") (setq cajas (strcat cajas ",")))
        (setq cajas (strcat cajas (am:json-caja caja))))))
  (am:post-maquetar
    (strcat "{\"estilo_texto\":" (am:json-cad estilo)
            ",\"punto\":[" (am:json-num (car punto)) "," (am:json-num (cadr punto)) "]"
            ",\"altura_minima\":" (if (or (null altura) (= altura "nil")) "null" altura)
            ",\"cajas_de_cuadros\":[" cajas "]"
            ",\"celdas\":" (am:json-celdas (am:celdas-del-cuadro bloque))
            ;; En el plano, las notas cortas que redacta el servidor (3.9.2); si es
            ;; uno anterior que no las manda, las de siempre.
            ",\"notas\":" (am:json-cadenas (if (am:pos "(\"notas_del_dibujo\"" bloque 0)
                                              (am:cadenas-tras bloque "notas_del_dibujo" 0)
                                              (am:textos-de-notas bloque)))
            ",\"textos_medidos\":" (am:json-cadenas textos)
            ",\"anchos_medidos\":" (am:json-numeros anchos)
            ",\"obstaculos\":" (if obstaculos obstaculos "[]")
            "}")))


(defun am:avisar-del-dibujo (texto)
  ;; Apunta algo que no se ha podido hacer al dibujar, una sola vez: el mismo
  ;; fallo en treinta casillas es un aviso, no treinta.
  (if (not (member texto *am:avisos-del-dibujo*))
    (setq *am:avisos-del-dibujo* (cons texto *am:avisos-del-dibujo*))))


(defun am:intentar (que funcion argumentos / r)
  ;; Una llamada que puede fallar sin que la tabla deje de dibujarse. **Si falla,
  ;; no se calla**: apunta qué no se ha podido hacer y el mensaje de AutoCAD, y
  ;; el comando lo enseña. Devuelve el resultado de la llamada, T si no devuelve
  ;; nada, o nil si ha fallado.
  (setq r (vl-catch-all-apply funcion argumentos))
  (if (vl-catch-all-error-p r)
    (progn
      (am:avisar-del-dibujo (strcat que ": " (vl-catch-all-error-message r)))
      nil)
    (if r r T)))


(defun am:estilo-de-tabla (doc nombre estilo h ht margen margen-v / dic ts r paso)
  ;; El estilo de tabla de ArchMuse: su texto, sus alturas y sus márgenes, todo
  ;; del servidor. Devuelve el nombre si lo ha encontrado o creado, o nil **con
  ;; el paso y el motivo apuntados en `*am:avisos-del-dibujo*`**.
  ;;
  ;; **Por qué existe** (AutoCAD, 2026-09-13): la tabla se creaba con el estilo
  ;; activo del plano —en `v1plantas.dxf`, `Standard` con margen vertical 1,5 y
  ;; texto 4,5, medidos en su DXF— y las filas crecían hasta decenas de veces lo
  ;; calculado: las notas acababan encima de la cabecera y las filas desiguales.
  ;;
  ;; **Sin verificar en AutoCAD:** `AddObject` con «AcDbTableStyle» y los tipos
  ;; de fila (1 datos, 2 título, 4 cabecera). Si falla, no pasa nada grave: la
  ;; tabla se dibuja con el estilo activo y los mismos márgenes y alturas puestos
  ;; en la propia tabla y en cada celda (`am:dibujar-cuadro`).
  (setq paso "abrir el diccionario de estilos de tabla")
  (setq r (vl-catch-all-apply
            '(lambda ( / )
              (setq dic (vla-Item (vla-get-Dictionaries doc) "ACAD_TABLESTYLE")
                    ts  (vl-catch-all-apply 'vla-Item (list dic nombre)))
              (if (vl-catch-all-error-p ts)
                (progn
                  (setq paso "crearlo")
                  (setq ts (vla-AddObject dic nombre "AcDbTableStyle"))))
              (setq paso "fijar sus márgenes")
              (vla-put-HorzCellMargin ts margen)
              (vla-put-VertCellMargin ts margen-v)
              (setq paso "fijar su estilo de texto")
              (vla-SetTextStyle ts 7 estilo)
              (setq paso "fijar sus alturas de texto")
              (vla-SetTextHeight ts 5 h)
              (vla-SetTextHeight ts 2 ht))))
  (if (vl-catch-all-error-p r)
    (progn
      (am:avisar-del-dibujo
        (strcat "estilo de tabla «" nombre "», al " paso ": "
                (vl-catch-all-error-message r)
                " (la tabla lleva sus medidas puestas igualmente)"))
      nil)
    nombre))


(defun am:dibujar-cuadro (m celdas / doc ms tabla estilos st capas ly x y h ht alto alto-t
                              margen margen-v anchos filas cols estilo fuente capa color
                              estilo-tabla c f mt r paso)
  ;; Dibuja la tabla **exactamente como la ha resuelto el servidor** (`D-14`):
  ;; esquina, alturas de texto y de fila (el título aparte), márgenes, ancho de
  ;; cada columna, estilos, capa y color. Devuelve la tabla, o nil si falla.
  ;;
  ;; **Aquí no hay ni una medida.** Hasta el 2026-09-13 la fila medía 1,0 y la
  ;; columna 14,0 escritas a mano y la altura de texto no se fijaba; en AutoCAD
  ;; 2027 salió un texto más alto que el edificio, partido letra a letra.
  ;;
  ;; **Y nada se hereda del plano** (3.3.0): ni el estilo de tabla activo —sus
  ;; márgenes hacían crecer las filas y ponían las notas encima—, ni el color
  ;; activo —la tabla salía amarilla—, ni la altura de las celdas vacías.
  ;;
  ;; **Y ningún fallo se calla** (3.4.1). La 3.4.0 dijo en AutoCAD «No he podido
  ;; dibujar la tabla» y nada más: este handler capturaba el error de AutoCAD y
  ;; lo tiraba. Ahora cada paso que puede tumbar la tabla se apunta en `paso`
  ;; antes de darlo, y si falla queda en `*am:fallo-del-dibujo*` como «al <paso>:
  ;; <mensaje de AutoCAD>». Lo que falla sin impedir la tabla —estilo, capa,
  ;; color, margen vertical, una casilla— va por `am:intentar` y queda en
  ;; `*am:avisos-del-dibujo*`. El comando enseña las dos cosas.
  (setq *am:fallo-del-dibujo* nil
        *am:avisos-del-dibujo* nil
        *am:dibujo-empezado* nil
        paso "leer las medidas que ha mandado el servidor")
  (setq r (vl-catch-all-apply
    '(lambda ( / )
      (setq x        (atof (am:valor-tras m "x" 0))
            y        (atof (am:valor-tras m "y" 0))
            h        (atof (am:valor-tras m "altura_texto" 0))
            ht       (atof (am:valor-tras m "altura_titulo" 0))
            alto     (atof (am:valor-tras m "alto_fila" 0))
            alto-t   (atof (am:valor-tras m "alto_fila_titulo" 0))
            margen   (atof (am:valor-tras m "margen" 0))
            margen-v (atof (am:valor-tras m "margen_vertical" 0))
            anchos   (am:numeros-tras m "anchos" 0)
            filas    (atoi (am:valor-tras m "n_filas" 0))
            cols     (atoi (am:valor-tras m "n_columnas" 0))
            estilo   (am:valor-tras m "estilo" 0)
            fuente   (am:valor-tras m "fuente" 0)
            estilo-tabla (am:valor-tras m "estilo_tabla" 0)
            capa     (am:valor-tras m "capa" 0)
            color    (atoi (am:valor-tras m "color_capa" 0)))
      (setq paso "abrir el dibujo")
      (setq doc     (vla-get-ActiveDocument (vlax-get-acad-object))
            ms      (vla-get-ModelSpace doc)
            estilos (vla-get-TextStyles doc))
      ;; **El estilo de texto es uno que YA EXISTE en su plano** —el de su cuadro
      ;; o el de sus rótulos, elegido por el servidor— y con él ha medido AutoCAD
      ;; cada texto (`am:medir-textos`). Aquí no se crea ninguno (3.5.0).
      ;;
      ;; **Lo que no se sabe, escrito aunque el arreglo lo esquive.** La 3.2.0
      ;; creó aquí un estilo «ARCHMUSE» con `arial.ttf` sobre `v1plantas.dxf` y
      ;; dibujó. La 3.4.1, con el mismo código, falló en este paso: «Error de
      ;; automatización. Error de archivador». No se sabe por qué, ni cuál de las
      ;; dos llamadas falló (crear el estilo o ponerle la fuente). Un acierto sin
      ;; explicación es una hipótesis con suerte: la 3.2.0 no probó que funcionara.
      (setq paso (strcat "encontrar en el dibujo el estilo de texto «" estilo "»"))
      (setq st (vla-Item estilos estilo))
      ;; Su capa, con su color. El color se pone sólo al crearla: si el
      ;; arquitecto ya se la ha cambiado, se respeta lo que él decidió.
      (setq paso (strcat "crear la capa «" capa "»"))
      (setq capas (vla-get-Layers doc)
            ly    (vl-catch-all-apply 'vla-Item (list capas capa)))
      (if (vl-catch-all-error-p ly)
        (progn
          (setq ly (vla-Add capas capa) *am:dibujo-empezado* T)
          (am:intentar (strcat "poner el color " (itoa color) " a la capa «" capa "»")
                       'vla-put-Color (list ly color))))
      (setq paso "crear la tabla")
      (setq tabla (vla-AddTable ms (vlax-3d-point (list x y 0.0))
                                filas cols alto (car anchos))
            *am:dibujo-empezado* T)
      (setq paso "suspender la regeneración de la tabla")
      (vla-put-RegenerateTableSuppressed tabla :vlax-true)
      (if (am:estilo-de-tabla doc estilo-tabla estilo h ht margen margen-v)
        (am:intentar (strcat "aplicar a la tabla el estilo «" estilo-tabla "»")
                     'vla-put-StyleName (list tabla estilo-tabla)))
      ;; PorCapa (256): sin esto la tabla toma el color activo del dibujo.
      (am:intentar (strcat "poner la tabla en la capa «" capa "»")
                   'vla-put-Layer (list tabla capa))
      (am:intentar "poner la tabla PorCapa (color 256)"
                   'vla-put-Color (list tabla 256))
      (setq paso "fijar el margen horizontal de las casillas")
      (vla-put-HorzCellMargin tabla margen)
      (am:intentar "fijar el margen vertical de las casillas"
                   'vla-put-VertCellMargin (list tabla margen-v))
      (setq paso "fijar el ancho de las columnas" c 0)
      (foreach ancho anchos
        (vla-SetColumnWidth tabla c ancho)
        (setq c (1+ c)))
      (setq paso "fijar el alto de las filas")
      (vla-SetRowHeight tabla 0 alto-t)
      (setq f 1)
      (while (< f filas)
        (vla-SetRowHeight tabla f alto)
        (setq f (1+ f)))
      ;; El título, a lo ancho.
      (am:intentar "fusionar la fila del título"
                   'vla-MergeCells (list tabla 0 0 0 (1- cols)))
      ;; Estilo y altura en TODAS las celdas, también las vacías: una celda vacía
      ;; conserva la altura del estilo, y con la de `Standard` (4,5) es la que
      ;; hacía crecer las filas del cuerpo.
      (setq f 0)
      (while (< f filas)
        (setq c 0)
        (while (< c cols)
          (am:intentar "poner el estilo de texto en las casillas"
                       'vla-SetCellTextStyle (list tabla f c estilo))
          (am:intentar "poner la altura de texto en las casillas"
                       'vla-SetCellTextHeight (list tabla f c (if (= f 0) ht h)))
          (setq c (1+ c)))
        (setq f (1+ f)))
      (foreach celda celdas
        (am:intentar "escribir el texto de alguna casilla (se queda vacía)"
                     'vla-SetText (list tabla (car celda) (cadr celda) (caddr celda))))
      ;; Las notas, DEBAJO y FUERA del marco (decisión 2 de Pablo), en la misma
      ;; capa y PorCapa. Ancho 0 = sin partir: las líneas ya vienen partidas por
      ;; palabras del servidor.
      (setq paso "dibujar las notas al pie")
      (foreach nota (am:notas-colocadas m)
        (setq mt (vla-AddMText ms (vlax-3d-point (list (car nota) (cadr nota) 0.0))
                               0.0 (caddr nota)))
        (vla-put-Height mt h)
        (am:intentar (strcat "poner las notas en la capa «" capa "»")
                     'vla-put-Layer (list mt capa))
        (am:intentar "poner las notas PorCapa (color 256)"
                     'vla-put-Color (list mt 256))
        (am:intentar (strcat "aplicar a las notas el estilo de texto «" estilo "»")
                     'vla-put-StyleName (list mt estilo)))
      (setq paso "regenerar la tabla")
      (vla-put-RegenerateTableSuppressed tabla :vlax-false)
      T)))
  (if (vl-catch-all-error-p r)
    (progn
      (setq *am:fallo-del-dibujo*
             (strcat "al " paso ": " (vl-catch-all-error-message r)))
      nil)
    tabla))

;;; ---------------------------------------------------------------------------
;;; Rellenar el cuadro
;;; ---------------------------------------------------------------------------

(defun am:punto->lista (v / r)
  ;; Un punto de la API ActiveX, venga como venga, a `(x y z)`.
  ;;
  ;; **No todos llegan igual, y confundirlos revienta el comando.**
  ;; `vla-get-InsertionPoint` DEVUELVE una variante que envuelve un safearray;
  ;; `vla-GetBoundingBox` no devuelve nada: ESCRIBE safearrays directamente en
  ;; los dos símbolos que se le pasan. Aplicar `vlax-variant-value` a lo segundo
  ;; da «tipo de argumento erróneo: variantp #<safearray...>», que es el error
  ;; que tumbó el comando el 2026-09-11 **después de escribir las diez celdas**.
  ;;
  ;; Se mira el tipo en vez de suponerlo, y así la misma función sirve para los
  ;; dos casos y para el siguiente que aparezca.
  (setq r (vl-catch-all-apply
            '(lambda ()
              (cond
                ((= (type v) 'variant)   (vlax-safearray->list (vlax-variant-value v)))
                ((= (type v) 'safearray) (vlax-safearray->list v))
                ((listp v)               v)
                (T nil)))))
  (if (vl-catch-all-error-p r) nil r))

(defun am:altura-del-cuadro (tabla / h)
  ;; La altura de texto con la que está escrito el cuadro, leída de una celda de
  ;; datos. **No se supone: se pregunta.**
  ;;
  ;; La marca de borrador califica a este cuadro, así que tiene que leerse a su
  ;; misma escala. Un valor fijo derivado de `$INSUNITS` no vale: el 2026-09-11,
  ;; sobre `v1plantas.dxf`, daba 0,25 cuando el cuadro está escrito a 0,125 — el
  ;; triple de alto en pantalla, y con el ancho de 60 caracteres que llevaba, un
  ;; texto que se salía por la derecha.
  (setq h (vl-catch-all-apply 'vla-GetCellTextHeight (list tabla 1 0)))
  (if (or (vl-catch-all-error-p h) (null h) (not (numberp h)) (<= h 0.0))
    nil
    h))

(defun am:caja-de (obj / minp maxp r a b)
  ;; `((xmin ymin) (xmax ymax))` de la extensión REAL del objeto, o nil.
  ;;
  ;; Hace falta porque el punto de inserción de una tabla es su esquina
  ;; **superior** izquierda, y la tabla crece hacia abajo. Escribir «debajo»
  ;; restando unas unidades a ese punto deja la marca ENCIMA del cuadro, tapando
  ;; las primeras filas — que son justo las que se acaban de rellenar. Pasó el
  ;; 2026-09-11 y tapaba tres.
  (setq r (vl-catch-all-apply 'vla-GetBoundingBox (list obj 'minp 'maxp)))
  (if (vl-catch-all-error-p r)
    nil
    (progn
      (setq a (am:punto->lista minp)
            b (am:punto->lista maxp))
      (if (and a b (cadr a) (cadr b)) (list a b) nil))))

(defun am:sitio-de-la-marca (tabla / caja h alto-fila ext)
  ;; Dónde y de qué tamaño va la marca: `(x y ancho altura)`.
  ;;
  ;; **Siempre devuelve un sitio.** Con la caja de la tabla, justo debajo de su
  ;; borde inferior y con su mismo ancho. Sin ella —una tabla que no sabe
  ;; medirse— se recurre a la esquina inferior izquierda del dibujo
  ;; (`$EXTMIN`), que es donde la pone `marca_borrador.estampar_dxf()` en la vía
  ;; web: un sitio poco elegante pero seguro, que nunca cae sobre el cuadro.
  ;;
  ;; Esa segunda salida existe porque **`C-3` no admite un «no he podido»**. Una
  ;; versión anterior dejaba el plano sin marca cuando no podía medir la tabla, y
  ;; eso es una forma de desactivarla: lo cazó su propio guardián. Entre marcar
  ;; en un sitio poco elegante y no marcar, se marca.
  (setq caja (am:caja-de tabla)
        h    (am:altura-del-cuadro tabla))

  (if caja
    (progn
      ;; Sin altura legible, la de una fila: el alto de la tabla entre sus filas,
      ;; a un 40% —lo que ocupa el texto dentro de su fila—. Estimación, y sólo
      ;; se usa cuando la buena no se puede leer.
      (setq alto-fila (/ (- (cadr (cadr caja)) (cadr (car caja)))
                         (float (max 1 (vla-get-Rows tabla)))))
      (if (null h) (setq h (* 0.4 alto-fila)))
      (list (car (car caja))                        ; el borde IZQUIERDO
            (- (cadr (car caja)) (* 2.0 h))          ; bajo el borde INFERIOR
            (- (car (cadr caja)) (car (car caja)))   ; su mismo ancho
            h))
    (progn
      (setq ext (getvar "EXTMIN"))
      (if (null h) (setq h (* 0.25 (am:escala-de-dibujo))))
      (list (car ext) (- (cadr ext) (* 4.0 h)) (* 40.0 h) h))))

(defun am:sitio-de-la-marca-del-servidor (m tabla / x)
  ;; Donde dice el servidor —debajo de las notas, `D-14`—; si no lo dice (un
  ;; servidor anterior), el sitio de siempre, debajo de la tabla.
  (setq x (if m (am:valor-tras m "marca_x" 0) nil))
  (if x
    (list (atof x)
          (atof (am:valor-tras m "marca_y" 0))
          (atof (am:valor-tras m "marca_ancho" 0))
          (atof (am:valor-tras m "altura_texto" 0)))
    (am:sitio-de-la-marca tabla)))

(defun am:marcar-borrador (tabla m / doc ms capa sitio mt r)
  ;; `C3` dentro del plano, **sin tocar ni una celda del cuadro**.
  ;; Devuelve **T si la marca ha quedado escrita, nil si no** — y esa respuesta
  ;; la mira el comando, porque un cuadro con números y sin marca es exactamente
  ;; el estado que `C-3` existe para impedir.
  ;;
  ;; Aprobado el 2026-09-10 así y no de otra forma: un MTEXT en su propia capa,
  ;; justo debajo del cuadro. El arquitecto puede apagar la capa para imprimir
  ;; sin borrar nada, y la marca se lee junto a los números que califica. Añadirle
  ;; una fila a su tabla se descartó porque le cambia la maquetación, que es
  ;; justo lo que ha pedido que no hagamos.
  ;;
  ;; Tres cosas salen de la propia tabla y ninguna es un valor fijo: **dónde**
  ;; (debajo de su borde inferior, no de su punto de inserción), **de qué
  ;; tamaño** (la altura de texto de sus celdas) y **de qué ancho** (el suyo, así
  ;; que el texto parte en líneas en vez de salirse por un lado). Las tres eran
  ;; constantes hasta el 2026-09-11 y las tres estaban mal.
  (setq r (vl-catch-all-apply
    '(lambda ( / )
      (setq doc   (vla-get-ActiveDocument (vlax-get-acad-object))
            ms    (vla-get-ModelSpace doc)
            capa  *am:capa-de-la-marca*
            sitio (am:sitio-de-la-marca-del-servidor m tabla))
      (if (vl-catch-all-error-p
            (vl-catch-all-apply 'vla-Item (list (vla-get-Layers doc) capa)))
        (vl-catch-all-apply 'vla-Add (list (vla-get-Layers doc) capa)))
      (setq mt (vla-AddMText ms (vlax-3d-point (list (car sitio) (cadr sitio) 0.0))
                             (caddr sitio) *am:leyenda-borrador*))
      (vla-put-Layer mt capa)
      (vla-put-Height mt (cadddr sitio))
      T)))
  (if (vl-catch-all-error-p r)
    (progn
      (princ (strcat "\n  (motivo: " (vl-catch-all-error-message r) ")"))
      nil)
    T))

;;; ---------------------------------------------------------------------------
;;; El comando
;;; ---------------------------------------------------------------------------

;;; ---------------------------------------------------------------------------
;;; ARCHMUSE-INFORME — EL REGISTRO, EMPAQUETADO PARA MANDARLO
;;; ---------------------------------------------------------------------------
;;; §4.4 del PRD de la beta. Lo que este comando tiene que conseguir no es
;;; comprimir un fichero: es que **el arquitecto pueda mandar lo que hace falta
;;; sin mandar su proyecto**, y que lo sepa sin fiarse de nuestra palabra. De ahí
;;; las tres decisiones que tiene dentro:
;;;
;;; 1. **Se enseña la lista exacta antes de comprimir**, con el tamaño de cada
;;;    fichero. La promesa de «sin planos dentro» tiene que ser verificable por
;;;    él, no una afirmación nuestra.
;;; 2. **El plano va en OTRO comando** (`ARCHMUSE-INFORME-PLANO`), nunca aquí y
;;;    nunca por omisión. Son dos nombres distintos y no una pregunta con
;;;    opciones, porque una pregunta se contesta mal con las prisas y un nombre
;;;    de comando hay que teclearlo entero.
;;; 3. **Siempre se dice la ruta de la carpeta.** Si el ZIP falla —política de
;;;    ejecución de PowerShell, antivirus, disco lleno—, él sigue teniendo dónde
;;;    ir a buscar los ficheros y comprimirlos a mano. Un comando de diagnóstico
;;;    que falla en silencio es peor que no tenerlo.
;;;
;;; **Por qué PowerShell y no AutoLISP.** AutoLISP no sabe comprimir. La
;;; alternativa clásica (`Shell.Application` + `CopyHere` sobre una cabecera ZIP
;;; falsificada) es asíncrona y falla en silencio; `Compress-Archive` está en
;;; todos los Windows 10 y 11 y devuelve un error cuando hay un error. Además
;;; PowerShell resuelve el escritorio **de verdad** con
;;; `[Environment]::GetFolderPath('Desktop')`, que es lo único que acierta
;;; cuando OneDrive lo ha redirigido — un `%USERPROFILE%\Desktop` escrito a mano
;;; dejaría el ZIP en una carpeta que él no ve.
;;;
;;; **Se manda el registro entero, no los últimos 30 días.** El PRD decía 30
;;; días; son líneas de texto de unos 180 caracteres y hacer aritmética de
;;; fechas en AutoLISP para recortar un fichero de unos KB es complejidad que se
;;; paga sin comprar nada. La rotación es mensual, así que el recorte natural ya
;;; existe: un fichero por mes.

(defun am:legible (bytes)
  (if (< bytes 1024)
    (strcat (itoa bytes) " B")
    (strcat (itoa (fix (/ bytes 1024.0))) " KB")))


(defun am:ficheros-de-registro ( / carpeta)
  ;; Los `.log` de la carpeta de registro, sólo nombres. `1` es «ficheros, no
  ;; directorios».
  (setq carpeta (am:carpeta-de-registro))
  (if carpeta
    (vl-directory-files carpeta "archmuse-*.log" 1)
    nil))


(defun am:escribe-entorno ( / base ruta f)
  ;; Un `entorno.txt` con lo que hace falta para interpretar el registro y NADA
  ;; que identifique el proyecto. Devuelve la ruta, o nil.
  (setq base (am:carpeta))
  (if (null base)
    nil
    (progn
      (setq ruta (strcat base "\\entorno.txt"))
      (setq f (vl-catch-all-apply 'open (list ruta "w")))
      (if (or (null f) (vl-catch-all-error-p f))
        nil
        (progn
          (write-line (strcat "fecha            " (am:ahora)) f)
          (write-line (strcat "archmuse lsp     " *am:version*) f)
          (write-line (strcat "archmuse srv     " *am:version-del-servidor*) f)
          (write-line (strcat "autocad          " (getvar "ACADVER")) f)
          (write-line (strcat "endpoint         " (am:url)) f)
          (write-line (strcat "capa por defecto " *am:capa-por-defecto*) f)
          (write-line (strcat "carpeta          " base) f)
          (close f)
          ruta)))))


(defun am:lanza-el-empaquetado (con-plano / base ps f destino sello dwg)
  ;; Escribe el .ps1 y lo lanza. Devuelve el nombre del ZIP que va a aparecer,
  ;; o nil si ni siquiera se ha podido escribir el guión.
  (setq base (am:carpeta))
  (if (null base)
    nil
    (progn
      (setq sello (menucmd "M=$(edtime,$(getvar,date),YYYY-MO-DD-HHMM)"))
      (setq destino (strcat "archmuse-informe-" sello
                            (if con-plano "-con-plano" "") ".zip"))
      (setq ps (strcat base "\\informe.ps1"))
      (setq f (vl-catch-all-apply 'open (list ps "w")))
      (if (or (null f) (vl-catch-all-error-p f))
        nil
        (progn
          (write-line "$ErrorActionPreference = 'Stop'" f)
          (write-line (strcat "$base = '" base "'") f)
          (write-line (strcat "$destino = Join-Path ([Environment]::GetFolderPath('Desktop')) '"
                              destino "'") f)
          (write-line "$tmp = Join-Path $env:TEMP ('archmuse-' + [guid]::NewGuid().ToString('N'))" f)
          (write-line "New-Item -ItemType Directory -Path $tmp | Out-Null" f)
          (write-line "Copy-Item (Join-Path $base 'registro\\archmuse-*.log') $tmp" f)
          (write-line "Copy-Item (Join-Path $base 'entorno.txt') $tmp" f)
          (if con-plano
            (progn
              (setq dwg (strcat (getvar "DWGPREFIX") (getvar "DWGNAME")))
              (write-line (strcat "Copy-Item '" dwg "' $tmp") f)))
          (write-line "Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $destino -Force" f)
          (write-line "Remove-Item $tmp -Recurse -Force" f)
          (write-line "Start-Process -FilePath explorer.exe -ArgumentList ('/select,\"' + $destino + '\"')" f)
          (close f)
          (startapp "powershell.exe"
                    (strcat "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \""
                            ps "\""))
          destino)))))


(defun am:informe (con-plano / ficheros carpeta total tam r destino)
  (setq carpeta (am:carpeta-de-registro))
  (if (null carpeta)
    (progn
      (princ "\nArchMuse no ha podido encontrar su carpeta de registro")
      (princ "\n(%LOCALAPPDATA%\\ArchMuse). Sin ella no hay informe que mandar.")
      (princ)
      (exit)))

  (setq ficheros (am:ficheros-de-registro))
  (if (null ficheros)
    (progn
      (princ "\nTodavía no hay nada registrado: ArchMuse no ha medido ningún plano")
      (princ "\nen este ordenador, o no ha podido escribir su registro.")
      (princ (strcat "\nLa carpeta es: " carpeta))
      (princ)
      (exit)))

  ;; **La lista exacta, antes de comprimir.** Es lo que hace verificable la
  ;; promesa en vez de creíble.
  (princ "\nEsto es TODO lo que voy a meter en el informe:")
  (setq total 0)
  (foreach n ficheros
    (setq tam (vl-file-size (strcat carpeta "\\" n)))
    (if (null tam) (setq tam 0))
    (setq total (+ total tam))
    (princ (strcat "\n   " n "   (" (am:legible tam) ")")))
  (princ (strcat "\n   entorno.txt   (versiones de ArchMuse y de tu AutoCAD)"))
  (if con-plano
    (princ (strcat "\n   " (getvar "DWGNAME")
                   "   <-- TU PLANO, porque has usado ARCHMUSE-INFORME-PLANO")))
  (princ (strcat "\n\nSon " (am:legible total) " de texto"
                 (if con-plano ", más tu plano." ".")))
  (princ "\nNo hay nada más: ni medidas, ni nombres de estancias, ni rutas de")
  (princ "\ncarpetas. Puedes abrir el ZIP y comprobarlo antes de mandarlo.")

  (if con-plano
    (progn
      (princ "\n\n*** ESTE INFORME INCLUYE UNA COPIA DE TU DIBUJO. ***")
      (princ "\nEs el proyecto de tu cliente. Sólo di que sí si te lo he pedido")
      (princ "\nexpresamente y sabes por qué hace falta.")))

  (initget "Si No")
  (setq r (getkword (if con-plano
                      "\n\n¿Preparo el informe CON tu plano dentro? [Si/No] <No>: "
                      "\n\n¿Preparo el informe? [Si/No] <No>: ")))
  (if (/= r "Si")
    (progn (princ "\nCancelado. No se ha creado ningún fichero.") (princ) (exit)))

  (am:escribe-entorno)
  (setq destino (am:lanza-el-empaquetado con-plano))
  (am:log (strcat "ARCHMUSE-INFORME" (if con-plano "-PLANO" "") ": "
                  (itoa (length ficheros)) " fichero(s) de registro"))

  (if (null destino)
    (progn
      (princ "\n\nNo he podido preparar el ZIP. No pasa nada: los ficheros están")
      (princ (strcat "\naquí y los puedes comprimir tú:\n   " carpeta)))
    (progn
      (princ (strcat "\n\nEn unos segundos aparecerá en tu ESCRITORIO:\n   " destino))
      (princ "\nY se abrirá la carpeta con él seleccionado. Arrástralo a WhatsApp.")
      (princ (strcat "\n\nSi no aparece, los ficheros están aquí y los puedes")
             )
      (princ (strcat "\ncomprimir tú:\n   " carpeta))))
  (princ))


(defun c:ARCHMUSE-INFORME ()
  (am:informe nil))


(defun c:ARCHMUSE-INFORME-PLANO ()
  ;; Comando aparte, y no una opción del anterior. Mandar el proyecto de un
  ;; cliente tiene que costar teclear otro nombre.
  (am:informe T))


(defun c:ARCHMUSE ( / *error* capa cuadros cuerpo respuesta celdas motivos consejo
                      sueltas descartes doc marcado tablas eco r grupo-abierto
                      trozos ini fin bloque dibujadas tabla
                      filas cols notas i n
                      punto geometria ambitos alineado nombres elegida m intentos
                      estilo-texto textos medidos eleccion otras obstaculos
                      colocado tapa detalle linea antes-de-dibujar propios arrastre-libre)

  (defun *error* (msg)
    ;; **ArchMuse nunca acaba en silencio** (Pablo, 2026-09-15). Tres casos:
    (cond
      ((null msg))
      ;; `(exit)` levanta *error* con «quit / exit abort». Es la salida ordenada
      ;; del propio comando, que ya ha dicho el motivo antes de llamarla: aquí
      ;; no se repite, y no se imprime como un fallo.
      ((wcmatch (strcase msg) "*SALIDA*,*QUIT*,*EXIT*"))
      ;; Un Esc (`*CANCEL*`, `*BREAK*`). Hasta la 3.8.0 también se callaba, y así
      ;; acabó el plano grande: tras cinco minutos esperando al servidor con la
      ;; interfaz bloqueada, el Esc de quien creía que se había colgado se
      ;; procesó al llegar la respuesta —justo después de «Servidor ArchMuse
      ;; 0.3.9 · comando 3.8.0»— y el comando terminó sin dibujar ni decir nada.
      ;; Hipótesis leída en el código, no reproducida en AutoCAD: es la única
      ;; salida muda que había (`tests/test_archmuse_nunca_acaba_en_silencio.py`).
      ((wcmatch (strcase msg) "*BREAK*,*CANCEL*")
        (princ "\nCancelado con Esc.")
        (if (not (and grupo-abierto *am:dibujo-empezado*))
          (princ " No se ha dibujado nada."))
        (am:log "cancelado con Esc"))
      (T
        (princ (strcat "\nArchMuse se ha detenido: " msg))
        ;; **El único sitio del comando que registra una traza.** Un fallo que
        ;; sólo existe en la línea de comandos se pierde en cuanto él teclea
        ;; otra cosa, y es justo el que hay que poder leer tres semanas después.
        ;; `msg` es el mensaje de AutoLISP: no lleva geometría dentro.
        (am:log (strcat "ERROR: " msg))))
    ;; **ArchMuse deja AutoCAD como lo encontró, pase lo que pase** (`C-16`,
    ;; 2026-09-15). Un Esc o un error sin capturar mientras dibujaba llegaba
    ;; aquí con el grupo de deshacer ABIERTO —el siguiente UNDO del arquitecto
    ;; se comportaba raro— y con la tabla a medias y sin marca de borrador, que
    ;; es lo que `C-3` prohíbe. Se cierra el grupo y, si llegó a dibujarse algo,
    ;; se retira. `command-s` y no `command`: dentro de *error* AutoCAD no admite
    ;; `command`. **Sin ejecutar en AutoCAD todavía**: lo comprueba el guardián
    ;; (`herramientas/guardian_autocad/`), no la suite.
    (if grupo-abierto
      (progn
        (setq grupo-abierto nil)
        (vl-catch-all-apply 'vla-EndUndoMark (list doc))
        (if *am:dibujo-empezado*
          (if (vl-catch-all-error-p (vl-catch-all-apply 'command-s (list "_.U")))
            (princ "\nY NO he podido deshacer lo que llegué a dibujar: pulsa Ctrl+Z tú.")
            (princ "\nHe deshecho lo que llegué a dibujar: tu plano está como antes.")))))
    ;; Orto, forzcursor, referencias y rastreo, si el Esc llegó en pleno arrastre (3.9.7).
    (if arrastre-libre
      (progn
        (setvar "ORTHOMODE" (cdr (assoc "ORTHOMODE" arrastre-libre)))
        (setvar "SNAPMODE" (cdr (assoc "SNAPMODE" arrastre-libre)))
        (setvar "OSMODE" (cdr (assoc "OSMODE" arrastre-libre)))
        (setvar "AUTOSNAP" (cdr (assoc "AUTOSNAP" arrastre-libre)))
        (setq arrastre-libre nil)))
    (setvar "CMDECHO" (if eco eco 1))
    (princ))

  (setq eco (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  (princ (strcat "\nArchMuse " *am:version*))

  ;; 0. **`C-15`: los recintos en una referencia externa.** Va lo primero, antes
  ;;    incluso de buscar el cuadro: en una hoja montada sobre un maestro el
  ;;    cuadro TAMBIÉN está en la xref, y «este plano no tiene ningún cuadro»
  ;;    sería otra causa falsa. Si están ahí, se dice dónde y se sale **sin
  ;;    ofrecer la lista de capas**: elegir otra ahí acaba en una cifra falsa.
  (if (am:recintos-en-xref-p *am:capa-por-defecto*)
    (progn
      (am:log "C-15: los recintos de la capa por defecto estan en una referencia externa. No se mide")
      (setvar "CMDECHO" eco) (princ) (exit)))
  ;;    Xrefs sin cargar: no se puede saber qué tienen. Se avisa y se sigue,
  ;;    decidido así por Pablo por ahora. RIESGO ABIERTO: si elige una capa
  ;;    cualquiera, puede salir una cifra falsa igual.
  (if (am:avisar-xrefs-sin-cargar)
    (am:log "C-15: referencias externas sin cargar y ningun recinto en la capa por defecto"))

  ;; 1. Los cuadros del arquitecto, si los tiene. **Ya no es un requisito.**
  ;;
  ;;    Hasta el 2026-09-12 esto era una puerta: sin cuadro el comando se
  ;;    paraba, porque lo unico que sabia hacer era rellenar el suyo. Sobre
  ;;    `V5.dxf` -- el plano que MEJOR mide de todo el lote -- eso significaba
  ;;    medir tres viviendas enteras y no entregar nada.
  ;;
  ;;    Ahora ArchMuse entrega siempre su cuadro. Si el tiene uno, se copian sus
  ;;    filas para que la comparacion sea directa; si no, se dibuja con el
  ;;    formato de ArchMuse y **se le dice que es el de ArchMuse**.
  (setq cuadros (am:buscar-cuadros))
  ;; Las tablas de pasadas anteriores se dicen y no se leen (2026-09-15).
  (if (> *am:tablas-propias* 0)
    (princ (strcat "\nHay " (itoa *am:tablas-propias*)
                   " cuadro(s) de ArchMuse de pasadas anteriores: no los leo como tuyos.")))
  (if (null cuadros)
    (progn
      ;; **Dos casos distintos, y hasta el 2026-09-11 se decían igual.** El
      ;; mensaje anterior sugería siempre que el cuadro podía estar dibujado con
      ;; líneas sueltas; en `V5.dxf` eso no era verdad —ese plano no tiene cuadro
      ;; de ninguna clase, ni tabla ni líneas— y mandaba a buscar algo que no
      ;; existe. Ahora se dice lo que se sabe y sólo lo que se sabe.
      (setq tablas (- (am:cuantas-tablas) *am:tablas-propias*))
      (if (= tablas 0)
        (progn
          (princ "\nEste plano no tiene ningun cuadro de superficies.")
          (princ "\n  No pasa nada: medire el plano y te dibujare el mio, con el")
          (princ "\n  formato de ArchMuse. Nada de lo que tienes dibujado se toca."))
        (progn
          (princ (strcat "\nHe encontrado " (itoa tablas) " tabla(s) en este dibujo, pero"))
          (princ "\nninguna parece tu cuadro de superficies.")
          (princ (strcat "\n  Busco una cuya primera celda diga «"
                         *am:titulo-del-cuadro* "»."))
          ;; Hasta la 3.9.7 seguía «Si el tuyo se titula de otra forma, dilo: copiar tus
          ;; filas es mejor que inventarlas.»: la tabla ya no copia filas de su cuadro.
          (princ "\n  Te dibujare el cuadro de ArchMuse con mi formato."))))
    (princ (strcat "\nHe encontrado " (itoa (length cuadros))
                   " cuadro(s) de superficies. No voy a tocar ninguno.")))

  (setq capa (am:elegir-capa))
  (if (null capa)
    (progn (setvar "CMDECHO" eco) (princ) (exit)))
  ;; `C-15` otra vez, con la capa que él ha elegido si no es la de por defecto:
  ;; la comprobación de arriba sólo sabía buscar ésa.
  (if (and (/= (strcase capa) (strcase *am:capa-por-defecto*))
           (am:recintos-en-xref-p capa))
    (progn
      (am:log "C-15: los recintos de la capa elegida estan en una referencia externa. No se mide")
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; **Primer clic: qué vivienda** (3.9.4; dos clics, Pablo, 2026-09-16). Dónde va
  ;; la tabla se decide después de medir, con el segundo clic (`am:colocar-cuadro`).
  (setq punto (am:pedir-punto))
  (if (null punto)
    (progn
      (princ "\nCancelado. No se ha dibujado nada.")
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; Medido el 2026-09-15 en un plano de 9.220 polilíneas y 6.280 textos: 6-8 s.
  (princ "\nLeyendo el dibujo…")
  (setq geometria (am:recolectar capa cuadros))
  (if (null geometria)
    (progn (setvar "CMDECHO" eco) (princ) (exit)))

  ;; 1b. **Un clic, una tabla** (3.9.0; PRD 2026-09-15; `C-17`, PROPUESTO,
  ;;     PENDIENTE DE FIRMA). Primero, de qué vivienda es el clic; si hay duda, el
  ;;     servidor lo dice y no se mide. Después, de las demás capas sólo viajan
  ;;     las polilíneas de las zonas que él pide: las que pueden cambiar una cifra
  ;;     de esa vivienda (`C-12`). Los recintos y los textos van enteros: de ellos
  ;;     sale qué vivienda es cada recinto, y recortarlos cambiaría las cifras.
  (setq eleccion (am:elegir-por-clic capa geometria punto))
  (if (null eleccion)
    (progn (setvar "CMDECHO" eco) (princ) (exit)))
  (setq otras (am:otras-polilineas capa (am:en-cuatros (am:numeros-tras eleccion "zonas" 0))
                                   (am:cadenas-tras eleccion "capas_enteras" 0))
        geometria (am:con-vivienda geometria (car otras)
                                   (am:valor-tras eleccion "vivienda_json" 0)))
  (princ (strcat "\nEnvío " (itoa (cdr otras)) " polilínea(s) de otras capas: las que están "
                 "cerca de un rótulo de superficie construida, que puede estar en otra capa."))
  (setq ambitos nil alineado nil
        cuerpo (am:con-dibujo geometria cuadros punto ambitos))

  (am:log (strcat "envio " (itoa *am:celdas-enviadas*) " celda(s) del cuadro"))
  (princ "\nMidiendo… (una planta de seis viviendas tarda unos segundos; si tarda más, te lo iré diciendo)")
  (setq respuesta (am:post cuerpo))
  (if (null respuesta)
    (progn
      (am:log "el servidor no ha respondido")
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; **La versión del servidor, en cuanto se sabe.** A partir de aquí cada línea
  ;; del registro la lleva; antes decía «desconocida», que era la verdad.
  (setq r (am:valor-tras respuesta "version" 0))
  (if r (setq *am:version-del-servidor* r))
  (princ (strcat "\nServidor ArchMuse " *am:version-del-servidor*
                 "  ·  comando " *am:version-corta* "."))

  ;; **D-2: el comando cargado tiene que ser el que va con este servidor, o no
  ;; se escribe.** Condición de la aprobación del PRD, no un detalle. Se compara
  ;; la versión EXACTA del `.lsp` que el servidor dice llevar consigo, no «la
  ;; parte mayor»: servidor (0.3.x) y comando (3.x) numeran por separado, y lo
  ;; que hay que cazar es actualizar con AutoCAD abierto — el `.lsp` viejo en
  ;; memoria contra el servidor nuevo, que es el caso que produce cifras que
  ;; nadie puede reproducir después. Va aquí: después de saber qué servidor es y
  ;; antes de tocar nada del dibujo.
  (setq r (am:valor-tras respuesta "lsp" 0))
  (cond
    ((null r)
      (am:log "el servidor no declara con que lsp va (servidor anterior a la beta)"))
    ((/= r *am:version-corta*)
      (princ (strcat "\n\nNO ESCRIBO NADA. El comando ArchMuse cargado en este AutoCAD es el "
                     *am:version-corta* ", y este servidor va con el " r "."))
      (princ "\n  Pasa cuando ArchMuse se actualiza con AutoCAD abierto.")
      (princ "\n  Cierra AutoCAD y vuelve a abrirlo, y teclea ARCHMUSE otra vez.")
      (am:log (strcat "versiones desparejadas: el servidor va con lsp " r ". No se escribe"))
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; 2a. Lo que el servidor ha tirado, con su motivo. Va ANTES del reparto: si
  ;;     falta superficie, esto dice si se perdió en el camino o nunca se envió.
  ;; 2a-bis. Lo que ha entrado REPARADO (`C-10`). Va antes que los descartes
  ;;     porque responde a la misma pregunta y es la menos esperada de las dos:
  ;;     que falte superficie se entiende; que ArchMuse haya tenido que arreglar
  ;;     un contorno para poder medirlo hay que decirlo en voz alta, porque el
  ;;     número sale bien y el dibujo sigue estando mal.
  (setq r (am:valor-tras respuesta "geometria_reparada_aviso" 0))
  (if r
    (progn
      (princ "\n\nAVISO — ")
      (princ r)
      (am:log "el servidor ha reparado geometria para poder medirla")))

  ;; 2a-ter. **Los rótulos desplazados, y la única pregunta que este comando
  ;;     hace sobre el dibujo del arquitecto.**
  ;;
  ;;     Va aquí, con la medición ya hecha, porque hasta que el servidor no mide
  ;;     no se sabe si hay desfase ni de cuánto. Si él dice que sí, **se vuelve a
  ;;     medir** — sí, dos veces: sólo ocurre en los planos que lo necesitan, y
  ;;     el precio de no medir dos veces sería preguntar a ciegas.
  ;;
  ;;     Tres cosas que no son negociables, y están firmadas:
  ;;     · **nunca se alinea sin que él lo diga**, ni con la detección más
  ;;       limpia del mundo — la certeza técnica no sustituye su permiso;
  ;;     · **por defecto NO**;
  ;;     · y si el desfase no es limpio, el servidor manda
  ;;       `puede_alinearse` a `nil` y aquí **no se ofrece nada**: se dice y se
  ;;       sigue. Ofrecer un desplazamiento dudoso es peor que no ofrecer.
  ;;
  ;;     Ni una de las frases se escribe aquí: vienen redactadas del servidor,
  ;;     incluido el DESPLAZA que le arreglaría el plano para siempre.
  (setq r (am:valor-tras respuesta "rotulos_desplazados_aviso" 0))
  (if r
    (progn
      (princ "\n\nAVISO — ")
      (princ r)
      (setq consejo (am:valor-tras respuesta "rotulos_desplazados_consejo" 0))
      (if consejo (progn (princ "\n  ") (princ consejo)))
      (am:log "el servidor declara rotulos desplazados")
      (if (am:pos "(\"rotulos_desplazados_puede_alinearse\" . T)" respuesta 0)
        (progn
          (initget "Si No")
          (setq r (getkword "\n¿Los alineo SÓLO para esta medición? Tu dibujo no se toca. [Si/No] <No>: "))
          (if (= r "Si")
            (progn
              (princ "\nDe acuerdo. Vuelvo a medir con los rótulos alineados…")
              (am:log "el usuario acepta alinear los rotulos")
              (setq alineado T
                    cuerpo (am:con-alineado cuerpo))
              (setq respuesta (am:post cuerpo))
              (if (null respuesta)
                (progn
                  (am:log "el servidor no ha respondido al volver a medir")
                  (setvar "CMDECHO" eco) (princ) (exit)))
              (setq r (am:valor-tras respuesta "rotulos_alineados_aviso" 0))
              (if r (progn (princ "\n") (princ r))))
            (am:log "el usuario NO alinea los rotulos")))
        (princ "\n  No te ofrezco alinearlos: el desplazamiento no es el mismo en todo el plano."))))

  ;;     Lo que no se ha medido, en una frase del servidor (3.9.8; Pablo, 2026-09-17):
  ;;     antes salía un motivo por polilínea, con detalle de programa. Al registro, sólo
  ;;     que ha pasado.
  (setq r (am:valor-tras respuesta "geometria_descartada_aviso" 0))
  (if r
    (progn
      (princ (strcat "\n\nAVISO — " r))
      (am:log "el servidor ha dejado polilineas sin medir")))

  ;; 2b. **La tabla de ArchMuse** (PRD 2026-09-13). Plantilla fija: las filas
  ;;     las pone el plano, el formato ArchMuse y el tamaño el servidor. Si no
  ;;     llega, se distingue un servidor anterior de un fallo suyo por lo que el
  ;;     propio servidor declara saber hacer.
  (if (null (am:pos "(\"cuadro_a_dibujar\"" (am:zona-de-repartos respuesta) 0))
    (progn
      (cond
        ((am:motivos-indistinguibles respuesta)
          ;; `C-13`: no es un fallo, es un criterio firmado. Varias viviendas con
          ;; el mismo rótulo no se distinguen, y no se dibuja la de ninguna.
          (princ "\n\nNo dibujo ningún cuadro:")
          (foreach r (am:motivos-indistinguibles respuesta)
            (princ (strcat "\n  " r))))
        ((null (am:pos "\"reparto_de_cuadro\"" respuesta 0))
          (princ "\n\nTu servidor ArchMuse NO SABE dibujar el cuadro: es una versión")
          (princ "\nanterior a esa función. Ha medido bien, pero no dibuja.")
          (princ "\n  Reinícialo y vuelve a teclear ARCHMUSE."))
        (T
          ;; El motivo de la tabla, leído en `repartos` y no en toda la respuesta:
          ;; allí hay cientos de «motivo» de otras cosas. Con el clic (3.9.0) puede
          ;; ser que la vivienda no sea la elegida (`C-17`).
          (setq r (am:valor-tras (am:zona-de-repartos respuesta) "motivo" 0))
          (if (and r (/= r "nil"))
            (princ (strcat "\n\nNo dibujo ningún cuadro: " r))
            (progn
              (princ "\n\nEl servidor ha medido y no ha devuelto ningún cuadro que dibujar.")
              (princ "\n  Esto es un fallo suyo, no tuyo: avisa con esta línea.")))))
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; 2c. **Interior o exterior**, si el servidor lo pregunta (decisión 4 de
  ;;     Pablo): una pregunta por familia, redactada allí. Con las respuestas se
  ;;     vuelve a medir la MISMA geometría con una instrucción más, como al
  ;;     alinear los rótulos.
  (setq ambitos (am:preguntar-ambitos respuesta))
  (if ambitos
    (progn
      (am:log (strcat "el usuario contesta " (itoa (length ambitos))
                      " pregunta(s) de interior o exterior"))
      (setq cuerpo (am:con-dibujo geometria cuadros punto ambitos))
      (if alineado (setq cuerpo (am:con-alineado cuerpo)))
      (setq respuesta (am:post cuerpo))
      (if (null respuesta)
        (progn
          (am:log "el servidor no ha respondido al volver a medir con las respuestas")
          (setvar "CMDECHO" eco) (princ) (exit)))))

  ;; 2d. **De qué vivienda**, si el plano tiene varias: él elige. Las que llevan
  ;;     el mismo rótulo que otra no se ofrecen (`C-13`), y se dice por qué: dos
  ;;     opciones con el mismo nombre no se pueden elegir.
  (if (am:motivos-indistinguibles respuesta)
    (progn
      (princ "\n\nNo te ofrezco estas viviendas:")
      (foreach r (am:motivos-indistinguibles respuesta)
        (princ (strcat "\n  " r)))))
  (setq nombres (am:viviendas-de respuesta)
        elegida (am:elegir-vivienda nombres))
  (if (null elegida)
    (progn
      (princ "\nCancelado. No se ha dibujado nada.")
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; 2e. **El estilo de texto de la tabla** (3.5.0): uno que ya existe en su
  ;;     plano —el de su cuadro, o el de sus rótulos—, elegido por el servidor.
  ;;     Si el plano no tiene ninguno del que sacarlo, **no se inventa una
  ;;     fuente**: se dice por qué y no se dibuja (Pablo, 2026-09-13).
  (setq bloque (am:bloque-de-vivienda respuesta elegida))
  (if (or (null bloque)
          (null (am:valor-tras bloque "estilo_texto" 0))
          (= (am:valor-tras bloque "estilo_texto" 0) "nil"))
    (progn
      (princ (strcat "\n\nNo dibujo la tabla: "
                     (if (and bloque (am:valor-tras bloque "motivo_sin_estilo" 0))
                       (am:valor-tras bloque "motivo_sin_estilo" 0)
                       "el servidor no ha elegido ningún estilo de texto de tu plano.")))
      (am:log "no hay estilo de texto del plano con el que dibujar la tabla; no se dibuja")
      (setvar "CMDECHO" eco) (princ) (exit)))
  (setq estilo-texto (am:valor-tras bloque "estilo_texto" 0)
        celdas       (am:celdas-del-cuadro bloque)
        textos       (am:cadenas-tras bloque "textos_a_medir" 0))

  ;; 2f. **Los anchos los mide AutoCAD**, con `textbox`, en ese estilo y a altura
  ;;     1. Qué se mide lo ha decidido el servidor. Si una medida falla, se dice
  ;;     qué texto y qué ha contestado AutoCAD.
  (setq medidos (am:medir-textos textos estilo-texto))
  (if (null medidos)
    (progn
      (princ (strcat "\n\nNo he podido medir los textos de la tabla "
                     (if *am:fallo-de-la-medida*
                       *am:fallo-de-la-medida*
                       "y AutoCAD no ha dado ningún motivo")
                     "."))
      (am:log "fallo al medir los textos de la tabla con textbox")
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; 2g. **Cuánto mide la tabla**, con esas medidas: lo decide el servidor (`D-14`).
  ;;     Todavía sin sitio: se maqueta en el primer clic sólo para saber su tamaño,
  ;;     sin sus cuadros ni lo que hay dibujado. Todo lo lento ya está hecho, así
  ;;     que la vista previa no deja a nadie esperando con el cursor bloqueado.
  (setq m (am:maquetar bloque textos medidos punto nil estilo-texto nil))
  (if (or (null m) (null (am:pos "(\"cabe\" . T)" m 0)))
    (progn
      (princ (strcat "\n\nNo dibujo la tabla: "
                     (if (and m (am:valor-tras m "motivo" 0))
                       (am:valor-tras m "motivo" 0)
                       "el servidor no ha dicho cuánto mide.")))
      (am:log "la tabla no se ha podido maquetar; no se ha dibujado nada")
      (setvar "CMDECHO" eco) (princ) (exit)))

  (setq notas (am:notas-colocadas m))

  ;; 3. **Sin volver a preguntar** (3.7.1, Pablo, 2026-09-15). Hasta la 3.7.0
  ;;    aquí se preguntaba «¿Te dibujo el cuadro de ArchMuse? [Si/No] <No>».
  ;;    Marcar el punto ya es decir que sí, y un Enter sin leer se quedaba en el
  ;;    <No>: no dibujaba nada y parecía un fallo. La red es el grupo de deshacer
  ;;    de abajo: Ctrl+Z una vez lo quita todo. Lo que se dibuja se sigue diciendo.
  (princ (strcat "\n\nDibujo el cuadro de ArchMuse de " (nth elegida nombres)
                 ": " (itoa (length celdas)) " casilla(s) con texto."))
  (princ "\n  Tu cuadro no se toca.")
  ;; **En el plano, las notas cortas; aquí, el detalle** (3.9.2; Pablo: «el detalle
  ;; completo va a la línea de comandos y al log, no al plano»). Al registro van
  ;; los recuentos y no el detalle: lleva nombres de piezas, y el registro viaja
  ;; en ARCHMUSE-INFORME (§4.4).
  (setq detalle (am:textos-de-notas bloque))
  (if detalle
    (progn
      (princ (strcat "\n\nEn el plano, " (itoa (length notas))
                     " línea(s) de nota. El detalle, celda a celda:"))
      (foreach linea detalle (princ (strcat "\n   - " linea)))))
  (am:log (strcat "notas: " (itoa (length notas)) " en el plano, " (itoa (length detalle))
                  " de detalle"))

  ;; **Todo lo que se escribe va dentro de UN grupo de deshacer.** Así un solo
  ;; `UNDO` lo quita entero —tabla, notas y marca— en vez de dejar al arquitecto
  ;; pulsando diez veces, y así se puede retirar en bloque si algo sale mal.
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  ;; `grupo-abierto` es lo que le dice a *error* que hay un grupo que cerrar
  ;; (`C-16`). `*am:dibujo-empezado*` se pone a nil AQUÍ y no sólo dentro de
  ;; `am:dibujar-cuadro`: un Esc antes de entrar encontraría el T de la pasada
  ;; anterior, y el UNDO de *error* desharía algo que hizo él.
  (setq *am:dibujo-empezado* nil grupo-abierto T)
  (vl-catch-all-apply 'vla-StartUndoMark (list doc))
  ;; Lo que se dibuje a partir de aquí es lo que se arrastra en el segundo clic (3.9.6).
  (setq antes-de-dibujar (entlast))

  (setq tabla (am:dibujar-cuadro m celdas))
  (if (null tabla)
    (progn
      (setq grupo-abierto nil)
      (vl-catch-all-apply 'vla-EndUndoMark (list doc))
      ;; **La causa, siempre** (3.4.1). La 3.4.0 decía sólo «No he podido dibujar
      ;; la tabla. No se ha quedado nada a medias.»: ni en qué paso ni por qué —el
      ;; error de AutoCAD se capturaba y se tiraba—, y lo segundo no se comprobaba.
      (princ (strcat "\nNo he podido dibujar la tabla "
                     (if *am:fallo-del-dibujo*
                       *am:fallo-del-dibujo*
                       "y AutoCAD no ha dado ningún motivo")
                     "."))
      (am:log (strcat "fallo al dibujar el cuadro "
                      (if *am:fallo-del-dibujo* *am:fallo-del-dibujo* "sin motivo")))
      ;; Lo que llegó a dibujarse antes del fallo se retira con el mismo UNDO que
      ;; usa la marca de borrador. **Sólo si se llegó a dibujar algo**: con el
      ;; grupo vacío, ese UNDO desharía lo último que hizo él.
      (if *am:dibujo-empezado*
        (if (vl-catch-all-error-p (vl-catch-all-apply 'command (list "_.U")))
          (princ "\nY NO he podido deshacer lo que llegué a dibujar: pulsa Ctrl+Z tú.")
          (princ "\nHe deshecho lo que llegué a dibujar: tu plano está como antes."))
        (princ "\nNo había llegado a dibujar nada: tu plano está como antes."))
      (princ "\nCópiame la línea de «No he podido…» cuando me avises: dice dónde y por qué.")
      (setvar "CMDECHO" eco) (princ) (exit)))
  (princ (strcat "\n" (itoa (length celdas)) " casilla(s) escritas en el cuadro de ArchMuse."))
  (princ "\nTu cuadro sigue exactamente como estaba.")
  ;; Lo que no se ha podido hacer sin impedir la tabla, con su motivo: dicho, no
  ;; tragado (3.4.1).
  (if *am:avisos-del-dibujo*
    (progn
      (princ "\n\nLa tabla está dibujada, pero esto no se ha podido hacer:")
      (foreach r (reverse *am:avisos-del-dibujo*)
        (princ (strcat "\n  - " r))
        (am:log (strcat "aviso al dibujar: " r)))
      (princ "\nCópiame estas líneas cuando me avises.")))

  ;; **`C-3`: nunca números sin marca.** Un cuadro relleno sin la advertencia de
  ;; borrador es exactamente el estado que ese criterio existe para impedir, y es
  ;; peor que no haber escrito nada: el arquitecto se queda con cifras que
  ;; parecen definitivas. Si la marca no se puede poner, **se retira lo escrito**.
  ;;
  ;; Pasó el 2026-09-11: la marca reventó DESPUÉS de escribir las diez celdas y
  ;; el plano se quedó con los números y sin advertencia. Si el arquitecto no
  ;; llega a mirar la línea de comandos, no se entera.
  ;; **La marca va en la tabla de ArchMuse**, no en la suya: es la nuestra la
  ;; que lleva cifras que hay que calificar de borrador, y la suya no se toca.
  ;; Misma capa y mismo texto que la via web, que es lo que exige `C-9`.
  (setq marcado (am:marcar-borrador tabla m))

  (if (null marcado)
    (progn
      (setq grupo-abierto nil)
      (vl-catch-all-apply 'vla-EndUndoMark (list doc))
      (am:log "la marca de borrador no se ha podido poner; se retira lo escrito")
      (princ "\n\n*** ATENCIÓN — NO he podido poner la marca de borrador. ***")
      (princ "\nUn cuadro con cifras y sin esa advertencia parece definitivo, y no lo")
      (princ "\nes. Deshago lo que acabo de escribir para no dejarte el plano así.")
      (if (vl-catch-all-error-p (vl-catch-all-apply 'command (list "_.U")))
        (progn
          (princ "\n\n*** Y TAMPOCO he podido deshacerlo. ***")
          (princ "\nTu cuadro tiene AHORA MISMO cifras de ArchMuse sin marca de")
          (princ "\nborrador. Pulsa Ctrl+Z tú, o no entregues este plano sin revisarlo."))
        (princ "\nHecho: el cuadro ha vuelto a como estaba. No has perdido nada."))
      (setvar "CMDECHO" eco)
      (princ)
      (exit)))

  ;; 4. **Segundo clic: dónde va** (3.9.6; dos clics, Pablo, 2026-09-16). La tabla, sus
  ;;    notas y la marca siguen al cursor con la orden MOVER, dentro del mismo grupo de
  ;;    deshacer: Ctrl+Z una vez quita todo, movimiento incluido, y un Esc llega a
  ;;    *error* con el grupo abierto y lo deshace.
  (setq propios (am:entidades-desde antes-de-dibujar))
  ;;    Sin Orto, forzcursor ni referencias mientras se arrastra (3.9.7), y devueltos justo
  ;;    después: con Orto la tabla no iba pegada al cursor. Un Esc aquí los devuelve en *error*.
  (setq arrastre-libre (am:arrastre-libre))
  (setq colocado (am:arrastrar-cuadro tabla propios (nth elegida nombres)))
  (am:devolver-arrastre arrastre-libre)
  (setq arrastre-libre nil)
  (if (null colocado)
    (progn
      (setq grupo-abierto nil)
      (vl-catch-all-apply 'vla-EndUndoMark (list doc))
      (if (vl-catch-all-error-p (vl-catch-all-apply 'command (list "_.U")))
        (princ "\nNo has elegido dónde poner el cuadro, y NO he podido quitarlo: pulsa Ctrl+Z tú.")
        (princ "\nNo has elegido dónde poner el cuadro: no dejo nada dibujado."))
      (am:log "enter sin elegir sitio al colocar el cuadro; se retira lo dibujado")
      (setvar "CMDECHO" eco) (princ) (exit)))
  ;;    Si tapa algo, se queda donde está y sólo se avisa: se mira qué hay bajo esa
  ;;    huella, sin contar lo que acaba de dibujar, y el servidor lo redacta.
  (setq obstaculos (am:obstaculos (am:huella-del-cuadro m colocado) propios))
  (setq m (am:maquetar bloque textos medidos colocado cuadros estilo-texto obstaculos))
  (setq grupo-abierto nil)
  (vl-catch-all-apply 'vla-EndUndoMark (list doc))
  (setq tapa (if m (am:valor-tras m "tapa" 0)))
  (if (and tapa (/= tapa "nil"))
    (princ (strcat "\n  " tapa))
    (princ "\n  El cuadro va donde has hecho clic."))
  (am:log (strcat (itoa (if *am:obstaculos-enviados* *am:obstaculos-enviados* 0))
                  " obstaculo(s) bajo la tabla; "
                  (if (and tapa (/= tapa "nil")) "tapa parte del dibujo" "no tapa nada")))

  (princ "\nEs un BORRADOR para revisión de un colegiado. La marca está en la capa")
  ;; El nombre de la capa sale de la variable y no escrito a mano:
  ;; un mensaje que nombra una capa distinta de donde se escribe de
  ;; verdad es otra forma de mandar al arquitecto a mirar donde no es.
  (princ (strcat "\n«" *am:capa-de-la-marca* "»: puedes apagarla para imprimir, no borrarla."))
  ;; Ctrl+Z, no «UNDO» ni «U»: en AutoCAD en español «U» abre UNIR y «UNDO» no
  ;; deshace (Pablo, 2026-09-16). Todo va en un solo grupo de deshacer.
  (princ "\nCtrl+Z deshace todo lo que acabo de escribir.")
  ;; Hasta el 2026-09-13 esta línea leía `resultado`, que no se asignaba en
  ;; ninguna parte: `(itoa (car nil))` revienta, así que el comando terminaba
  ;; en «se ha detenido» después de haber dibujado y marcado bien.
  (am:log (strcat "OK: " (itoa (length celdas)) " casilla(s) escritas, "
                  (itoa (length notas)) " nota(s) al pie"))
  (setvar "CMDECHO" eco)
  ;; El aviso del día también aquí (2026-09-16): la primera petición del comando
  ;; ha hecho que el servidor mire el canal, y reiniciar AutoCAD no reinicia el
  ;; servidor. Sigue siendo como mucho un aviso al día, sin red.
  (if (and (getenv "LOCALAPPDATA") (am:servidor-instalado))
    (vl-catch-all-apply
      '(lambda () (am:actualizaciones-al-cargar (strcat (getenv "LOCALAPPDATA") "\\ArchMuse")))))
  (princ))

(defun c:ARCHMUSE-ACTUALIZAR ()
  ;; La actualización descargada, a mano (PRD 2026-09-15). Ver
  ;; `am:ofrecer-actualizacion`, en la sección de actualizaciones.
  (am:ofrecer-actualizacion)
  (princ))

;; Actualizaciones: como mucho un aviso al día, sin red y sin poder romper la carga
;; (3.9.1). Sólo en una instalación hecha con el instalador.
(if (and (getenv "LOCALAPPDATA") (am:servidor-instalado))
  (vl-catch-all-apply
    '(lambda () (am:actualizaciones-al-cargar (strcat (getenv "LOCALAPPDATA") "\\ArchMuse")))))

(princ "\nArchMuse cargado. Teclea ARCHMUSE para medir el plano y dibujar tu cuadro.")
(princ)
