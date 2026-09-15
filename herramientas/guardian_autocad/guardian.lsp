;;; ===========================================================================
;;; ArchMuse · guardián: ¿deja ARCHMUSE AutoCAD como lo encontró? (C-16)
;;; ===========================================================================
;;;
;;; Herramienta de desarrollo. NO va en el instalador. Ver LEEME.md.
;;;
;;; Uso, en un AutoCAD de verdad y con un plano abierto:
;;;   1. APPLOAD este fichero.
;;;   2. ARCHMUSE-GUARDIAN   foto de antes.
;;;   3. ARCHMUSE            como quieras probarlo: hasta el final, con Esc en
;;;                          una pregunta, con el servidor parado.
;;;   4. ARCHMUSE-GUARDIAN   foto de después: compara y lo dice.
;;; Entre 2 y 4, ningún otro comando: cualquiera cambia variables por su cuenta.
;;;
;;; Por qué dos pasos y no un comando que llame a ARCHMUSE: un Esc aborta TODA
;;; la evaluación de AutoLISP, también la del que llama. Un guardián que
;;; envolviera el comando no llegaría a comparar justo en el caso que más importa.
;;;
;;; Qué mira:
;;;   - Las variables de sistema que lista AutoCAD 2027 con SETVAR ? * en Core
;;;     Console (2026-09-15). Una que sólo exista en el AutoCAD con ventanas no
;;;     está en la lista.
;;;   - Los valores del registro del perfil activo (Variables) y de
;;;     FixedProfile\General Configuration, donde vive FILEDIA: una variable
;;;     puede volver a su valor en la sesión y quedar cambiada para la próxima.
;;; Qué no mira: el contenido del dibujo. Eso lo protege el grupo de deshacer.
;;;
;;; No cambia nada: sólo lee (getvar, vl-registry-read) y escribe su informe en
;;; %TEMP%. Un test de la suite lo comprueba.
;;;
;;; Sin punto y coma dentro del código ni líneas en blanco dentro de una forma:
;;; así se puede incrustar en un .scr de Core Console para probarlo allí.

(vl-load-com)

;; Las 880 variables de sistema de AutoCAD 2027, sacadas el 2026-09-15 con
;; (setvar "QAFLAGS" 2) y SETVAR ? * en Core Console. En trozos: cada forma cabe
;; en una línea de un .scr.
(setq *amg:variables* nil)
(setq *amg:variables* (append *amg:variables* '("ACADLSPASDOC" "ACADPREFIX" "ACADVER" "ACTPATH" "ACTRECORDERSTATE" "ACTRECPATH" "ACTUI" "AEC3DDWFEDGE" "AECEIPINPROGRESS" "AECPSDAUTOATTACH" "AECPSDVISIBILITY" "AFLAGS" "ANGBASE" "ANGDIR" "ANNOALLVISIBLE" "ANNOAUTOSCALE" "ANNOMONITOR" "ANNOSCALEZOOM" "ANNOTATIVEDWG" "APBOX" "APERTURE" "APPAUTOLOAD" "AREA" "ARRAYCREATION" "ARRAYEDITSTATE" "ARRAYTYPE" "ASMOUTVER" "ATTDIA" "ATTIPE" "ATTMODE" "ATTMULTI" "ATTREQ" "AUDITCTL" "AUNITS" "AUPREC" "AUTODWFPUBLISH" "AUTOMATICPUB" "AUTOPLACEMENT" "AUTOSNAP" "BACKGROUNDPLOT" "BACKZ" "BACTIONBARMODE" "BACTIONCOLOR" "BCONSTATUSMODE" "BCONVERTLAYER" "BGCOREPUBLISH" "BGRIPOBJCOLOR" "BGRIPOBJSIZE" "BINDTYPE" "BLOCKCREATEMODE" "BLOCKEDITLOCK" "BLOCKEDITOR" "BLOCKMRULIST" "BLOCKNAVIGATE" "BLOCKSYNCFOLDER" "BLOCKTARGETCOLOR" "BLOCKTESTWINDOW" "BPARAMETERCOLOR" "BPARAMETERFONT" "BPARAMETERSIZE")))
(setq *amg:variables* (append *amg:variables* '("BPTEXTHORIZONTAL" "BTMARKDISPLAY" "BVMODE" "CACHEMAXFILES" "CALCINPUT" "CAMERADISPLAY" "CAMERAHEIGHT" "CANNOSCALE" "CANNOSCALEVALUE" "CBARTRANSPARENCY" "CCONSTRAINTFORM" "CDATE" "CDYNDISPLAYMODE" "CECOLOR" "CELTSCALE" "CELTYPE" "CELWEIGHT" "CENTERCROSSGAP" "CENTERCROSSSIZE" "CENTEREXE" "CENTERLAYER" "CENTERLTSCALE" "CENTERLTYPE" "CENTERLTYPEFILE" "CENTERMARKEXE" "CENTERMT" "CETRANSPARENCY" "CGEOCS" "CHAMFERA" "CHAMFERB" "CHAMFERC" "CHAMFERD" "CHAMMODE" "CHECKOUTFADECTL" "CIRCLERAD" "CLASSICKEYS" "CLAYER" "CLAYOUT" "CLEANSCREENSTATE" "CLIPROMPTLINES" "CLIPROMPTUPDATE" "CMATERIAL" "CMDACTIVE" "CMDDIA" "CMDECHO" "CMDNAMES" "CMFADECOLOR" "CMFADEOPACITY" "CMLEADERSTYLE" "CMLJUST" "CMLSCALE" "CMLSTYLE" "CMOSNAP" "COLORTHEME" "COMMANDPREVIEW" "COMMENTHIGHLIGHT" "COMPARECOLOR1" "COMPARECOLOR2" "COMPAREFRONT" "COMPAREHATCH")))
(setq *amg:variables* (append *amg:variables* '("COMPAREPROPS" "COMPARERCMARGIN" "COMPARERCSHAPE" "COMPARESHOW1" "COMPARESHOW2" "COMPARESHOWRC" "COMPARETEXT" "COMPARETOLERANCE" "COMPASS" "COMPLEXLTPREVIEW" "CONSTRAINTINFER" "CONSTRAINTRELAX" "COORDS" "COPYMODE" "COUNTCHECK" "COUNTCOLOR" "COUNTERRORCOLOR" "COUNTERRORNUM" "COUNTMODE" "COUNTNUMBER" "COUNTSERVICE" "CPLOTSTYLE" "CPROFILE" "CTAB" "CTABLESTYLE" "CULLINGOBJ" "CURSORBADGE" "CURSORSIZE" "CURSORTYPE" "CVIEWDETAILSTYLE" "CVPORT" "DATALINKNOTIFY" "DATE" "DBLCLKEDIT" "DBMOD" "DCSERVICESTATUS" "DCTCUST" "DCTMAIN" "DEFAULTGIZMO" "DEFAULTINDEX" "DEFAULTLIGHTING" "DEFLPLSTYLE" "DEFPLSTYLE" "DELOBJ" "DEMANDLOAD" "DGNFRAME" "DGNIMPORTMAX" "DGNIMPORTMODE" "DGNMAPPINGPATH" "DGNOSNAP" "DIASTAT" "DIGITIZER" "DIMADEC" "DIMALT" "DIMALTD" "DIMALTF" "DIMALTRND" "DIMALTTD" "DIMALTTZ" "DIMALTU")))
(setq *amg:variables* (append *amg:variables* '("DIMALTZ" "DIMANNO" "DIMAPOST" "DIMARCSYM" "DIMASO" "DIMASSOC" "DIMASZ" "DIMATFIT" "DIMAUNIT" "DIMAZIN" "DIMBLK" "DIMBLK1" "DIMBLK2" "DIMCEN" "DIMCLRD" "DIMCLRE" "DIMCLRT" "DIMCONTINUEMODE" "DIMDEC" "DIMDLE" "DIMDLI" "DIMDSEP" "DIMEXE" "DIMEXO" "DIMFIT" "DIMFRAC" "DIMFXL" "DIMFXLON" "DIMGAP" "DIMJOGANG" "DIMJUST" "DIMLAYER" "DIMLDRBLK" "DIMLFAC" "DIMLIM" "DIMLTEX1" "DIMLTEX2" "DIMLTYPE" "DIMLUNIT" "DIMLWD" "DIMLWE" "DIMPICKBOX" "DIMPOST" "DIMRND" "DIMSAH" "DIMSCALE" "DIMSD1" "DIMSD2" "DIMSE1" "DIMSE2" "DIMSHO" "DIMSOXD" "DIMSTYLE" "DIMTAD" "DIMTDEC" "DIMTFAC" "DIMTFILL" "DIMTFILLCLR" "DIMTIH" "DIMTIX")))
(setq *amg:variables* (append *amg:variables* '("DIMTM" "DIMTMOVE" "DIMTOFL" "DIMTOH" "DIMTOL" "DIMTOLJ" "DIMTP" "DIMTSZ" "DIMTVP" "DIMTXSTY" "DIMTXT" "DIMTXTDIRECTION" "DIMTXTRULER" "DIMTZIN" "DIMUNIT" "DIMUPT" "DIMZIN" "DISPSILH" "DISPSILHBLOCKS" "DISTANCE" "DIVMESHBOXHEIGHT" "DIVMESHBOXLENGTH" "DIVMESHBOXWIDTH" "DIVMESHCONEAXIS" "DIVMESHCONEBASE" "DIVMESHCYLAXIS" "DIVMESHCYLBASE" "DIVMESHCYLHEIGHT" "DIVMESHPYRBASE" "DIVMESHPYRHEIGHT" "DIVMESHPYRLENGTH" "DIVMESHTORUSPATH" "DIVMESHWEDGEBASE" "DONUTID" "DONUTOD" "DRAGCOLOR" "DRAGMODE" "DRAGP1" "DRAGP2" "DRAGVS" "DRAWORDERCTL" "DTEXTED" "DWFFRAME" "DWFOSNAP" "DWGCHECK" "DWGCODEPAGE" "DWGCOMPAREMODE" "DWGNAME" "DWGPREFIX" "DWGTITLED" "DXEVAL" "DYNDIGRIP" "DYNDIVIS" "DYNINFOTIPS" "DYNMODE" "DYNPICOORDS" "DYNPIFORMAT" "DYNPIVIS" "DYNPROMPT" "DYNTOOLTIPS")))
(setq *amg:variables* (append *amg:variables* '("EDGEMODE" "ELEVATION" "ENABLEDSTLOCK" "ENABLESYNCPDF" "ENTERPRISEMENU" "ERHIGHLIGHT" "EXPERT" "EXPLMODE" "EXPORTMODELSPACE" "EXPORTPAGESETUP" "EXPORTPAPERSPACE" "EXPVALUE" "EXPWHITEBALANCE" "EXTMAX" "EXTMIN" "EXTNAMES" "FACETERDEVNORMAL" "FACETERGRIDRATIO" "FACETERMAXGRID" "FACETERMESHTYPE" "FACETERMINUGRID" "FACETERMINVGRID" "FACETERSMOOTHLEV" "FACETRATIO" "FACETRES" "FASTSHADEDMODE" "FIELDDISPLAY" "FIELDEVAL" "FILEDIA" "FILETABPREVIEW" "FILETABSTATE" "FILLETPOLYARC" "FILLETRAD" "FILLETRAD3D" "FILLMODE" "FONTALT" "FONTMAP" "FRAME" "FRAMESELECTION" "FRONTZ" "FULLOPEN" "FULLPLOTPATH" "GALLERYVIEW" "GEOLATLONGFORMAT" "GEOLOCATEMODE" "GEOMAPMODE" "GFANG" "GFCLR1" "GFCLR2" "GFCLRLUM" "GFCLRSTATE" "GFNAME" "GFSHIFT" "GLOBALOPACITY" "GRIDDISPLAY" "GRIDMAJOR" "GRIDMODE" "GRIDSTYLE" "GRIDUNIT" "GRIPBLOCK")))
(setq *amg:variables* (append *amg:variables* '("GRIPCOLOR" "GRIPCONTOUR" "GRIPDYNCOLOR" "GRIPHOT" "GRIPHOVER" "GRIPOBJLIMIT" "GRIPS" "GRIPSIZE" "GRIPSUBOBJMODE" "GRIPTIPS" "GROUPDISPLAYMODE" "GSTHREADING" "GTAUTO" "GTDEFAULT" "GTLOCATION" "HALOGAP" "HANDLES" "HATCHBOUNDSET" "HATCHCREATION" "HATCHTYPE" "HELPPREFIX" "HIDETEXT" "HIDEXREFSCALES" "HIGHLIGHT" "HPANG" "HPANNOTATIVE" "HPASSOC" "HPBOUND" "HPBOUNDRETAIN" "HPCOLOR" "HPDLGMODE" "HPDOUBLE" "HPDRAWMODE" "HPDRAWORDER" "HPGAPTOL" "HPINHERIT" "HPLASTPATTERN" "HPLAYER" "HPLINETYPE" "HPMAXAREAS" "HPMAXLINES" "HPMAXLOOPS" "HPNAME" "HPOBJWARNING" "HPORIGIN" "HPORIGINMODE" "HPPATHALIGNMENT" "HPPATHWIDTH" "HPPICKMODE" "HPQUICKPREVIEW" "HPRELATIVEPS" "HPSCALE" "HPSEPARATE" "HPSPACE" "HPTRANSPARENCY" "HYPERLINKBASE" "IBLENVIRONMENT" "IMAGEASYNC" "IMAGEFRAME" "IMAGEHLT")))
(setq *amg:variables* (append *amg:variables* '("IMPLIEDFACE" "INDEXCTL" "INETLOCATION" "INPUTHISTORYMODE" "INPUTSEARCHDELAY" "INSBASE" "INSNAME" "INSUNITS" "INTERFERECOLOR" "INTERFEREOBJVS" "INTERFEREVPVS" "ISAVEBAK" "ISAVEPERCENT" "ISOLINES" "JIGZOOMMAX" "JIGZOOMMIN" "LASTANGLE" "LASTPOINT" "LASTPROMPT" "LATITUDE" "LAYERDLGMODE" "LAYEREVAL" "LAYEREVALCTL" "LAYERFILTERALERT" "LAYERNOTIFY" "LAYLOCKFADECTL" "LAYOUTREGENCTL" "LAYOUTTAB" "LEGACYCODESEARCH" "LEGACYCTRLPICK" "LENSLENGTH" "LIGHTINGUNITS" "LIGHTSINBLOCKS" "LIMCHECK" "LIMMAX" "LIMMIN" "LINEFADING" "LINEFADINGLEVEL" "LISPSYS" "LOCALE" "LOCALROOTPREFIX" "LOCKUI" "LOFTANG1" "LOFTANG2" "LOFTMAG1" "LOFTMAG2" "LOFTNORMALS" "LOFTPARAM" "LOGFILEMODE" "LOGFILENAME" "LOGFILEPATH" "LOGINNAME" "LONGITUDE" "LTGAPSELECTION" "LTSCALE" "LUNITS" "LUPREC" "LWDEFAULT" "LWDISPLAY" "LWUNITS")))
(setq *amg:variables* (append *amg:variables* '("MACRONOTIFY" "MARKUPASSISTMODE" "MAXACTVP" "MAXSORT" "MAXTOUCHES" "MBUTTONPAN" "MEASUREINIT" "MEASUREMENT" "MENUBAR" "MENUCTL" "MENUECHO" "MENUNAME" "MESHTYPE" "MIRRHATCH" "MIRRTEXT" "MLEADERLAYER" "MLEADERSCALE" "MODEMACRO" "MSLTSCALE" "MSOLESCALE" "MTEXTAUTOSTACK" "MTEXTCOLUMN" "MTEXTDETECTSPACE" "MTEXTED" "MTEXTEDENCODING" "MTEXTFIXED" "MTEXTTOOLBAR" "MTJIGSTRING" "MVIEWPREVIEW" "NAVBARDISPLAY" "NAVSWHEELMODE" "NAVSWHEELSIZEBIG" "NAVVCUBEDISPLAY" "NAVVCUBELOCATION" "NAVVCUBEOPACITY" "NAVVCUBEORIENT" "NAVVCUBESIZE" "NOMUTT" "NORTHDIRECTION" "OBSCUREDCOLOR" "OBSCUREDLTYPE" "OFFSETDIST" "OFFSETGAPTYPE" "OLEFRAME" "OLEHIDE" "OLEQUALITY" "OLESTARTUP" "ONLINEUSERID" "ONLINEUSERNAME" "ORBITAUTOTARGET" "ORTHOMODE" "OSMODE" "OSNAPCOORD" "OSNAPHATCH" "OSNAPZ" "OSOPTIONS" "PALETTEOPAQUE" "PAPERUPDATE" "PASTESPECMODE" "PCMSTATE")))
(setq *amg:variables* (append *amg:variables* '("PDFFRAME" "PDFIMPORTFILTER" "PDFIMPORTLAYERS" "PDFIMPORTMODE" "PDFOSNAP" "PDFSHX" "PDMODE" "PDSIZE" "PEDITACCEPT" "PELLIPSE" "PERIMETER" "PERSPECTIVE" "PERSPECTIVECLIP" "PFACEVMAX" "PICKADD" "PICKAUTO" "PICKBOX" "PICKDRAG" "PICKFIRST" "PICKSTYLE" "PLATFORM" "PLINECONVERTMODE" "PLINEGCENMAX" "PLINEGEN" "PLINETYPE" "PLINEWID" "PLOTOFFSET" "PLOTROTMODE" "PLQUIET" "POINTCLOUDLOD" "POLARADDANG" "POLARANG" "POLARDIST" "POLARMODE" "POLYSIDES" "POPUPS" "PREVIEWDELAY" "PREVIEWFILTER" "PREVIEWTYPE" "PROJECTAWARE" "PROJECTNAME" "PROJMODE" "PROPERTYPREVIEW" "PROPOBJLIMIT" "PROPPREVTIMEOUT" "PROXYGRAPHICS" "PROXYNOTICE" "PROXYSHOW" "PSLTSCALE" "PSOLHEIGHT" "PSOLWIDTH" "PSPROLOG" "PSQUALITY" "PSTYLEMODE" "PSTYLEPOLICY" "PSVPSCALE" "PUBLISHALLSHEETS" "PUBLISHCOLLATE" "PUBLISHHATCH" "PUCSBASE")))
(setq *amg:variables* (append *amg:variables* '("QPLOCATION" "QPMODE" "QTEXTMODE" "QVDRAWINGPIN" "QVLAYOUTPIN" "RASTERDPI" "RASTERPERCENT" "RASTERTHRESHOLD" "REBUILD2DCV" "REBUILD2DDEGREE" "REBUILD2DOPTION" "REBUILDDEGREEU" "REBUILDDEGREEV" "REBUILDOPTIONS" "REBUILDU" "REBUILDV" "RECOVERAUTO" "RECOVERYMODE" "REFEDITNAME" "REFPATHTYPE" "REGENMODE" "REMEMBERFOLDERS" "RENDERLEVEL" "RENDERLIGHTCALC" "RENDERTARGET" "RENDERTIME" "RENDERUSERLIGHTS" "REPORTERROR" "REVCLOUDGRIPS" "REVCLOUDLAYER" "RIBBONBGLOAD" "RIBBONICONRESIZE" "RIBBONSELECTMODE" "RIBBONSTATE" "ROLLOVEROPACITY" "ROLLOVERTIPS" "RTDISPLAY" "RTREGENAUTO" "SAFEMODE" "SAVEFIDELITY" "SAVEFILE" "SAVEFILEPATH" "SAVENAME" "SAVETIME" "SCREENBOXES" "SCREENMODE" "SCREENSIZE" "SECTIONOFFSETINC" "SECURELOAD" "SELECTIONAREA" "SELECTIONCYCLING" "SELECTIONEFFECT" "SELECTIONPREVIEW" "SETBYLAYERMODE" "SHADEDGE" "SHADEDIF" "SHORTCUTMENU" "SHOWHIST" "SHOWLAYERUSAGE" "SHOWMOTIONPIN")))
(setq *amg:variables* (append *amg:variables* '("SHPNAME" "SIGWARN" "SKETCHHLWIDTH" "SKETCHINC" "SKPOLY" "SKTOLERANCE" "SKYSTATUS" "SMOOTHMESHGRID" "SMOOTHMESHMAXLEV" "SMSTATE" "SNAPANG" "SNAPBASE" "SNAPGRIDLEGACY" "SNAPISOPAIR" "SNAPMODE" "SNAPSTYL" "SNAPTYPE" "SNAPUNIT" "SOLIDCHECK" "SOLIDHIST" "SORTENTS" "SORTORDER" "SPLDEGREE" "SPLFRAME" "SPLINE_FASTDRAW" "SPLINESEGS" "SPLINETYPE" "SPLKNOTS" "SPLMETHOD" "SPLPERIODIC" "SSFOUND" "SSLOCATE" "SSMAUTOOPEN" "SSMOPENMODE" "SSMPOLLTIME" "SSMSHEETSTATUS" "STARTINFOLDER" "STARTMODE" "STARTUP" "STATUSBAR" "STEPSIZE" "STEPSPERSEC" "STUDENTDRAWING" "SUNSTATUS" "SUPPRESSALERTS" "SURFACEAUTOTRIM" "SURFTAB1" "SURFTAB2" "SURFTYPE" "SURFU" "SURFV" "SYSCODEPAGE" "SYSFLOATING" "SYSMON" "TABLEINDICATOR" "TABLELAYER" "TABLETOOLBAR" "TABMODE" "TARGET" "TBSHOWSHORTCUTS")))
(setq *amg:variables* (append *amg:variables* '("TDCREATE" "TDINDWG" "TDUCREATE" "TDUPDATE" "TDUSRTIMER" "TDUUPDATE" "TEMPOVERRIDES" "TEMPPREFIX" "TEXTALIGNMODE" "TEXTALIGNSPACING" "TEXTALLCAPS" "TEXTED" "TEXTEDITMODE" "TEXTEDITOR" "TEXTEVAL" "TEXTFILL" "TEXTGAPSELECTION" "TEXTJUSTIFY" "TEXTLAYER" "TEXTQLTY" "TEXTSIZE" "TEXTSTYLE" "TEXTTOATTRIBUTE" "THICKNESS" "THUMBSAVE" "THUMBSIZE" "THUMBSIZE2D" "TILEMODE" "TIMEZONE" "TOOLTIPMERGE" "TOOLTIPS" "TOOLTIPSIZE" "TOUCHMODE" "TRACEFADECTL" "TRACEOSNAP" "TRACEPAPERCTL" "TRACEVPSUPPORT" "TRACKPATH" "TRAYICONS" "TRAYNOTIFY" "TRAYTIMEOUT" "TREEDEPTH" "TREEMAX" "TRIMEDGES" "TRIMEXTENDMODE" "TRIMMODE" "TRUSTEDDOMAINS" "TRUSTEDPATHS" "TSPACEFAC" "TSPACETYPE" "TSTACKALIGN" "TSTACKSIZE" "UCSAXISANG" "UCSBASE" "UCSDETECT" "UCSFOLLOW" "UCSICON" "UCSNAME" "UCSORG" "UCSORTHO")))
(setq *amg:variables* (append *amg:variables* '("UCSSELECTMODE" "UCSVIEW" "UCSVP" "UCSXDIR" "UCSYDIR" "UNDOCTL" "UNDOMARKS" "UNITMODE" "UOSNAP" "UPDATETHUMBNAIL" "USERNAME" "VIEWBACKSTATUS" "VIEWCREATION" "VIEWCTR" "VIEWDETAILEDITOR" "VIEWDIR" "VIEWEDITOR" "VIEWFWDSTATUS" "VIEWMODE" "VIEWPORTLAYER" "VIEWSIZE" "VIEWSKETCHMODE" "VIEWTWIST" "VIEWUPDATEAUTO" "VISRETAIN" "VISRETAINMODE" "VPCONTROL" "VPLAYEROVERRIDES" "VPMAXIMIZEDSTATE" "VPROTATEASSOC" "VSACURVATUREHIGH" "VSACURVATURELOW" "VSACURVATURETYPE" "VSADRAFTANGLELOW" "VSAZEBRACOLOR1" "VSAZEBRACOLOR2" "VSAZEBRASIZE" "VSAZEBRATYPE" "VSBACKGROUNDS" "VSEDGECOLOR" "VSEDGEJITTER" "VSEDGELEX" "VSEDGEOVERHANG" "VSEDGES" "VSEDGESMOOTH" "VSFACECOLORMODE" "VSFACEHIGHLIGHT" "VSFACEOPACITY" "VSFACESTYLE" "VSHALOGAP" "VSHIDEPRECISION" "VSISOONTOP" "VSMATERIALMODE" "VSMAX" "VSMIN" "VSMONOCOLOR" "VSOBSCUREDCOLOR" "VSOBSCUREDEDGES" "VSOBSCUREDLTYPE" "VSOCCLUDEDCOLOR")))
(setq *amg:variables* (append *amg:variables* '("VSOCCLUDEDEDGES" "VSOCCLUDEDLTYPE" "VSSHADOWS" "VSSILHEDGES" "VSSILHWIDTH" "VTDURATION" "VTENABLE" "VTFPS" "WBDEFAULTBROWSER" "WBHELPONLINE" "WBHELPTYPE" "WBLOCKCREATEMODE" "WINDOWAREACOLOR" "WIPEOUTFRAME" "WMFBKGND" "WMFFOREGND" "WORKINGFOLDER" "WORKSPACELABEL" "WORLDUCS" "WORLDVIEW" "WRITESTAT" "WSAUTOSAVE" "WSCURRENT" "XCLIPFRAME" "XCOMPAREBAKPATH" "XCOMPAREBAKSIZE" "XCOMPAREENABLE" "XDWGFADECTL" "XEDIT" "XFADECTL" "XLOADCTL" "XLOADPATH" "XREFCTL" "XREFLAYER" "XREFNOTIFY" "XREFOVERRIDE" "XREFREGAPPCTL" "XREFTYPE" "ZOOMFACTOR" "ZOOMWHEEL")))

;; Cambian solas o por el mero hecho de teclear un comando. No dicen nada de
;; lo que deja ArchMuse. Cada una con su motivo.
(setq *amg:por-el-reloj*
  '(("DATE" . "la hora")
    ("CDATE" . "la hora")
    ("MILLISECS" . "la hora")
    ("TDUSRTIMER" . "el cronómetro del dibujo")
    ("TDINDWG" . "el tiempo total de edición")
    ("TDUPDATE" . "la hora de la última actualización")
    ("LASTPROMPT" . "la última línea de la línea de comandos")
    ("CMDNAMES" . "el comando en curso")
    ("ERRNO" . "el código del último error de una función de AutoLISP")))

;; Cambian si ArchMuse dibuja, y es lo que tiene que pasar. Tras un Esc o un
;; fallo tampoco dicen nada: deshacer deja el dibujo marcado como modificado.
(setq *amg:por-lo-dibujado*
  '(("DBMOD" . "el dibujo se ha modificado")
    ("EXTMIN" . "los límites del dibujo")
    ("EXTMAX" . "los límites del dibujo")
    ("HANDSEED" . "el siguiente identificador de objeto")
    ("VSMIN" . "la zona regenerada")
    ("VSMAX" . "la zona regenerada")
    ("LASTPOINT" . "el punto que se marca para el cuadro")))

;; *amg:foto* NO se pone a nil al cargar (2026-09-15). Volver a cargar el
;; guardián entre los dos pasos convertía el segundo ARCHMUSE-GUARDIAN en otra
;; foto de antes, que no compara ni deja informe: de dos pasadas de Pablo no
;; quedó informe, y es la causa probable, sin medir.

(defun amg:valor (r)
  (if (vl-catch-all-error-p r) "<no se puede leer>" r))

;; Sin vlax-product-key no hay registro que leer, y se dice en el informe. Se
;; mira si la función existe ANTES de llamarla: en Core Console no existe, y
;; vl-catch-all-apply no atrapa una función sin definir (medido el 2026-09-15:
;; abortaba la foto entera).
(defun amg:claves-del-registro ( / producto)
  (setq producto (if (member (type vlax-product-key) '(SUBR EXRXSUBR))
                   (vl-catch-all-apply 'vlax-product-key nil)
                   nil))
  (if (or (null producto) (vl-catch-all-error-p producto))
    nil
    (list (strcat "HKEY_CURRENT_USER\\" producto "\\FixedProfile\\General Configuration")
          (strcat "HKEY_CURRENT_USER\\" producto "\\Profiles\\" (getvar "CPROFILE") "\\Variables"))))

(defun amg:foto-del-registro ( / res nombres)
  (setq res nil)
  (foreach clave (amg:claves-del-registro)
    (setq nombres (vl-catch-all-apply 'vl-registry-descendents (list clave T)))
    (if (and nombres (not (vl-catch-all-error-p nombres)))
      (foreach nombre nombres
        (setq res (cons (cons (strcat clave " : " nombre)
                              (amg:valor (vl-catch-all-apply 'vl-registry-read (list clave nombre))))
                        res)))))
  (reverse res))

(defun amg:foto ( / vars)
  (setq vars nil)
  (foreach n *amg:variables*
    (setq vars (cons (cons n (amg:valor (vl-catch-all-apply 'getvar (list n)))) vars)))
  (list (reverse vars) (amg:foto-del-registro)))

(defun amg:texto (v)
  (cond ((null v) "nil")
        ((= (type v) 'STR) (strcat "\"" v "\""))
        ((= (type v) 'INT) (itoa v))
        ((= (type v) 'REAL) (rtos v 2 6))
        (T (vl-princ-to-string v))))

(defun amg:diferencias (antes despues / res d)
  (setq res nil)
  (foreach par antes
    (setq d (assoc (car par) despues))
    (if (not (equal (cdr par) (cdr d) 1e-9))
      (setq res (cons (list (car par) (cdr par) (cdr d)) res))))
  (foreach par despues
    (if (null (assoc (car par) antes))
      (setq res (cons (list (car par) nil (cdr par)) res))))
  (reverse res))

(defun amg:linea (d)
  (strcat "  " (car d) ": " (amg:texto (cadr d)) " -> " (amg:texto (caddr d))))

(defun amg:informe (lineas / ruta f)
  (setq ruta (strcat (getenv "TEMP") "\\archmuse-guardian-"
                     (menucmd "M=$(edtime,$(getvar,date),YYYYMODD-HHMMSS)") ".txt"))
  (setq f (vl-catch-all-apply 'open (list ruta "w")))
  (if (and f (not (vl-catch-all-error-p f)))
    (progn
      (foreach l lineas (write-line l f))
      (close f)
      ruta)
    nil))

(defun c:ARCHMUSE-GUARDIAN ( / despues vars reg malas dibujo reloj lineas ruta)
  (if (null *amg:foto*)
    (progn
      (setq *amg:foto* (amg:foto))
      (princ (strcat "\nGuardián: foto de antes hecha, "
                     (itoa (length (car *amg:foto*))) " variables y "
                     (itoa (length (cadr *amg:foto*))) " valores del registro."))
      (princ "\n  Ahora teclea ARCHMUSE y úsalo como quieras probar: hasta el final, o con Esc.")
      (princ "\n  Sin otros comandos entre medias. Después, ARCHMUSE-GUARDIAN otra vez."))
    (progn
      (setq despues (amg:foto)
            vars    (amg:diferencias (car *amg:foto*) (car despues))
            reg     (amg:diferencias (cadr *amg:foto*) (cadr despues))
            malas nil dibujo nil reloj nil)
      (setq *amg:foto* nil)
      (foreach d vars
        (cond ((assoc (car d) *amg:por-el-reloj*) (setq reloj (cons d reloj)))
              ((assoc (car d) *amg:por-lo-dibujado*) (setq dibujo (cons d dibujo)))
              (T (setq malas (cons d malas)))))
      (setq lineas (list (strcat "ArchMuse · guardián · "
                                 (menucmd "M=$(edtime,$(getvar,date),YYYY-MO-DD HH:MM:SS)"))
                         (strcat "Dibujo: " (getvar "DWGNAME"))
                         ""
                         (if (or malas reg)
                           "RESULTADO: AutoCAD NO está como estaba."
                           "RESULTADO: AutoCAD está exactamente como estaba.")))
      (if malas
        (setq lineas (append lineas (list "" "Variables cambiadas:")
                             (mapcar 'amg:linea (reverse malas)))))
      (if reg
        (setq lineas (append lineas (list "" "Registro cambiado:")
                             (mapcar 'amg:linea reg))))
      (if dibujo
        (setq lineas (append lineas (list "" "Cambios de haber dibujado, esperables, no cuentan:")
                             (mapcar '(lambda (d)
                                        (strcat (amg:linea d) "   (" (cdr (assoc (car d) *amg:por-lo-dibujado*)) ")"))
                                     (reverse dibujo)))))
      (setq lineas (append lineas (list "" (strcat "Ignoradas por cambiar solas: " (itoa (length reloj))))))
      (foreach l lineas (princ (strcat "\n" l)))
      (setq ruta (amg:informe lineas))
      (if ruta (princ (strcat "\n\nInforme en: " ruta)))))
  (princ))

(princ "\nGuardián de ArchMuse cargado. Teclea ARCHMUSE-GUARDIAN para la foto de antes.")
(princ)
