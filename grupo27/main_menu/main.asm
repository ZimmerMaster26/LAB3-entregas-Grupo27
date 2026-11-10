

;
;   Programa principal, para probar el funcionamiento de la subrutina MAIN_MENU.
;   (Se puede usar la subrutina MAIN_MENU desde otro programa que no sea este si es necesario).
;

.ORIG x3000
BR main


;   **Solo para los ADMINISTRADOR**
;   Cambiar la subrutina de MAIN_MENU, por la de MAIN_MENU_PROGRESO:
;   -   Comentar las dos lineas de abajo.
;   -   Descomentar las dos siguientes.
;   -   Compilar.

.EXTERNAL MAIN_MENU-MAIN_MENU
sub_main_menu       .FILL MAIN_MENU-MAIN_MENU

;.EXTERNAL MAIN_MENU_PROGRESO-MAIN_MENU
;sub_main_menu       .FILL MAIN_MENU_PROGRESO-MAIN_MENU

main

    AND R0 R0 #0
    LD R1 sub_main_menu
    JSRR R1
    HALT


programa_del_menu
    .FILL   #1      ;   modo verboso (muestra todos los valores por consola)
    
    .FILL   #7      ;   MULTIPLICACION
    .FILL   #2      ;   MULTIPLICACION BOOTH
    .FILL   x0500   ;   (Q7.8) valor a (5)
    .FILL   xF400   ;   (Q7.8) valor b (-12)
    .FILL   #0      ;   (Q7.8) espacio para el resultado.
    
    .FILL   #4      ;   SQRT
    .FILL   #1      ;   SQRT NEWTONRAPHSON
    .FILL   x0002   ;   
    .FILL   x0000   ;   (Q15.16 usa 2 WORD) valor a (2.0)
    .FILL   #0      ;   
    .FILL   #0      ;   (Q15.16 usa 2 WORD) espacio para resultado.

    .FILL   #2      ;   COS TABLE
    .FILL   x1921   ;   (Q3.12) valor a (1.5708)
    .FILL   #0      ;   (Q1.14) espacio para el resultado.

    .FILL   #14     ;   SALIR



.END