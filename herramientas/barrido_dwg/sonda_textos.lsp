;;; Sonda 4, de solo lectura: los textos con SUPERFICIE de un dibujo, agrupados
;;; por (espacio, tipo, capa, contenido), para saber si son un cuadro dibujado a
;;; mano o sólo títulos y notas.

(defun s4-acum (lst clave / par)
  (setq par (assoc clave lst))
  (if par
    (subst (list clave (1+ (cadr par))) par lst)
    (cons (list clave 1) lst)))

(defun sonda4 (ruta / f ss i d lst txt)
  (setq f (open ruta "a") lst nil)
  (setq ss (ssget "_X" '((0 . "TEXT,MTEXT") (1 . "*SUPERFICIE*,*Superficie*,*superficie*"))) i 0)
  (if ss
    (while (< i (sslength ss))
      (setq d (entget (ssname ss i))
            txt (cdr (assoc 1 d)))
      (setq txt (vl-string-translate "\t\r\n" "   " (substr txt 1 (min 70 (strlen txt)))))
      (setq lst (s4-acum lst (strcat (cdr (assoc 410 d)) " | " (cdr (assoc 0 d)) " | "
                                     (cdr (assoc 8 d)) " | " txt)))
      (setq i (1+ i))))
  (write-line (strcat "== " (getvar "DWGNAME")) f)
  (foreach par (reverse lst)
    (write-line (strcat "   " (itoa (cadr par)) " x  " (car par)) f))
  (close f)
  (princ))
