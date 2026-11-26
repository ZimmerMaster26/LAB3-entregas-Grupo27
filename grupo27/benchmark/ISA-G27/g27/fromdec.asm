;=====================================================================
; SUBRUTINA: FROMDEC (Cadena decimal de 8 bits -> Parte entera + Q0.16)
;
;   -> INPUT  [R0] Puntero (dirección de byte) a cadena ASCII decimal ('\0')
;   <- OUTPUT [R0] Parte entera (entero con signo de 16 bits)
;   <- OUTPUT [R1] Parte fraccionaria en Q0.16 (0..65535; 0.5 = 32768)
;   <- OUTPUT [R5] Banderas de error:
;                    bit 0 (1): INVALID_INPUT
;                    bit 1 (2): OVERFLOW
;   Conserva: R2-R4, R6 (intacto) y R7.
;=====================================================================
FROMDEC:
        ST      R2, fromdec_r2
        ST      R3, fromdec_r3
        ST      R4, fromdec_r4
        ST      R7, fromdec_r7

        AND     R5, R5, #0              ; errores = 0
        ADD     R4, R0, #0              ; R4 = puntero de lectura (bytes)

        AND     R0, R0, #0
        ST      R0, fromdec_entero
        ST      R0, fromdec_fraccion
        ST      R0, fromdec_negativo
        ST      R0, fromdec_has_number

        ; --- 1. Signo opcional ('-' o '+') ---
        LDRB    R0, R4, #0              ; LDRB actualiza NZP
        BRz     fromdec_ret

        LD      R1, fromdec_neg_minus
        ADD     R1, R1, R0
        BRnp    fromdec_chk_plus
        AND     R1, R1, #0
        ADD     R1, R1, #1
        ST      R1, fromdec_negativo
        ADD     R4, R4, #1
        BR      fromdec_int_loop

fromdec_chk_plus:
        LD      R1, fromdec_neg_plus
        ADD     R1, R1, R0
        BRnp    fromdec_int_loop
        ADD     R4, R4, #1

        ; --- 2. Parte entera ---
fromdec_int_loop:
        LDRB    R0, R4, #0              ; LDRB actualiza NZP
        BRz     fromdec_ret

        LD      R1, fromdec_neg_dot
        ADD     R1, R1, R0
        BRz     fromdec_int_period_found

        LD      R1, fromdec_neg_period
        ADD     R1, R1, R0
        BRz     fromdec_int_period_found
        BR      fromdec_int_range_chk

fromdec_int_period_found:
        ADD     R4, R4, #1              ; Avanzar tras '.' o ','
        BR      fromdec_dec

fromdec_int_range_chk:
        LD      R1, fromdec_neg_zero
        ADD     R1, R1, R0
        BRn     fromdec_int_invalid

        LD      R1, fromdec_neg_nine
        ADD     R1, R1, R0
        BRp     fromdec_int_invalid

        ; Comprobar desbordamiento (> 3276, o == 3276 con dígito >= 8 + negativo)
        LD      R1, fromdec_entero
        LD      R2, fromdec_neg_overchk
        ADD     R2, R2, R1
        BRp     fromdec_int_overflow
        BRn     fromdec_int_append

        LD      R2, fromdec_neg_eight
        LD      R3, fromdec_negativo
        NOT     R3, R3
        ADD     R3, R3, #1
        ADD     R2, R2, R3
        ADD     R2, R2, R0
        BRn     fromdec_int_append

fromdec_int_overflow:
        OR      R5, R5, #2              ; OVERFLOW (bit 1)

fromdec_int_append:
        LD      R2, fromdec_c10
        MUL     R1, R1, R2              ; entero * 10
        LD      R2, fromdec_neg_zero
        ADD     R1, R1, R2
        ADD     R1, R1, R0              ; entero = entero * 10 + (char - '0')

        AND     R2, R2, #0
        ADD     R2, R2, #1
        ST      R2, fromdec_has_number
        ST      R1, fromdec_entero
        ADD     R4, R4, #1
        BR      fromdec_int_loop

fromdec_int_invalid:
        OR      R5, R5, #1              ; INVALID_INPUT (bit 0)
        BR      fromdec_ret

        ; --- 3. Parte fraccionaria escalada a 32 bits (base 10^9) ---
fromdec_dec:
        AND     R0, R0, #0
        ST      R0, fromdec_fraccion_l
        ST      R0, fromdec_fraccion_h
        ADD     R0, R0, #9
        ST      R0, fromdec_contador

fromdec_dec_loop:
        LD      R0, fromdec_contador
        BRnz    fromdec_dec_break

        AND     R0, R0, #0
        ST      R0, fromdec_current
        LDRB    R0, R4, #0              ; LDRB actualiza NZP

        LD      R1, fromdec_neg_zero
        ADD     R1, R1, R0
        BRn     fromdec_dec_sk1
        LD      R1, fromdec_neg_nine
        ADD     R1, R1, R0
        BRp     fromdec_dec_sk1

        LD      R1, fromdec_neg_zero
        ADD     R1, R1, R0
        ST      R1, fromdec_current
        ADD     R4, R4, #1
        BR      fromdec_dec_increment

fromdec_dec_sk1:
        BRz     fromdec_dec_increment
        OR      R5, R5, #1              ; INVALID_INPUT (bit 0)

fromdec_dec_increment:
        ; [aux_h:aux_l] = 4 * [fraccion_h:fraccion_l]
        LD      R0, fromdec_fraccion_h
        LD      R1, fromdec_fraccion_l
        LSHO    R2, R0, #2
        LSH     R0, R0, #2
        LSHO    R3, R1, #2
        LSH     R1, R1, #2
        OR      R0, R0, R3
        ST      R0, fromdec_aux_h
        ST      R1, fromdec_aux_l

        ; [aux_h:aux_l] = 5 * [fraccion_h:fraccion_l]
        LD      R2, fromdec_aux_l
        LD      R1, fromdec_fraccion_l
        AND     R3, R3, #0
        ADD     R2, R2, R1
        ADC     R3, R3, R3
        ST      R2, fromdec_aux_l

        LD      R2, fromdec_aux_h
        LD      R1, fromdec_fraccion_h
        ADD     R2, R2, R1
        ADD     R2, R2, R3
        ST      R2, fromdec_aux_h

        ; [fraccion_h:fraccion_l] = 2 * [aux_h:aux_l] = 10 * frac
        LD      R0, fromdec_aux_h
        LD      R1, fromdec_aux_l
        LSHO    R2, R1, #1
        LSH     R1, R1, #1
        LSH     R0, R0, #1
        OR      R0, R0, R2
        ST      R0, fromdec_fraccion_h
        ST      R1, fromdec_fraccion_l

        ; Sumar dígito actual en parte baja de 32 bits
        LD      R2, fromdec_current
        AND     R3, R3, #0
        ADD     R1, R1, R2
        ADC     R0, R0, R3
        ST      R1, fromdec_fraccion_l
        ST      R0, fromdec_fraccion_h

        LD      R0, fromdec_contador
        ADD     R0, R0, #-1
        ST      R0, fromdec_contador
        BR      fromdec_dec_loop

        ; --- 4. Convertir fracción decimal (10^9) a 16 bits Q0.16 ---
fromdec_dec_break:
        AND     R0, R0, #0
        ST      R0, fromdec_contador
        ST      R0, fromdec_fraccion

fromdec_dec_loop2:
        ; Duplicar valor decimal de 32 bits: val32 = val32 * 2
        LD      R0, fromdec_fraccion_h
        LD      R1, fromdec_fraccion_l
        LSHO    R2, R1, #1
        LSH     R1, R1, #1
        LSH     R0, R0, #1
        OR      R0, R0, R2
        ST      R0, fromdec_fraccion_h
        ST      R1, fromdec_fraccion_l

        ; Comparar val32 contra 1_000_000_000: aux32 = val32 - 1_000_000_000
        LD      R2, fromdec_neg_frac_l
        LD      R3, fromdec_neg_frac_h
        AND     R4, R4, #0
        ADD     R1, R1, R2
        ADC     R0, R0, R3
        ST      R1, fromdec_aux_l
        ST      R0, fromdec_aux_h

        ; Si ya se generaron los 16 bits Q0.16 (contador >= 16), redondear y salir
        LD      R0, fromdec_contador
        ADD     R0, R0, #-8
        ADD     R0, R0, #-8
        BRzp    fromdec_dec_round

        ; Desplazar acumulador Q0.16 a la izquierda 1 bit
        LD      R0, fromdec_fraccion
        LSH     R0, R0, #1

        ; Si val32 >= 1_000_000_000 (aux_h >= 0), el bit es 1 y actualizamos val32 = aux32
        LD      R1, fromdec_aux_h
        BRn     fromdec_dec_continue2
        OR      R0, R0, #1
        LD      R1, fromdec_aux_l
        ST      R1, fromdec_fraccion_l
        LD      R1, fromdec_aux_h
        ST      R1, fromdec_fraccion_h

fromdec_dec_continue2:
        ST      R0, fromdec_fraccion
        LD      R0, fromdec_contador
        ADD     R0, R0, #1
        ST      R0, fromdec_contador
        BR      fromdec_dec_loop2

fromdec_dec_round:
        ; Redondeo al más cercano usando el bit 17 (aux_h >= 0)
        LD      R0, fromdec_aux_h
        BRn     fromdec_ret
        LD      R0, fromdec_fraccion
        ADD     R0, R0, #1
        ST      R0, fromdec_fraccion
        BRnp    fromdec_ret

        ; Si fraccion Q0.16 desborda a 0 (65536 -> 0), incrementar parte entera
        LD      R0, fromdec_entero
        ADD     R0, R0, #1
        ST      R0, fromdec_entero

        ; --- 5. Retorno y aplicación de signo ---
fromdec_ret:
        LD      R0, fromdec_has_number
        BRnp    fromdec_ret_sk1
        OR      R5, R5, #1              ; INVALID_INPUT si no hubo dígitos

fromdec_ret_sk1:
        LD      R0, fromdec_negativo
        BRz     fromdec_ret_skp_neg

        LD      R0, fromdec_entero
        LD      R1, fromdec_fraccion
        NOT     R0, R0
        NOT     R1, R1
        ADD     R1, R1, #1
        BRnp    fromdec_neg_store
        ADD     R0, R0, #1

fromdec_neg_store:
        ST      R0, fromdec_entero
        ST      R1, fromdec_fraccion

fromdec_ret_skp_neg:
        LD      R0, fromdec_entero
        LD      R1, fromdec_fraccion
        LD      R2, fromdec_r2
        LD      R3, fromdec_r3
        LD      R4, fromdec_r4
        LD      R7, fromdec_r7
        RET

;=====================================================================
; ZONA DE DATOS Y CONSTANTES
;=====================================================================
fromdec_entero:       .FILL #0
fromdec_fraccion:     .FILL #0
fromdec_negativo:     .FILL #0
fromdec_has_number:   .FILL #0
fromdec_fraccion_h:   .FILL #0
fromdec_fraccion_l:   .FILL #0
fromdec_aux_h:        .FILL #0
fromdec_aux_l:        .FILL #0
fromdec_current:      .FILL #0
fromdec_contador:     .FILL #0

fromdec_r2:           .FILL #0
fromdec_r3:           .FILL #0
fromdec_r4:           .FILL #0
fromdec_r7:           .FILL #0

fromdec_c10:          .FILL #10
fromdec_neg_plus:     .FILL #-43
fromdec_neg_period:   .FILL #-44
fromdec_neg_minus:    .FILL #-45
fromdec_neg_dot:      .FILL #-46
fromdec_neg_zero:     .FILL #-48
fromdec_neg_eight:    .FILL #-56
fromdec_neg_nine:     .FILL #-57
fromdec_neg_overchk:  .FILL #-3276
fromdec_neg_frac_h:   .FILL xC465
fromdec_neg_frac_l:   .FILL x3600

.END