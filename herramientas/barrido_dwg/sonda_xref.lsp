;;; Sonda de solo lectura: qué referencias externas tiene el dibujo abierto y
;;; qué ve `ssget "_X"`. No modifica ni guarda nada.
;;; Salida por dibujo, separada por tabuladores: ruta, xrefs, cargadas,
;;; inserciones en Model, inserciones en total, polilíneas en Model, polilíneas
;;; en capas *AREA* propias, polilíneas dentro de xref, polilíneas en capas
;;; *AREA* dentro de xref, capas dependientes *AREA*, detalle de cada xref.

(defun sonda-contar (ss) (if ss (sslength ss) 0))

;; Entidades de la definición de un bloque (para una xref cargada, su contenido):
;; (polilíneas  polilíneas-en-capas-*AREA*)
(defun sonda-dentro (nombre / e d n na)
  (setq n 0 na 0 e (tblobjname "BLOCK" nombre))
  (if e
    (while (setq e (entnext e))
      (setq d (entget e))
      (if (= (cdr (assoc 0 d)) "LWPOLYLINE")
        (progn
          (setq n (1+ n))
          (if (wcmatch (strcase (cdr (assoc 8 d))) "*AREA*") (setq na (1+ na)))))))
  (list n na))

(defun sonda (ruta / f b fl nom nx resueltas enmodelo entodas xr lays l ln dentro tot tota ssh sa)
  (setq f (open ruta "a")
        nx 0 resueltas 0 enmodelo 0 entodas 0 xr "" tot 0 tota 0)
  (setq b (tblnext "BLOCK" T))
  (while b
    (setq fl (cdr (assoc 70 b)) nom (cdr (assoc 2 b)))
    (if (= 4 (logand 4 fl))
      (progn
        (setq nx (1+ nx))
        (if (= 32 (logand 32 fl)) (setq resueltas (1+ resueltas)))
        (setq enmodelo (+ enmodelo (sonda-contar (ssget "_X" (list '(0 . "INSERT") (cons 2 nom) '(410 . "Model"))))))
        (setq entodas (+ entodas (sonda-contar (ssget "_X" (list '(0 . "INSERT") (cons 2 nom))))))
        (setq dentro (sonda-dentro nom)
              tot (+ tot (car dentro))
              tota (+ tota (cadr dentro)))
        (setq xr (strcat xr nom " [flags " (itoa fl) ", " (itoa (car dentro)) " pol, "
                         (itoa (cadr dentro)) " en *AREA*] = "
                         (if (assoc 1 b) (cdr (assoc 1 b)) "?") " ## "))))
    (setq b (tblnext "BLOCK")))
  (setq lays "" l (tblnext "LAYER" T))
  (while l
    (setq ln (cdr (assoc 2 l)))
    (if (and (wcmatch ln "*`|*") (wcmatch (strcase ln) "*AREA*"))
      (setq lays (strcat lays ln " ## ")))
    (setq l (tblnext "LAYER")))
  (setq ssh (sonda-contar (ssget "_X" '((0 . "LWPOLYLINE") (410 . "Model"))))
        sa  (sonda-contar (ssget "_X" '((0 . "LWPOLYLINE") (8 . "*AREA*") (410 . "Model")))))
  (write-line (strcat (getvar "DWGPREFIX") (getvar "DWGNAME")
                      "\t" (itoa nx) "\t" (itoa resueltas) "\t" (itoa enmodelo) "\t" (itoa entodas)
                      "\t" (itoa ssh) "\t" (itoa sa) "\t" (itoa tot) "\t" (itoa tota)
                      "\t" lays "\t" xr)
              f)
  (close f)
  (princ))
