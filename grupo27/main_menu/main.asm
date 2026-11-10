

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



.END