;;; ===========================================================================
;;; ArchMuse — comando ARCHMUSE para AutoCAD
;;; ===========================================================================
;;;
;;; Mide las superficies útiles de la planta dibujada y las escribe en una
;;; tabla nativa dentro del propio plano.
;;;
;;; PRD: docs/prd/2026-09-08-integracion-autocad-autolisp.md (tareas 5 y 6).
;;; Checklist de la primera prueba: docs/design/checklist-primera-prueba-autocad.md
;;;
;;; ---------------------------------------------------------------------------
;;; ESTE FICHERO NUNCA SE HA EJECUTADO
;;; ---------------------------------------------------------------------------
;;; Se escribió el 2026-09-09 sin AutoCAD instalado. Cada función se ha
;;; contrastado contra la referencia oficial de Autodesk, y el fichero pasa un
;;; comprobador de paréntesis y de comillas, pero **eso no es haberlo
;;; ejecutado**. Lo que no se ha podido comprobar está en `docs/PROGRESS.md`,
;;; entrada del 2026-09-09, y el checklist separa prueba a prueba lo que sería
;;; un fallo del flujo de lo que sería un fallo del lenguaje.
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

(setq *am:url*      "http://localhost:5000/api/medicion-geometria?formato=lisp")
(setq *am:version*  "1.0.0 (2026-09-09, sin ejecutar)")
(setq *am:capa-por-defecto* "00 areas")

;; Leyenda de `C3`, literal y sin opción de desactivarla. Es la misma frase que
;; `analyzer/marca_borrador.py` estampa en el resto de entregables: si cambia
;; allí, tiene que cambiar aquí.
(setq *am:leyenda-borrador*
  "BORRADOR PARA REVISIÓN DE UN COLEGIADO. ArchMuse asesora; el proyecto lo firma el arquitecto que lo redacta.")

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

(defun am:cadenas-de-lista (cadena clave desde / marca p i ch res par seguir)
  ;; Las cadenas de una lista `("clave" . ("a" "b"))`, en orden.
  ;; Recorre carácter a carácter llevando la cuenta de si está dentro de una
  ;; cadena, que es lo que hace que un «pieza(s)» dentro de un motivo no cierre
  ;; la lista antes de tiempo.
  (setq marca (strcat "(\"" clave "\" . ("))
  (setq p (am:pos marca cadena desde))
  (if (null p)
    nil
    (progn
      (setq i (+ p (strlen marca)) res nil seguir T)
      (while (and seguir (< i (strlen cadena)))
        (setq ch (am:car-en cadena i))
        (cond
          ((= ch "\"")
            (setq par (am:lee-cadena cadena i))
            (if par
              (setq res (cons (car par) res) i (cdr par))
              (setq seguir nil)))
          ((= ch ")") (setq seguir nil))
          (T          (setq i (1+ i)))))
      (reverse res))))

(defun am:num->texto (x)
  ;; Formato español de una superficie: dos decimales y coma decimal, igual que
  ;; el PDF y el acta. `rtos` en modo 2 escribe siempre con punto.
  (vl-string-subst "," "." (rtos x 2 2)))

(defun am:texto->real (s)
  ;; «58.78» -> 58.78. `distof` en modo 2 (decimal) devuelve nil si no es un
  ;; número, que es lo que hace falta para distinguir una cifra de un «nil».
  (if s (distof s 2) nil))

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

(defun am:capas-con-recintos ( / ss i ename capa capas par)
  ;; Capas que tienen alguna polilínea cerrada, con su recuento. Es una ayuda
  ;; para preguntar, no una detección: la capa la confirma el usuario y el
  ;; servidor la valida.
  (setq ss (ssget "_X" '((0 . "LWPOLYLINE") (-4 . "&") (70 . 1))))
  (setq capas nil i 0)
  (if ss
    (while (< i (sslength ss))
      (setq ename (ssname ss i)
            capa  (cdr (assoc 8 (entget ename)))
            par   (assoc capa capas))
      (if par
        (setq capas (subst (cons capa (1+ (cdr par))) par capas))
        (setq capas (cons (cons capa 1) capas)))
      (setq i (1+ i))))
  (reverse capas))

(defun am:elegir-capa ( / capas respuesta)
  (setq capas (am:capas-con-recintos))
  (cond
    ((null capas)
      (princ "\nArchMuse: no hay ninguna polilínea cerrada en este dibujo.")
      nil)
    ;; Si la capa por defecto del repositorio está y tiene recintos, se propone.
    ((assoc *am:capa-por-defecto* capas)
      (princ (strcat "\nArchMuse: capa de recintos detectada «" *am:capa-por-defecto*
                     "» (" (itoa (cdr (assoc *am:capa-por-defecto* capas)))
                     " polilíneas cerradas)."))
      (setq respuesta (getstring T "\nPulsa INTRO para aceptarla, o escribe otra capa: "))
      (if (= respuesta "") *am:capa-por-defecto* respuesta))
    (T
      (princ "\nArchMuse no reconoce la capa de recintos de este plano. Candidatas:")
      (foreach par capas
        (princ (strcat "\n   " (car par) "  (" (itoa (cdr par)) " polilíneas cerradas)")))
      (setq respuesta (getstring T "\nEscribe la capa de recintos: "))
      (if (= respuesta "") nil respuesta))))

(defun am:abiertas-en (capa / todas cerradas)
  ;; Cuántas polilíneas de la capa NO llevan el bit de cerrada. Ver la decisión
  ;; de diseño 3 de la cabecera: el navegador recupera buena parte de éstas y
  ;; este comando no puede, así que se cuentan para poder decirlo.
  ;;
  ;; Por diferencia y no con un filtro `<NOT` sobre el operador bit a bit:
  ;; anidar `<NOT` alrededor de `(-4 . "&")` es construcción dudosa, y aquí no
  ;; hay forma de probarla. Dos `ssget` simples hacen lo mismo sin apostar.
  (setq todas    (ssget "_X" (list '(0 . "LWPOLYLINE") (cons 8 capa)))
        cerradas (ssget "_X" (list '(0 . "LWPOLYLINE") (cons 8 capa)
                                   '(-4 . "&") '(70 . 1))))
  (- (if todas (sslength todas) 0)
     (if cerradas (sslength cerradas) 0)))

(defun am:recolectar (capa / ss i ename recintos textos datos tipo txt pt primero json)
  ;; Devuelve el cuerpo JSON completo, o nil si no hay nada que medir.
  (setq ss (ssget "_X" (list '(0 . "LWPOLYLINE") (cons 8 capa) '(-4 . "&") '(70 . 1))))
  (if (null ss)
    (progn (princ (strcat "\nArchMuse: no hay polilíneas cerradas en la capa «" capa "»."))
           nil)
    (progn
      (setq recintos "" primero T i 0)
      (while (< i (sslength ss))
        (setq ename (ssname ss i))
        (if (not primero) (setq recintos (strcat recintos ",")))
        (setq recintos
          (strcat recintos
                  "{\"handle\":" (am:json-cad (cdr (assoc 5 (entget ename))))
                  ",\"capa\":"   (am:json-cad capa)
                  ",\"vertices\":" (am:json-vertices (am:vertices-de ename)) "}"))
        (setq primero nil i (1+ i)))

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
          (if (and txt (/= txt "") (car pt))
            (progn
              (if (not primero) (setq textos (strcat textos ",")))
              (setq textos
                (strcat textos
                        "{\"handle\":" (am:json-cad (cdr (assoc 5 datos)))
                        ",\"capa\":"   (am:json-cad (cdr (assoc 8 datos)))
                        ",\"texto\":"  (am:json-cad txt)
                        ",\"x\":"      (am:json-num (car pt))
                        ",\"y\":"      (am:json-num (cadr pt)) "}"))
              (setq primero nil)))
          (setq i (1+ i))))

      (setq json
        (strcat "{\"insunits\":" (itoa (getvar "INSUNITS"))
                ",\"capa_de_recintos\":" (am:json-cad capa)
                ",\"recintos\":[" recintos "]"
                ",\"textos\":[" textos "]}"))
      json)))

;;; ---------------------------------------------------------------------------
;;; La petición
;;; ---------------------------------------------------------------------------

(defun am:post (cuerpo / http estado respuesta)
  ;; COM es la única vía: AutoLISP no tiene HTTP. En AutoCAD LT
  ;; `vlax-create-object` devuelve nil siempre y aquí se sale con un mensaje
  ;; que lo dice, en vez de con un error de LISP que no explica nada.
  (setq http (vl-catch-all-apply 'vlax-create-object (list "WinHttp.WinHttpRequest.5.1")))
  (if (or (vl-catch-all-error-p http) (null http))
    (progn
      (princ "\nArchMuse: no se ha podido crear el objeto HTTP.")
      (princ "\n  Si esto es AutoCAD LT, no hay solución: LT no permite crear objetos COM.")
      (princ "\n  Si es AutoCAD completo, revisa el antivirus o el cortafuegos.")
      nil)
    (progn
      (setq respuesta
        (vl-catch-all-apply
          '(lambda ()
            (vlax-invoke-method http 'Open "POST" *am:url* :vlax-false)
            (vlax-invoke-method http 'SetRequestHeader "Content-Type"
                                "application/json; charset=utf-8")
            ;; Resolver, conectar, enviar, recibir. El de recibir es de cinco
            ;; minutos a propósito: medir seis viviendas tarda unos doce
            ;; segundos, y el valor por defecto de WinHttp (30 s) dejaría un
            ;; plano grande a medias con un error que parecería de red.
            (vlax-invoke-method http 'SetTimeouts 10000 10000 30000 300000)
            (vlax-invoke-method http 'Send cuerpo)
            (setq estado (vlax-get-property http 'Status))
            (vlax-get-property http 'ResponseText))))
      (vl-catch-all-apply 'vlax-release-object (list http))
      (cond
        ((vl-catch-all-error-p respuesta)
          (princ "\nArchMuse no responde en localhost:5000. ¿Está levantado el servidor?")
          (princ (strcat "\n  Detalle: " (vl-catch-all-error-message respuesta)))
          nil)
        ((/= estado 200)
          (princ (strcat "\nArchMuse ha devuelto un error " (itoa estado) ":"))
          (princ (strcat "\n  " respuesta))
          nil)
        (T respuesta)))))

;;; ---------------------------------------------------------------------------
;;; Lectura de la respuesta — cuatro campos, no un parser
;;; ---------------------------------------------------------------------------

(defun am:viviendas (s / p viviendas nombre interior exterior motivos)
  ;; Recorre las marcas `("vivienda" . "…")` en orden. Para cada una, el primer
  ;; `("util_interior_m2" . …)` que aparece DESPUÉS es el suyo: son campos del
  ;; mismo diccionario, así que están dentro de su bloque, y los del plano
  ;; entero vienen más tarde. No depende del orden de las claves.
  (setq viviendas nil p 0)
  (while (setq p (am:pos "(\"vivienda\" . " s p))
    (setq nombre   (am:valor-tras s "vivienda" p)
          interior (am:valor-tras s "util_interior_m2" p)
          exterior (am:valor-tras s "util_exterior_m2" p)
          motivos  (am:cadenas-de-lista s "impedimentos" p))
    (setq viviendas (cons (list nombre interior exterior motivos) viviendas))
    (setq p (1+ p)))
  (reverse viviendas))

;;; ---------------------------------------------------------------------------
;;; La tabla
;;; ---------------------------------------------------------------------------

(defun am:filas-necesarias (viviendas / n)
  ;; Título + cabecera + una fila por vivienda + una fila de motivo por cada
  ;; vivienda bloqueada + fila de planta + fila de la marca de borrador.
  (setq n 2)
  (foreach v viviendas
    (setq n (1+ n))
    (if (null (am:texto->real (cadr v))) (setq n (1+ n))))
  (+ n 2))

(defun am:escala-de-dibujo ( / u)
  ;; Cuantas unidades de dibujo mide un metro, segun `$INSUNITS`.
  ;;
  ;; La tabla se crea con medidas en UNIDADES DE DIBUJO, no en metros. Una tabla
  ;; de 1 unidad de alto es legible en un plano dibujado en metros y es un punto
  ;; invisible en uno dibujado en milimetros, que es como viene la mitad de los
  ;; planos. Esto no es criterio: es la misma tabla de unidades que usa
  ;; `analyzer/escala.py`, aplicada aqui al tamaño del dibujo.
  (setq u (getvar "INSUNITS"))
  (cond ((= u 4) 1000.0)      ; milimetros
        ((= u 5) 100.0)       ; centimetros
        ((= u 14) 10.0)       ; decimetros
        (T 1.0)))             ; metros, o desconocido: no se escala

(defun am:dibujar-tabla (pt s viviendas / doc ms tabla fila v interior exterior
                                          plano-int plano-ext motivo p-planta k)
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object))
        ms  (vla-get-ModelSpace doc)
        k   (am:escala-de-dibujo))
  ;; (InsertionPoint NumRows NumColumns RowHeight ColWidth)
  (setq tabla (vla-AddTable ms (vlax-3d-point pt)
                            (am:filas-necesarias viviendas) 3 (* 1.0 k) (* 12.0 k)))
  (vla-put-RegenerateTableSuppressed tabla :vlax-true)

  (vla-SetColumnWidth tabla 0 (* 16.0 k))
  (vla-SetColumnWidth tabla 1 (* 12.0 k))
  (vla-SetColumnWidth tabla 2 (* 12.0 k))

  (vla-SetText tabla 0 0 "ArchMuse · superficies útiles")
  (vla-SetText tabla 1 0 "Vivienda")
  (vla-SetText tabla 1 1 "Útil interior (m²)")
  ;; El encabezado dice que no se suman. Es la primera lectura que hace quien
  ;; mira la tabla, y la que evita que alguien sume las dos columnas a mano.
  (vla-SetText tabla 1 2 "Útil exterior (m²) — no se suma a la interior")

  (setq fila 2)
  (foreach v viviendas
    (setq interior (am:texto->real (cadr v))
          exterior (am:texto->real (caddr v)))
    (vla-SetText tabla fila 0 (car v))
    (if (and interior exterior)
      (progn
        (vla-SetText tabla fila 1 (am:num->texto interior))
        (vla-SetText tabla fila 2 (am:num->texto exterior))
        (setq fila (1+ fila)))
      (progn
        ;; NUNCA un valor inventado ni una celda vacía: una celda vacía se lee
        ;; como «se olvidó», y el motivo va debajo, en su propia fila.
        (vla-SetText tabla fila 1 "no se publica")
        (vla-SetText tabla fila 2 "no se publica")
        (setq fila (1+ fila))
        ;; Acumulado con `foreach` y no con `(apply 'strcat …)`: `apply` tiene
        ;; tope de argumentos, y una vivienda puede traer tres impedimentos.
        (setq motivo "")
        (foreach m (cadddr v) (setq motivo (strcat motivo m ". ")))
        (if (= motivo "")
          (setq motivo "Sin motivo declarado — avisa, esto es un fallo de ArchMuse."))
        (vla-MergeCells tabla fila fila 0 2)
        (vla-SetText tabla fila 0 motivo)
        (setq fila (1+ fila)))))

  ;; La planta entera, con las mismas dos magnitudes y la misma regla.
  (setq p-planta (am:pos "(\"superficies_del_plano\"" s 0)
        plano-int (if p-planta (am:texto->real (am:valor-tras s "util_interior_m2" p-planta)))
        plano-ext (if p-planta (am:texto->real (am:valor-tras s "util_exterior_m2" p-planta))))
  (vla-SetText tabla fila 0 "TOTAL DE LA PLANTA")
  (if (and plano-int plano-ext)
    (progn
      (vla-SetText tabla fila 1 (am:num->texto plano-int))
      (vla-SetText tabla fila 2 (am:num->texto plano-ext)))
    (progn
      (vla-SetText tabla fila 1 "no se publica")
      (vla-SetText tabla fila 2 "no se publica")))
  (setq fila (1+ fila))

  ;; `C3`, obligatoria y sin parámetro que la quite. Va la última porque es lo
  ;; que tiene que leer quien reciba el plano, no quien lo dibuja.
  (vla-MergeCells tabla fila fila 0 2)
  (vla-SetText tabla fila 0 *am:leyenda-borrador*)

  (vla-put-RegenerateTableSuppressed tabla :vlax-false)
  tabla)

;;; ---------------------------------------------------------------------------
;;; El comando
;;; ---------------------------------------------------------------------------

(defun c:ARCHMUSE ( / *error* capa abiertas cuerpo respuesta viviendas pt eco)

  (defun *error* (msg)
    ;; `(exit)` levanta *error* con «quit / exit abort». Una salida ordenada no
    ;; puede imprimirse como fallo, asi que entra en la lista junto al ESC.
    (if (and msg (not (wcmatch (strcase msg)
                               "*BREAK*,*CANCEL*,*SALIDA*,*QUIT*,*EXIT*")))
      (princ (strcat "\nArchMuse se ha detenido: " msg)))
    (setvar "CMDECHO" (if eco eco 1))
    (princ))

  (setq eco (getvar "CMDECHO"))
  (setvar "CMDECHO" 0)

  (princ (strcat "\nArchMuse " *am:version*))

  (setq capa (am:elegir-capa))
  (if (null capa)
    (progn (setvar "CMDECHO" eco) (princ) (exit)))

  ;; Lo que se deja fuera, ANTES de medir. Ver la decisión de diseño 3.
  (setq abiertas (am:abiertas-en capa))
  (if (> abiertas 0)
    (progn
      (princ (strcat "\nAVISO: " (itoa abiertas) " polilínea(s) de «" capa
                     "» no llevan el flag de cerrada y NO se envían."))
      (princ "\n  El navegador sí recupera las que cierran geométricamente, así que")
      (princ "\n  esta medición puede quedarse corta. Súbelo a /medir para comparar.")))

  (setq cuerpo (am:recolectar capa))
  (if (null cuerpo)
    (progn (setvar "CMDECHO" eco) (princ) (exit)))

  (princ "\nMidiendo… (una planta de seis viviendas tarda unos 12 segundos)")
  (setq respuesta (am:post cuerpo))
  (if (null respuesta)
    (progn (setvar "CMDECHO" eco) (princ) (exit)))

  (setq viviendas (am:viviendas respuesta))
  (if (null viviendas)
    (progn
      (princ "\nArchMuse no ha podido separar ninguna vivienda en este plano.")
      (princ (strcat "\n  " (if (am:valor-tras respuesta "motivo" 0)
                              (am:valor-tras respuesta "motivo" 0)
                              "Sin motivo declarado.")))
      (setvar "CMDECHO" eco) (princ) (exit)))

  ;; Se enseña por la línea de comandos ANTES de dibujar: si la cifra está mal,
  ;; el arquitecto lo ve sin haberse encontrado ya una tabla dentro del plano.
  (princ (strcat "\n" (itoa (length viviendas)) " vivienda(s) medidas:"))
  (foreach v viviendas
    (princ (strcat "\n   " (car v) "   interior " (cadr v) "   exterior " (caddr v))))

  (setq pt (getpoint "\nPunto de inserción de la tabla: "))
  (if (null pt)
    (progn (princ "\nCancelado: no se ha dibujado nada.")
           (setvar "CMDECHO" eco) (princ) (exit)))

  (am:dibujar-tabla pt respuesta viviendas)
  (princ "\nTabla insertada. Es un BORRADOR para revisión de un colegiado.")
  (setvar "CMDECHO" eco)
  (princ))

(princ "\nArchMuse cargado. Teclea ARCHMUSE para medir la planta.")
(princ)
