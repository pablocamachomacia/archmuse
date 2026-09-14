;;; Sonda 3, de solo lectura: dónde están los cuadros de superficies.
;;; Por fichero: tablas (ACAD_TABLE) que ve `ssget "_X"`, cuántas son cuadros
;;; (algún texto con SUPERFICIE o S. UTIL), en qué espacio están, tablas dentro
;;; de xref cargadas, y textos sueltos con SUPERFICIE (cuadro dibujado a mano).

(defun s3-textos (d / r)
  (setq r "")
  (foreach g d
    (if (and (member (car g) '(1 3 302 303)) (= (type (cdr g)) 'STR))
      (setq r (strcat r " " (cdr g)))))
  r)

(defun s3-es-cuadro (txt)
  (wcmatch (strcase txt) "*SUPERFICIE*,*S. UTIL*,*S.UTIL*"))

(defun s3-limpio (txt)
  (vl-string-translate "\t\r\n" "   " (substr txt 1 (min 90 (strlen txt)))))

(defun sonda3 (ruta / f ss i d txt n nc esp ej b fl nom e nx nxc ssT nt)
  (setq f (open ruta "a") n 0 nc 0 esp "" ej "")
  (setq ss (ssget "_X" '((0 . "ACAD_TABLE"))) i 0)
  (if ss
    (while (< i (sslength ss))
      (setq d (entget (ssname ss i)) txt (s3-textos d) n (1+ n))
      (if (s3-es-cuadro txt)
        (progn
          (setq nc (1+ nc) esp (strcat esp (cdr (assoc 410 d)) " "))
          (if (= ej "") (setq ej (s3-limpio txt)))))
      (setq i (1+ i))))
  (setq nx 0 nxc 0 b (tblnext "BLOCK" T))
  (while b
    (setq fl (cdr (assoc 70 b)) nom (cdr (assoc 2 b)))
    (if (= 36 (logand 36 fl))
      (progn
        (setq e (tblobjname "BLOCK" nom))
        (while (setq e (entnext e))
          (setq d (entget e))
          (if (= (cdr (assoc 0 d)) "ACAD_TABLE")
            (progn
              (setq nx (1+ nx))
              (if (s3-es-cuadro (s3-textos d)) (setq nxc (1+ nxc))))))))
    (setq b (tblnext "BLOCK")))
  (setq ssT (ssget "_X" '((0 . "TEXT,MTEXT") (1 . "*SUPERFICIE*,*Superficie*,*superficie*"))))
  (setq nt (if ssT (sslength ssT) 0))
  (write-line (strcat (getvar "DWGPREFIX") (getvar "DWGNAME")
                      "\t" (itoa n) "\t" (itoa nc) "\t" esp "\t" (itoa nx) "\t" (itoa nxc)
                      "\t" (itoa nt) "\t" ej)
              f)
  (close f)
  (princ))
