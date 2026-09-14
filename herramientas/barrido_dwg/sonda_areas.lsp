;;; Sonda 2, de solo lectura: polilíneas en capas *AREA* por capa, con su
;;; superficie (fórmula del área de Gauss sobre los vértices), en el propio plano
;;; y dentro de las xref cargadas. No modifica ni guarda nada.

(defun s2-gauss (d / pts a i n p q)
  (setq pts nil)
  (foreach g d (if (= (car g) 10) (setq pts (cons (cdr g) pts))))
  (setq pts (reverse pts) a 0.0 i 0 n (length pts))
  (while (< i n)
    (setq p (nth i pts) q (nth (rem (1+ i) n) pts))
    (setq a (+ a (- (* (car p) (cadr q)) (* (car q) (cadr p)))))
    (setq i (1+ i)))
  (abs (/ a 2.0)))

(defun s2-acum (lst capa ar / par)
  (setq par (assoc capa lst))
  (if par
    (subst (list capa (1+ (cadr par)) (+ ar (caddr par))) par lst)
    (cons (list capa 1 ar) lst)))

(defun sonda2 (ruta / f ss i d lst b fl nom e)
  (setq f (open ruta "a") lst nil)
  (setq ss (ssget "_X" '((0 . "LWPOLYLINE") (410 . "Model"))) i 0)
  (if ss
    (while (< i (sslength ss))
      (setq d (entget (ssname ss i)))
      (if (wcmatch (strcase (cdr (assoc 8 d))) "*AREA*")
        (setq lst (s2-acum lst (strcat "[propio] " (cdr (assoc 8 d))) (s2-gauss d))))
      (setq i (1+ i))))
  (setq b (tblnext "BLOCK" T))
  (while b
    (setq fl (cdr (assoc 70 b)) nom (cdr (assoc 2 b)))
    (if (= 36 (logand 36 fl))
      (progn
        (setq e (tblobjname "BLOCK" nom))
        (while (setq e (entnext e))
          (setq d (entget e))
          (if (and (= (cdr (assoc 0 d)) "LWPOLYLINE")
                   (wcmatch (strcase (cdr (assoc 8 d))) "*AREA*"))
            (setq lst (s2-acum lst (strcat "[xref] " (cdr (assoc 8 d))) (s2-gauss d)))))))
    (setq b (tblnext "BLOCK")))
  (write-line (strcat "== " (getvar "DWGPREFIX") (getvar "DWGNAME")) f)
  (foreach par (reverse lst)
    (write-line (strcat "   " (car par) "\t" (itoa (cadr par)) " pol\t" (rtos (caddr par) 2 2) " u2") f))
  (close f)
  (princ))
