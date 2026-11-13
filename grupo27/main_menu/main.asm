
.ORIG x3000
BR main

;   ============================================================================
;       Programa de ENTRADA para pruebas del menu
;       *****************************************
;   ============================================================================
;
;   Metodologia:
;       Se puede probar el menu, de ditintas maneras:
;       -   Prueba de unicamente la interfaz (SIN SUBRUTINAS EXTERNAS).
;       -   Prueba de unicamente la interfaz en modo automatico (SIN SUBRUTINAS EXTERNAS).
;       -   Prueba con subrutinas externas.
;       -   Prueba con subrutinas externas en modo automatico.
;      
;
;   (!) Para que se carguen correctamente las SUBRUTINAS EXTERNAS, tiene que estar *logeado*
;   con alguna cuenta (ya sea de grupo o administrador) y darle a *Ensamblar*.
;
;   (!) Para cambiar entre prueba SIN y CON SUBRUTINAS EXTERNAS, comente y descomente las
;   siguientes lineas:

; .EXTERNAL MAIN_MENU-MAIN_MENU                               ; <- Pruebas unicamente la interfaz.
; sub_main_menu       .FILL MAIN_MENU-MAIN_MENU               ; <- *

.EXTERNAL MAIN_MENU_PROGRESO-MAIN_MENU                      ; <- Pruebas con subrutinas externas.
sub_main_menu       .FILL MAIN_MENU_PROGRESO-MAIN_MENU      ; <- * 


;   (!) Para cambiar entre modo Mostrar interfaz, y modo Automatico, comente y descomente las
;   siguientes lineas:

main
    AND R0 R0 #0                    ; <- 0 es nullptr (osea mostrar el menu normalmente)
    ; LEA R0 programa_del_menu        ; <- ptr (es para que automaticamente corra el programa de abajo)

    LD R1 sub_main_menu
    JSRR R1
    HALT


;   (i) Bloque de Operaciones para correr AUTOMATICAMENTE en el menu:
;   (vea archivo 'como_programar_bloque_automatizacion.asm' el grupo 27 para mas info).

programa_del_menu
    .FILL   #1      ;   modo verboso (muestra todos los valores por consola)
    
    .FILL   #15     ;   MULTIPLICACION BOOTH        (Indice de operacion)
    .FILL   x0500   ;   Valor 5                     (Q7.8)
    .FILL   xF400   ;   Valor -12                   (Q7.8)
    .FILL   #0      ;   Espacio para el resultado   (Q7.8)
    .FILL   #0      ;   Espacio para el resultado   (Quedara en blanco)
    
    .FILL   #9      ;   SQRT NEWTONRAPHSON          (Indice de operacion)
    .FILL   x0002   ;   Valor 2.0                   (Q15.16) 
    .FILL   x0000   ;   *                           (DQ16 usa 2 WORD)
    .FILL   #0      ;   Espacio para el resultado   (Q15.16)
    .FILL   #0      ;   *                           (DQ16 usa 2 WORD)

    .FILL   #5      ;   COSENO TABLA                (Indice de operacion)
    .FILL   x1921   ;   Valor 1.5708                (Q3.12)
    .FILL   #0      ;   *                           (Usa un solo operando)
    .FILL   #0      ;   Espacio para el resultado   (Q1.14)
    .FILL   #0      ;   Espacio para el resultado   (Quedara en blanco)

    .FILL   #0      ;   SALIR



.END