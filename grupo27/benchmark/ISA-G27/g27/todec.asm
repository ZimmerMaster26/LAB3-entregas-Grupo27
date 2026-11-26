;=====================================================================
; SUBRUTINA: TODEC (Convierte [R0: entero, R1: fracción] a texto decimal de 8 bits)
;
;   -> INPUT  [R0] Parte entera (con signo, 16 bits)
;   -> INPUT  [R1] Parte fraccionaria (magnitud/fracción de 16 bits)
;   -> INPUT  [R2] Puntero (dirección de byte) al buffer de salida (mín. 17 bytes)
;   -> INPUT  [R3] Formato: bit 0 = SHOW_PLUS (+), bit 1 = SHOW_LEADZ, bit 2 = SHOW_ENDZ
;   <- OUTPUT [R2] Puntero (dirección de byte) al inicio del buffer con cadena '\0'
;   Conserva: R0-R7 (todos intactos, incluyendo R6).
;=====================================================================
TODEC:
        ST      R0, todec_r0
        ST      R1, todec_r1
        ST      R3, todec_r3
        ST      R4, todec_r4
        ST      R5, todec_r5
        ST      R7, todec_r7

        ST      R0, todec_entero
        ST      R1, todec_fraccion
        ST      R2, todec_cursor_beg
        ST      R2, todec_cursor_wr
        ST      R3, todec_format

        ; --- 1. Signo ('-' o '+') ---
        LD      R0, todec_entero
        BRzp    todec_sig_elif

        LD      R0, todec_chr_minus
        LD      R2, todec_cursor_wr
        STRB    R0, R2, #0
        ADD     R2, R2, #1
        ST      R2, todec_cursor_wr

        ; Negar par [entero, fraccion]
        LD      R0, todec_entero
        LD      R1, todec_fraccion
        NOT     R0, R0
        NOT     R1, R1
        ADD     R1, R1, #1
        BRnp    todec_sig_neg_ok
        ADD     R0, R0, #1
todec_sig_neg_ok:
        ST      R0, todec_entero
        ST      R1, todec_fraccion
        BR      todec_int

todec_sig_elif:
        LD      R0, todec_format
        AND     R0, R0, #1
        BRz     todec_int

        LD      R0, todec_chr_plus
        LD      R2, todec_cursor_wr
        STRB    R0, R2, #0
        ADD     R2, R2, #1
        ST      R2, todec_cursor_wr

        ; --- 2. Parte entera (dígitos de 10000 a 1 usando DIV / MOD) ---
todec_int:
        LD      R3, todec_entero        ; R3 = remanente entero
        LEA     R5, todec_dec_divisors  ; Tabla de divisores en palabras (2 bytes/elem)

todec_int_loop:
        LDR     R4, R5, #0              ; R4 = divisor actual
        BRz     todec_int_done

        DIV     R2, R3, R4              ; R2 = dígito actual (0..9)
        MOD     R3, R3, R4              ; R3 = nuevo remanente

        ; Mostrar si SHOW_LEADZ está activo, el dígito no es 0, o es el último divisor (1)
        LD      R0, todec_format
        AND     R0, R0, #2
        BRnp    todec_int_emit
        ADD     R2, R2, #0
        BRnp    todec_int_set_leadz
        ADD     R0, R4, #-1
        BRz     todec_int_emit
        BR      todec_int_next

todec_int_set_leadz:
        LD      R0, todec_format
        OR      R0, R0, #2              ; Activar SHOW_LEADZ tras primer dígito no cero
        ST      R0, todec_format

todec_int_emit:
        LD      R0, todec_chr_zero
        ADD     R0, R0, R2              ; ASCII del dígito
        LD      R2, todec_cursor_wr
        STRB    R0, R2, #0
        ADD     R2, R2, #1
        ST      R2, todec_cursor_wr

todec_int_next:
        ADD     R5, R5, #2              ; Avanzar 1 palabra (2 bytes)
        BR      todec_int_loop

todec_int_done:
        ; --- 3. Retorno temprano si fraccion == 0 ---
        LD      R0, todec_fraccion
        BRnp    todec_dec

        LD      R2, todec_cursor_wr
        LD      R0, todec_format
        AND     R0, R0, #4              ; SHOW_ENDZ
        BRz     todec_write_null

        LD      R0, todec_chr_dot
        STRB    R0, R2, #0
        ADD     R2, R2, #1

        LD      R0, todec_chr_zero
        AND     R4, R4, #0
        ADD     R4, R4, #9              ; 9 ceros decimales
todec_early_zeros:
        STRB    R0, R2, #0
        ADD     R2, R2, #1
        ADD     R4, R4, #-1
        BRp     todec_early_zeros

todec_write_null:
        AND     R0, R0, #0
        STRB    R0, R2, #0
        ST      R2, todec_cursor_wr
        BR      todec_ret

        ; --- 4. Parte fraccionaria (acumular fracción * 10^9 en 32 bits) ---
todec_dec:
        LD      R0, todec_chr_dot
        LD      R2, todec_cursor_wr
        STRB    R0, R2, #0
        ADD     R2, R2, #1
        ST      R2, todec_cursor_wr

        AND     R0, R0, #0
        ST      R0, todec_fraccion_h
        ST      R0, todec_fraccion_l
        ST      R0, todec_aux_0

        LD      R0, todec_frac_expr_h
        ST      R0, todec_aux_1
        LD      R0, todec_frac_expr_l
        ST      R0, todec_aux_2

        AND     R5, R5, #0
        ADD     R5, R5, #1              ; mascara = 1

todec_dec_loop1:
        ADD     R5, R5, #0
        BRz     todec_dec_break1

        LD      R0, todec_fraccion
        AND     R0, R0, R5
        BRz     todec_dec_continue1

        LD      R0, todec_fraccion_l
        LD      R1, todec_aux_2
        AND     R2, R2, #0
        ADD     R0, R0, R1
        ADC     R2, R2, R2
        ST      R0, todec_fraccion_l

        LD      R0, todec_fraccion_h
        LD      R1, todec_aux_1
        ADD     R0, R0, R1
        ADD     R0, R0, R2
        ST      R0, todec_fraccion_h

todec_dec_continue1:
        ; [aux_0:aux_1:aux_2] <<= 1
        LD      R0, todec_aux_0
        LD      R1, todec_aux_1
        LD      R2, todec_aux_2

        LSHO    R3, R2, #1
        LSH     R2, R2, #1

        LSHO    R4, R1, #1
        LSH     R1, R1, #1
        OR      R1, R1, R3

        LSH     R0, R0, #1
        OR      R0, R0, R4

        ST      R0, todec_aux_0
        ST      R1, todec_aux_1
        ST      R2, todec_aux_2

        ADD     R5, R5, R5
        BR      todec_dec_loop1

todec_dec_break1:
        ; Extraer 9 dígitos decimales restando 10^8, 10^7, ..., 10^0
        LEA     R5, todec_expr_vec
        AND     R4, R4, #0              ; dígito = 0

todec_dec_loop2:
        LDR     R1, R5, #1              ; -expr_l (palabra baja)
        LDR     R2, R5, #0              ; -expr_h (palabra alta)
        LD      R0, todec_fraccion_l
        LD      R3, todec_fraccion_h
        AND     R7, R7, #0
        ADD     R0, R0, R1
        ADC     R7, R7, R7
        ADD     R3, R3, R2
        ADD     R3, R3, R7              ; R3:R0 = val32 + (-expr32)

        BRn     todec_dec_append
        ST      R3, todec_fraccion_h
        ST      R0, todec_fraccion_l
        ADD     R4, R4, #1
        BR      todec_dec_loop2

todec_dec_append:
        LD      R0, todec_chr_zero
        ADD     R0, R0, R4
        LD      R2, todec_cursor_wr
        STRB    R0, R2, #0
        ADD     R2, R2, #1
        ST      R2, todec_cursor_wr

        ; Si no se pide SHOW_ENDZ y el resto fraccionario es 0, terminar dígitos
        LD      R0, todec_format
        AND     R0, R0, #4
        BRnp    todec_dec_continue2
        LD      R0, todec_fraccion_l
        BRnp    todec_dec_continue2
        LD      R0, todec_fraccion_h
        BRnp    todec_dec_continue2
        BR      todec_dec_break2

todec_dec_continue2:
        AND     R4, R4, #0
        ADD     R5, R5, #4              ; Siguiente par de 32 bits (4 bytes)
        LDR     R0, R5, #1
        BRnp    todec_dec_loop2
        LDR     R0, R5, #0
        BRnp    todec_dec_loop2

todec_dec_break2:
        LD      R2, todec_cursor_wr
        AND     R0, R0, #0
        STRB    R0, R2, #0
        ST      R2, todec_cursor_wr

        ; --- 5. Restaurar registros y devolver puntero en R2 ---
todec_ret:
        LD      R0, todec_r0
        LD      R1, todec_r1
        LD      R2, todec_cursor_beg
        LD      R3, todec_r3
        LD      R4, todec_r4
        LD      R5, todec_r5
        LD      R7, todec_r7
        RET

;=====================================================================
; ZONA DE DATOS Y CONSTANTES
;=====================================================================
todec_r0:           .FILL #0
todec_r1:           .FILL #0
todec_r3:           .FILL #0
todec_r4:           .FILL #0
todec_r5:           .FILL #0
todec_r7:           .FILL #0

todec_entero:       .FILL #0
todec_fraccion:     .FILL #0
todec_cursor_beg:   .FILL #0
todec_cursor_wr:    .FILL #0
todec_format:       .FILL #0
todec_fraccion_h:   .FILL #0
todec_fraccion_l:   .FILL #0
todec_aux_0:        .FILL #0
todec_aux_1:        .FILL #0
todec_aux_2:        .FILL #0

todec_chr_plus:     .FILL #43           ; '+'
todec_chr_minus:    .FILL #45           ; '-'
todec_chr_dot:      .FILL #46           ; '.'
todec_chr_zero:     .FILL #48           ; '0'

todec_frac_expr_h:  .FILL x3B9A
todec_frac_expr_l:  .FILL xCA00         ; 1_000_000_000

todec_dec_divisors:
        .FILL #10000
        .FILL #1000
        .FILL #100
        .FILL #10
        .FILL #1
        .FILL #0

todec_expr_vec:
        .FILL xFA0A
        .FILL x1F00         ; -10^8 (9no dígito)
        .FILL xFF67
        .FILL x6980         ; -10^7 (8vo dígito)
        .FILL xFFF0
        .FILL xBDC0         ; -10^6 (7mo dígito)
        .FILL xFFFE
        .FILL x7960         ; -10^5 (6to dígito)
        .FILL xFFFF
        .FILL xD8F0         ; -10^4 (5to dígito)
        .FILL xFFFF
        .FILL xFC18         ; -10^3 (4to dígito)
        .FILL xFFFF
        .FILL xFF9C         ; -10^2 (3er dígito)
        .FILL xFFFF
        .FILL xFFF6         ; -10^1 (2do dígito)
        .FILL xFFFF
        .FILL xFFFF         ; -10^0 (1er dígito)
        .FILL x0000
        .FILL x0000         ; Terminador NULL de 32 bits

.END