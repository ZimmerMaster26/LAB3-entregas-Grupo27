

.EXTERNAL GETCFILTERED-GETCFILTERED
.EXTERNAL FROMHEX-FROMHEX
.EXTERNAL PAUSE-PAUSE

.EXTERNAL FROM_QM_N-FROM_QM_N

.EXTERNAL GETVAL-GETVAL         
.EXTERNAL GETVAL_INT-GETVAL_INT 
.EXTERNAL GETVAL_QM_N-GETVAL_QM_N   
.EXTERNAL OUTVAL-OUTVAL


;   Como es un programa muy extenso, las variables estan en un punto medio para aprovechar el PCoffset



;   ============================================================================
;   Subrutina: MAIN_MENU
;       Interfaz que permite seleccionar las funciones de la calculadora asi
;       como sus operandos, y llama a las subrutinas de dichas funciones.
;
;       Implementa una maquina de estados, que recorre NODOS los cuales tienen
;       toda la informacion relevante para ejecutarce (interactuar con un menu,
;       obtener datos y llamar a subrutina, entre otros).
; 
;       La estructura interna de cada NODO es la siguiente:
;       0 - Puntero al controlador (funcion que se encarga de procesar el nodo).
;       1 - Puntero al Texto (Titulo y menu a mostrar).
;       2 - Puntero al Filtro (Teclas validas en las opciones del menu).
;       3 - Puntero al Vector de nodos Siguientes (Corresponde con la opcion del menu).
;       4 - Puntero a Direccion de la Subrutina (Subrutina a llamar).
;
;       (No todos los controladores utilizan todos los datos, por ejemplo el
;       controlador de menus utiliza todos menos la Subrutina, el de obtener un decimal
;       y llamar a subrutina utiliza todos menos el filtro, etc.)
;   ============================================================================

MAIN_MENU                               ;
    ST R0 main_menu_r0                  ;
    ST R1 main_menu_r1                  ;
    ST R2 main_menu_r2                  ;
    ST R3 main_menu_r3                  ;
    ST R4 main_menu_r4                  ;
    ST R5 main_menu_r5                  ;
    ST R7 main_menu_r7                  ;

    LD R0 main_menu_state_initial       ;   
    ST R0 main_menu_state               ;   [estado] = init
    LDR R0 R0 #0                        ;
    JMP R0                              ;   goto init.controlador


;   ==- Cambio de estado al siguiente nodo -====================================
;   !! ANTES DE SALTAR AQUI, [R0] next_offset
main_menu_swap_node                     ;  
    LD R5 main_menu_state               ;   [R5] nodo = [estado]
    LDR R1 R5 #3                        ;
    ADD R1 R1 R0                        ;   
    LDR R5 R1 #0                        ;   nodo = (nodo.next).peek(next_offset)
    ST R5 main_menu_state               ;   [estado] = nodo
    LDR R0 R5 #0                        ;
    JMP R0                              ;   goto nodo.controlador


;   ==- Return -================================================================
main_menu_return                        ;
    LD R0 main_menu_r0                  ;
    LD R1 main_menu_r1                  ;
    LD R2 main_menu_r2                  ;
    LD R3 main_menu_r3                  ;
    LD R4 main_menu_r4                  ;
    LD R5 main_menu_r5                  ;
    LD R7 main_menu_r7                  ;
    RET                                 ;


;   ==- Controlador para mostrar menus -========================================
main_menu_show_menu                     ;
    LD R5 main_menu_state               ;   [R5] nodo = [estado]
    LDR R0 R5 #1                        ;  
    PUTS                                ;   print(nodo.texto)

    LDR R0 R5 #2                        ;
    LD R1 sub_getcfiltered              ;
    JSRR R1                             ;   [R0] char = getcfiltered(nodo.filtro)

    LEA R1 main_menu_aux_0              ;
    STR R0 R1 #0                        ;
    AND R0 R0 #0                        ;
    STR R0 R1 #1                        ;
    ADD R0 R1 #0                        ;   [R0] buffer = char + '\0'
    LD R1 sub_fromhex                   ;
    JSRR R1                             ;   [R0] valor = fromhex(buffer) # (tambien cambia [R5] banderas de error)

    BR main_menu_swap_node              ;   # Cambio de nodo (offset = valor)


;   ==- Controlador subrutinas de un entero (no muestra resultado) -============
main_menu_one_int_noresult
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_inta         ;
    PUTS                                ;   print(" a (int) > ")

    LD R2 sub_getval_int                ;
    JSRR R2                             ;   [R0] = getval_int()

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   node.subrutina(value_a)

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   swap_node(offset = 0)


;   ==- Controlador subrutinas de un entero  -==================================
main_menu_one_int
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_inta         ;
    PUTS                                ;   print(" a (int) > ")
    LD R0 sub_getval_int                ;
    JSRR R0                             ;   [R0] = getval_int()

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_int          ;
    PUTS                                ;   print("(int) ")

    LD R0 main_menu_aux_0               ;
    AND R1 R1 #0                        ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(result)

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   swap_node(offset = 0)


;   ==- Controlador subrutinas de dos enteros  -================================
main_menu_two_int
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_inta         ;
    PUTS                                ;   print(" a (int) > ")
    LD R0 sub_getval_int                ;
    JSRR R0                             ;   [R0] = getval_int()

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_intb         ;
    PUTS                                ;   print(" b (int) > ")
    LD R0 sub_getval_int                ;
    JSRR R0                             ;   [R0] = getval_int()

    ADD R1 R0 #0                        ;
    LD R0 main_menu_aux_0               ;

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a, value_b)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_int          ;
    PUTS                                ;   print("(int) ")

    LD R0 main_menu_aux_0               ;
    AND R1 R1 #0                        ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(result)

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   swap_node(offset = 0)


;   ==- Controlador subrutinas de un Q3.12 -====================================
main_menu_one_q12
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_q12a         ;
    PUTS                                ;   print("a (Q3.12) > ")
    LD R0 main_menu_12                  ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(12)

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q12          ;
    PUTS                                ;   print("(Q3.12) ")

    LD R0 main_menu_aux_0               ;
    LD R1 main_menu_12                  ;
    LD R2 sub_from_qm_n                 ;
    JSRR R2                             ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(fromQm_n(result, 12))

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   # Cambio de nodo (offset = 0)


;   ==- Controlador subrutinas de un Q3.12 con resultado en Q1.14 -=============
main_menu_one_q12_result_q8
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_q12a         ;
    PUTS                                ;   print("a (Q3.12) > ")
    LD R0 main_menu_12                  ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(12)

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q8           ;
    PUTS                                ;   print("(Q7.8) ")
    
    LD R0 main_menu_aux_0               ;
    LD R1 main_menu_8                   ;
    LD R2 sub_from_qm_n                 ;
    JSRR R2                             ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(fromQm_n(result, 8))

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   # Cambio de nodo (offset = 0)


;   ==- Controlador subrutinas de un Q3.12 con resultado en Q1.14 -=============
main_menu_one_q12_result_q14
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_q12a         ;
    PUTS                                ;   print("a (Q3.12) > ")
    LD R0 main_menu_12                  ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(12)

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q14          ;
    PUTS                                ;   print("(Q1.14) ")
    
    LD R0 main_menu_aux_0               ;
    LD R1 main_menu_14                  ;
    LD R2 sub_from_qm_n                 ;
    JSRR R2                             ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(fromQm_n(result, 14))

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   # Cambio de nodo (offset = 0)




;   ==- Controlador subrutinas de un Q7.8 -=====================================
main_menu_one_q8
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_q8a          ;
    PUTS                                ;   print("a (Q7.8) > ")
    LD R0 main_menu_8                   ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(8)

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q8           ;
    PUTS                                ;   print("(Q7.8) ")

    LD R0 main_menu_aux_0               ;
    LD R1 main_menu_8                   ;
    LD R2 sub_from_qm_n                 ;
    JSRR R2                             ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(fromQm_n(result, 8))

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    BR main_menu_swap_node              ;   # Cambio de nodo (offset = 0)


;   ============================================================================
;   ==- Variables -=============================================================

main_menu_r0                .FILL #0
main_menu_r1                .FILL #0
main_menu_r2                .FILL #0
main_menu_r3                .FILL #0
main_menu_r4                .FILL #0
main_menu_r5                .FILL #0
main_menu_r7                .FILL #0
main_menu_state_initial     .FILL main_menu_init
main_menu_state             .FILL #0
main_menu_prompt_inta       .FILL main_menu_prompt_inta_text 
main_menu_prompt_intb       .FILL main_menu_prompt_intb_text 
main_menu_prompt_int        .FILL main_menu_prompt_int_text  
main_menu_prompt_q8a        .FILL main_menu_prompt_q8a_text  
main_menu_prompt_q8b        .FILL main_menu_prompt_q8b_text  
main_menu_prompt_q8         .FILL main_menu_prompt_q8_text   
main_menu_prompt_q12a       .FILL main_menu_prompt_q12a_text 
main_menu_prompt_q12b       .FILL main_menu_prompt_q12b_text 
main_menu_prompt_q12        .FILL main_menu_prompt_q12_text  
main_menu_prompt_q14        .FILL main_menu_prompt_q14_text  
main_menu_prompt_q15a       .FILL main_menu_prompt_q15a_text 
main_menu_prompt_q15b       .FILL main_menu_prompt_q15b_text 
main_menu_prompt_q15        .FILL main_menu_prompt_q15_text  
main_menu_prompt_dq16a      .FILL main_menu_prompt_dq16a_text
main_menu_prompt_dq16b      .FILL main_menu_prompt_dq16b_text
main_menu_prompt_dq16       .FILL main_menu_prompt_dq16_text 
main_menu_8                 .FILL #8
main_menu_12                .FILL #12
main_menu_14                .FILL #14
main_menu_15                .FILL #15
main_menu_aux_0             .FILL #0
main_menu_aux_1             .FILL #0

main_menu_swap_node_ads     .FILL main_menu_swap_node

sub_getcfiltered            .FILL GETCFILTERED-GETCFILTERED
sub_fromhex                 .FILL FROMHEX-FROMHEX
sub_pause                   .FILL PAUSE-PAUSE

sub_from_qm_n               .FILL FROM_QM_N-FROM_QM_N

sub_getval                  .FILL GETVAL-GETVAL
sub_getval_int              .FILL GETVAL_INT-GETVAL_INT
sub_getval_qm_n             .FILL GETVAL_QM_N-GETVAL_QM_N
sub_outval                  .FILL OUTVAL-OUTVAL


;   ==- Controlador subrutinas de dos Q7.8 -====================================
main_menu_two_q8
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_q8a          ;
    PUTS                                ;   print("a (Q7.8) > ")
    LD R0 main_menu_8                   ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(8)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q8b          ;
    PUTS                                ;   print("b (Q7.8) > ")
    LD R0 main_menu_8                   ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(8)

    ADD R1 R0 #0                        ;
    LD R0 main_menu_aux_0               ;

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a, value_b)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q8           ;
    PUTS                                ;   print("(Q7.8) ")

    LD R0 main_menu_aux_0               ;
    LD R1 main_menu_8                   ;
    LD R2 sub_from_qm_n                 ;
    JSRR R2                             ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(fromQm_n(result, 8))

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    LD R1 main_menu_swap_node_ads       ;
    JMP R1                              ;   # Cambio de nodo (offset = 0)


;   ==- Controlador subrutinas de dos Q0.15 -===================================
main_menu_two_q15
    LD R5 main_menu_state               ;   [R5] nodo = [estado]

    LDR R0 R5 #1                        ;
    PUTS                                ;   print(nodo.texto)

    LD R0 main_menu_prompt_q15a         ;
    PUTS                                ;   print("a (Q0.15) > ")
    LD R0 main_menu_15                  ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(15)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q15b         ;
    PUTS                                ;   print("b (Q0.15) > ")
    LD R0 main_menu_15                  ;
    LD R2 sub_getval_qm_n               ;
    JSRR R2                             ;   [R0] = getval_Qm_n(15)

    ADD R1 R0 #0                        ;
    LD R0 main_menu_aux_0               ;

    LDR R2 R5 #4                        ;
    LDR R2 R2 #0                        ;
    JSRR R2                             ;   [R0] result = node.subrutina(value_a, value_b)

    ST R0 main_menu_aux_0               ;

    LD R0 main_menu_prompt_q15          ;
    PUTS                                ;   print("(Q0.15) ")

    LD R0 main_menu_aux_0               ;
    LD R1 main_menu_15                  ;
    LD R2 sub_from_qm_n                 ;
    JSRR R2                             ;
    LD R2 sub_outval                    ;
    JSRR R2                             ;   outval(fromQm_n(result, 15))

    LD R0 sub_pause                     ;
    JSRR R0                             ;   pause()

    AND R0 R0 #0                        ;
    LD R1 main_menu_swap_node_ads       ;
    JMP R1                              ;   # Cambio de nodo (offset = 0)



;   ============================================================================
;   ==- Prompt texts -==========================================================

main_menu_prompt_inta_text  .STRINGZ " a (int) > "
main_menu_prompt_intb_text  .STRINGZ " b (int) > "
main_menu_prompt_int_text   .STRINGZ "(int) "
main_menu_prompt_q8a_text   .STRINGZ " a (Q7.8) > "
main_menu_prompt_q8b_text   .STRINGZ " b (Q7.8) > "
main_menu_prompt_q8_text    .STRINGZ "(Q7.8) "
main_menu_prompt_q12a_text  .STRINGZ " a (Q3.12) > "
main_menu_prompt_q12b_text  .STRINGZ " b (Q3.12) > "
main_menu_prompt_q12_text   .STRINGZ "(Q3.12) "
main_menu_prompt_q14_text   .STRINGZ "(Q1.14) "
main_menu_prompt_q15a_text  .STRINGZ " a (Q0.15) > "
main_menu_prompt_q15b_text  .STRINGZ " b (Q0.15) > "
main_menu_prompt_q15_text   .STRINGZ "(Q0.15) "
main_menu_prompt_dq16a_text .STRINGZ " a (Q15.16) > "
main_menu_prompt_dq16b_text .STRINGZ " b (Q15.16) > "
main_menu_prompt_dq16_text  .STRINGZ "(Q15.16) "


;   ============================================================================
;   ==- NODOS -=================================================================

main_menu_init              .FILL main_menu_show_menu
                            .FILL main_menu_init_text
                            .FILL main_menu_init_filter
                            .FILL main_menu_init_next
                            .FILL #0
main_menu_init_text         .STRINGZ "\n\n==CALCULADORA ARQUITECTURA 2026==\n[7] x      [8] /      [9] Log    [b] TRANSFORMACION BILINEAL\n[4] sqrt   [5] exp    [6] pow    [c] CORDIC\n[1] sin    [2] cos    [3] base   [d] Q3.12 -> Q7.8\n[0] MCD    [a] MCM               [e] (salir)\n"
main_menu_init_filter       .STRINGZ "09aeAE"
main_menu_init_next         .FILL main_menu_mcd
                            .FILL main_menu_sin
                            .FILL main_menu_cos
                            .FILL main_menu_base
                            .FILL main_menu_sqrt
                            .FILL main_menu_exp
                            .FILL main_menu_pow
                            .FILL main_menu_mult
                            .FILL main_menu_div
                            .FILL main_menu_log
                            .FILL main_menu_mcm
                            .FILL main_menu_trbilin
                            .FILL main_menu_cordic
                            .FILL main_menu_qtoq
                            .FILL main_menu_end

;   ============================================================================
main_menu_end               .FILL main_menu_return
                            ; #0 #0 #0 #0 (no es necesario en este caso por que
                            ; el controlador simplemente es continuar en return).

;   ============================================================================
main_menu_mcd               .FILL main_menu_two_int
                            .FILL main_menu_mcd_text
                            .FILL #0
                            .FILL main_menu_mcd_next
                            .FILL main_menu_sub_mcd
main_menu_mcd_text          .STRINGZ "\n\n==MAXIMO COMUN DIVISOR==\n"
main_menu_mcd_next          .FILL main_menu_init

;   ============================================================================
main_menu_sin               .FILL main_menu_show_menu
                            .FILL main_menu_sin_text
                            .FILL main_menu_sin_filter
                            .FILL main_menu_sin_next
                            .FILL #0
main_menu_sin_text          .STRINGZ "\n\n==SENO TRIGONOMETRICO==\n[0] TAYLOR\n[1] TABLE\n[2] CHEBYSHEV-PADE\n"
main_menu_sin_filter        .STRINGZ "02"
main_menu_sin_next          .FILL main_menu_sin_taylor
                            .FILL main_menu_sin_table
                            .FILL main_menu_sin_chev
;   ----------------------------------------------------------------------------
main_menu_sin_taylor        .FILL main_menu_one_q12
                            .FILL main_menu_sin_taylor_text
                            .FILL #0
                            .FILL main_menu_sin_taylor_next
                            .FILL main_menu_sub_sin_taylor
main_menu_sin_taylor_text   .STRINGZ "\n\n==SENO TRIGONOMETRICO (TAYLOR)==\n"
main_menu_sin_taylor_next   .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_sin_table         .FILL main_menu_one_q12_result_q14
                            .FILL main_menu_sin_table_text
                            .FILL #0
                            .FILL main_menu_sin_table_next
                            .FILL main_menu_sub_sin_table
main_menu_sin_table_text    .STRINGZ "\n\n==SENO TRIGONOMETRICO (TABLE)==\n"
main_menu_sin_table_next    .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_sin_chev          .FILL main_menu_one_q12_result_q14
                            .FILL main_menu_sin_chev_text
                            .FILL #0
                            .FILL main_menu_sin_chev_next
                            .FILL main_menu_sub_sin_chev
main_menu_sin_chev_text     .STRINGZ "\n\n==SENO TRIGONOMETRICO (CHEBYSHEV-PADE)==\n"
main_menu_sin_chev_next     .FILL main_menu_init

;   ============================================================================
main_menu_cos               .FILL main_menu_one_q12_result_q14
                            .FILL main_menu_cos_text
                            .FILL #0
                            .FILL main_menu_cos_next
                            .FILL main_menu_sub_cos
main_menu_cos_text          .STRINGZ "\n\n==COSENO TRIGONOMETRICO==\n"
main_menu_cos_next          .FILL main_menu_init

;   ============================================================================
main_menu_base              .FILL main_menu_show_menu
                            .FILL main_menu_base_text
                            .FILL main_menu_base_filter
                            .FILL main_menu_base_next
                            .FILL #0
main_menu_base_text         .STRINGZ "\n\n==EXPRESION CON BASE==\n[0] HEX\n[1] BIN\n"
main_menu_base_filter       .STRINGZ "01"
main_menu_base_next         .FILL main_menu_base_hex
                            .FILL main_menu_base_bin
;   ----------------------------------------------------------------------------
main_menu_base_hex          .FILL main_menu_one_int_noresult
                            .FILL main_menu_base_hex_text
                            .FILL #0
                            .FILL main_menu_base_hex_next
                            .FILL main_menu_sub_base_hex
main_menu_base_hex_text     .STRINGZ "\n\n==EXPRESION CON BASE (HEX)==\n"
main_menu_base_hex_next     .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_base_bin          .FILL main_menu_one_int_noresult
                            .FILL main_menu_base_bin_text
                            .FILL #0
                            .FILL main_menu_base_bin_next
                            .FILL main_menu_sub_base_bin
main_menu_base_bin_text     .STRINGZ "\n\n==EXPRESION CON BASE (BIN)==\n"
main_menu_base_bin_next     .FILL main_menu_init

;   ============================================================================
main_menu_sqrt              .FILL main_menu_show_menu
                            .FILL main_menu_sqrt_text
                            .FILL main_menu_sqrt_filter
                            .FILL main_menu_sqrt_next
                            .FILL #0
main_menu_sqrt_text         .STRINGZ "\n\n==RAIZ CUADRADA==\n[0] NON RESTORING\n[1] NEWTON-RAPHSON\n"
main_menu_sqrt_filter       .STRINGZ "01"
main_menu_sqrt_next         .FILL main_menu_sqrt_nonres
                            .FILL main_menu_sqrt_nr
;   ----------------------------------------------------------------------------
main_menu_sqrt_nonres       .FILL main_menu_one_q8
                            .FILL main_menu_sqrt_nonres_text
                            .FILL #0
                            .FILL main_menu_sqrt_nonres_next
                            .FILL main_menu_sub_sqrt_nonres
main_menu_sqrt_nonres_text  .STRINGZ "\n\n==RAIZ CUADRADA (NON RESTORING)==\n"
main_menu_sqrt_nonres_next  .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_sqrt_nr           .FILL main_menu_one_q8
                            .FILL main_menu_sqrt_nr_text
                            .FILL #0
                            .FILL main_menu_sqrt_nr_next
                            .FILL main_menu_sub_sqrt_nr
main_menu_sqrt_nr_text      .STRINGZ "\n\n==RAIZ CUADRADA (NEWTON-RAPHSON)==\n"
main_menu_sqrt_nr_next      .FILL main_menu_init

;   ============================================================================
main_menu_exp               .FILL main_menu_one_int
                            .FILL main_menu_exp_text
                            .FILL #0
                            .FILL main_menu_exp_next
                            .FILL main_menu_sub_exp
main_menu_exp_text          .STRINGZ "\n\n==EXPONENCIACION==\n"
main_menu_exp_next          .FILL main_menu_init

;   ============================================================================
main_menu_pow               .FILL main_menu_show_menu
                            .FILL main_menu_pow_text
                            .FILL main_menu_pow_filter
                            .FILL main_menu_pow_next
                            .FILL #0
main_menu_pow_text          .STRINGZ "\n\n==POTENCIACION==\n[0] SUMAS SUCESIVAS\n[1] EXP BINARIA\n"
main_menu_pow_filter        .STRINGZ "01"
main_menu_pow_next          .FILL main_menu_pow_sumas
                            .FILL main_menu_pow_expbin
;   ----------------------------------------------------------------------------
main_menu_pow_sumas         .FILL main_menu_two_int
                            .FILL main_menu_pow_sumas_text
                            .FILL #0
                            .FILL main_menu_pow_sumas_next
                            .FILL main_menu_sub_pow_sumas
main_menu_pow_sumas_text    .STRINGZ "\n\n==POTENCIACION (SUMAS SUCESIVAS)==\n"
main_menu_pow_sumas_next    .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_pow_expbin        .FILL main_menu_two_int
                            .FILL main_menu_pow_expbin_text
                            .FILL #0
                            .FILL main_menu_pow_expbin_next
                            .FILL main_menu_sub_pow_expbin
main_menu_pow_expbin_text   .STRINGZ "\n\n==POTENCIACION (EXPONENCIACION BINARIA)==\n"
main_menu_pow_expbin_next   .FILL main_menu_init

;   ============================================================================
main_menu_mult              .FILL main_menu_show_menu
                            .FILL main_menu_mult_text
                            .FILL main_menu_mult_filter
                            .FILL main_menu_mult_next
                            .FILL #0
main_menu_mult_text         .STRINGZ "\n\n==MULTIPLICACION==\n[0] CORDIC\n[1] BASIC\n[2] BOOTH\n"
main_menu_mult_filter       .STRINGZ "02"
main_menu_mult_next         .FILL main_menu_mult_cordic
                            .FILL main_menu_mult_basic
                            .FILL main_menu_mult_booth
;   ----------------------------------------------------------------------------
main_menu_mult_cordic       .FILL main_menu_two_int
                            .FILL main_menu_mult_cordic_text
                            .FILL #0
                            .FILL main_menu_mult_cordic_next
                            .FILL main_menu_sub_mult_cordic
main_menu_mult_cordic_text  .STRINGZ "\n\n==MULTIPLICACION (CORDIC)==\n"
main_menu_mult_cordic_next  .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_mult_basic        .FILL main_menu_two_int
                            .FILL main_menu_mult_basic_text
                            .FILL #0
                            .FILL main_menu_mult_basic_next
                            .FILL main_menu_sub_mult_basic
main_menu_mult_basic_text   .STRINGZ "\n\n==MULTIPLICACION (BASIC)==\n"
main_menu_mult_basic_next   .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_mult_booth        .FILL main_menu_two_int
                            .FILL main_menu_mult_booth_text
                            .FILL #0
                            .FILL main_menu_mult_booth_next
                            .FILL main_menu_sub_mult_booth
main_menu_mult_booth_text   .STRINGZ "\n\n==MULTIPLICACION (BOOTH)==\n"
main_menu_mult_booth_next   .FILL main_menu_init

;   ============================================================================
main_menu_div               .FILL main_menu_show_menu
                            .FILL main_menu_div_text
                            .FILL main_menu_div_filter
                            .FILL main_menu_div_next
                            .FILL #0
main_menu_div_text          .STRINGZ "\n\n==DIVISION==\n[0] LONG DIVISION\n[1] NEWTON-RAPHSON\n"
main_menu_div_filter        .STRINGZ "01"
main_menu_div_next          .FILL main_menu_div_long
                            .FILL main_menu_div_nr
;   ----------------------------------------------------------------------------
main_menu_div_long          .FILL main_menu_two_int
                            .FILL main_menu_div_long_text
                            .FILL #0
                            .FILL main_menu_div_long_next
                            .FILL main_menu_sub_div_long
main_menu_div_long_text     .STRINGZ "\n\n==DIVISION (LONG DIVISION)==\n"
main_menu_div_long_next     .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_div_nr            .FILL main_menu_two_int
                            .FILL main_menu_div_nr_text
                            .FILL #0
                            .FILL main_menu_div_nr_next
                            .FILL main_menu_sub_div_nr
main_menu_div_nr_text       .STRINGZ "\n\n==DIVISION (NEWTON-RAPHSON)==\n"
main_menu_div_nr_next       .FILL main_menu_init

;   ============================================================================
main_menu_log               .FILL main_menu_one_q8
                            .FILL main_menu_log_text
                            .FILL #0
                            .FILL main_menu_log_next
                            .FILL main_menu_sub_log
main_menu_log_text          .STRINGZ "\n\n==LOGARITMO==\n"
main_menu_log_next          .FILL main_menu_init

;   ============================================================================
main_menu_mcm               .FILL main_menu_two_int
                            .FILL main_menu_mcm_text
                            .FILL #0
                            .FILL main_menu_mcm_next
                            .FILL main_menu_sub_mcm
main_menu_mcm_text          .STRINGZ "\n\n==MINIMO COMUN MULTIPLO==\n"
main_menu_mcm_next          .FILL main_menu_init

;   ============================================================================
main_menu_trbilin           .FILL main_menu_one_q12
                            .FILL main_menu_trbilin_text
                            .FILL #0
                            .FILL main_menu_trbilin_next
                            .FILL main_menu_sub_trbilin
main_menu_trbilin_text      .STRINGZ "\n\n==TRANSFORMACION BILINEAL==\n"
main_menu_trbilin_next      .FILL main_menu_init

;   ============================================================================
main_menu_cordic            .FILL main_menu_show_menu
                            .FILL main_menu_cordic_text
                            .FILL main_menu_cordic_filter
                            .FILL main_menu_cordic_next
                            .FILL #0
main_menu_cordic_text       .STRINGZ "\n\n==CORDIC==\n[0] ARGUMENTO MANUAL\n[1] SERIE ARCTAN\n"
main_menu_cordic_filter     .STRINGZ "01"
main_menu_cordic_next       .FILL main_menu_cordic_man
                            .FILL main_menu_cordic_atan
;   ----------------------------------------------------------------------------
main_menu_cordic_man        .FILL main_menu_one_q12
                            .FILL main_menu_cordic_man_text
                            .FILL #0
                            .FILL main_menu_cordic_man_next
                            .FILL main_menu_sub_cordic_man
main_menu_cordic_man_text   .STRINGZ "\n\n==CORDIC (ARGUMENTO MANUAL)==\n"
main_menu_cordic_man_next   .FILL main_menu_init
;   ----------------------------------------------------------------------------
main_menu_cordic_atan       .FILL main_menu_one_q12
                            .FILL main_menu_cordic_atan_text
                            .FILL #0
                            .FILL main_menu_cordic_atan_next
                            .FILL main_menu_sub_cordic_atan
main_menu_cordic_atan_text  .STRINGZ "\n\n==CORDIC (SERIE ARCTAN)==\n"
main_menu_cordic_atan_next  .FILL main_menu_init

;   ============================================================================
main_menu_qtoq              .FILL main_menu_one_q12_result_q8
                            .FILL main_menu_qtoq_text
                            .FILL #0
                            .FILL main_menu_qtoq_next
                            .FILL main_menu_sub_qtoq
main_menu_qtoq_text         .STRINGZ "\n\n==Q3.12 -> Q7.8==\n"
main_menu_qtoq_next         .FILL main_menu_init



;   ============================================================================
;   ==- SUBRUTINAS de las Funciones de la calculadora -=========================

main_menu_sub_mult_cordic   .FILL NULL_SUBRUTINE        ; <- MULT_CORDIC
main_menu_sub_mult_basic    .FILL NULL_SUBRUTINE        ; <- MULT_BASIC
main_menu_sub_mult_booth    .FILL NULL_SUBRUTINE        ; <- MULT_BOOTH
main_menu_sub_div_long      .FILL NULL_SUBRUTINE        ; <- DIV_LONG
main_menu_sub_div_nr        .FILL NULL_SUBRUTINE        ; <- DIV_NEWTONRAPHSON
main_menu_sub_log           .FILL NULL_SUBRUTINE        ; <- LOG
main_menu_sub_sqrt_nonres   .FILL NULL_SUBRUTINE        ; <- SQRT_NONRES
main_menu_sub_sqrt_nr       .FILL NULL_SUBRUTINE        ; <- SQRT_NEWTONRAPHSON
main_menu_sub_exp           .FILL NULL_SUBRUTINE        ; <- EXP
main_menu_sub_pow_sumas     .FILL NULL_SUBRUTINE        ; <- POW_SUMAS
main_menu_sub_pow_expbin    .FILL NULL_SUBRUTINE        ; <- POW_EXPBIN
main_menu_sub_sin_taylor    .FILL NULL_SUBRUTINE        ; <- SIN_TAYLOR
main_menu_sub_sin_table     .FILL NULL_SUBRUTINE        ; <- SIN_TABLE
main_menu_sub_sin_chev      .FILL NULL_SUBRUTINE        ; <- SIN_CHEV
main_menu_sub_cos           .FILL NULL_SUBRUTINE        ; <- COS
main_menu_sub_base_dec      .FILL NULL_SUBRUTINE        ; <- BASE_DEC
main_menu_sub_base_hex      .FILL NULL_SUBRUTINE        ; <- BASE_HEX
main_menu_sub_base_bin      .FILL NULL_SUBRUTINE        ; <- BASE_BIN
main_menu_sub_mcd           .FILL NULL_SUBRUTINE        ; <- MCD
main_menu_sub_mcm           .FILL NULL_SUBRUTINE        ; <- MCM
main_menu_sub_trbilin       .FILL NULL_SUBRUTINE        ; <- TR_BILINEAL
main_menu_sub_cordic_man    .FILL NULL_SUBRUTINE        ; <- CORDIC_MANUAL
main_menu_sub_cordic_atan   .FILL NULL_SUBRUTINE        ; <- CORDIC_ARCTAN
main_menu_sub_qtoq          .FILL NULL_SUBRUTINE        ; <- Q_TO_Q                ; Q3.12 to Q7.8


; (subrutina valida, pero que no hace nada...)
NULL_SUBRUTINE
    ST R0 null_subrutine_r0
    ST R7 null_subrutine_r7
    LEA R0 null_subrutine_text
    PUTS
    LD R0 null_subrutine_r0
    LD R7 null_subrutine_r7
    RET
null_subrutine_r0   .FILL #0
null_subrutine_r7   .FILL #0
null_subrutine_text .STRINGZ "(se ejecutaria una subrutina...)\n"

.END
