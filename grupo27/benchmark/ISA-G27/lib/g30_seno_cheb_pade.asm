;=====================================================================
; SUBRUTINA: SEN_CHEB_PADE (Seno por aproximación racional Chebyshev-Padé)
;
;   Fórmula:  sen(x) ~= x * (1 - A*u) / (1 + B*u),  con u = x^2 / 2
;             A = 3672 / 16384 (0.2241), B = 1814 / 16384 (0.1107)
;   Entrada:  R0 = ángulo x en radianes (formato Q3.12 con signo)
;   Salida:   R0 = sen(x) en formato Q1.14 con signo (1.0 = 16384 = x4000)
;   Conserva: R1-R7 (todos intactos, incluyendo R6).
;=====================================================================
SEN_CHEB_PADE:
        ST      R1, SN_R1
        ST      R2, SN_R2
        ST      R3, SN_R3
        ST      R4, SN_R4
        ST      R5, SN_R5
        ST      R7, SN_R7

        ; ---- 1. Reducción de rango (Q3.12) a [0, pi/2] y signo ----
        AND     R4, R4, #0          ; R4 = bandera de signo (0 = +, 1 = -)
        ADD     R0, R0, #0
        BRzp    SN_ABS_OK
        NOT     R0, R0
        ADD     R0, R0, #1          ; R0 = |x| (si x = -8.0 -> x8000 = 32768 sin signo)
        ADD     R4, R4, #1          ; signo = negativo

SN_ABS_OK:
        ; Reducir |x| si supera 2*pi (25736)
        LD      R1, SN_N2PI         ; -25736
        ADD     R2, R0, R1          ; |x| - 2*pi
        BRnz    SN_CHK_PI
        ADD     R0, R2, #0          ; |x| -= 2*pi -> [0, 2*pi]

SN_CHK_PI:
        ; Si |x| > pi (12868), restar pi e invertir signo
        LD      R1, SN_NPI          ; -12868
        ADD     R2, R0, R1          ; |x| - pi
        BRnz    SN_CHK_HALFPI
        ADD     R0, R2, #0          ; |x| -= pi -> [0, pi]
        XOR     R4, R4, #1          ; Invertir bandera de signo

SN_CHK_HALFPI:
        ; Si |x| > pi/2 (6434), reflejar respecto a pi: x_ref = pi - |x|
        LD      R1, SN_NHALFPI      ; -6434
        ADD     R2, R0, R1          ; |x| - pi/2
        BRnz    SN_TO_Q14
        LD      R1, SN_PI           ; +12868
        NOT     R0, R0
        ADD     R0, R0, #1
        ADD     R0, R1, R0          ; R0 = pi - |x| -> [0, pi/2]

SN_TO_Q14:
        ; Convertir x en [0, pi/2] de Q3.12 a Q1.14 (<< 2)
        LSH     R0, R0, #2          ; R0 = x en Q1.14 (0..25736)
        BRz     SN_EXIT             ; Si x == 0 -> sen(0) = 0
        ST      R4, SN_SIGN
        ST      R0, SN_X

        ; ---- 2. Núcleo racional Chebyshev-Padé (Q1.14) ----
        ; 2a) u = (x * x + 2^14) >> 15  (x^2 / 2 redondeado en Q1.14)
        MUL     R2, R0, R0          ; Bits bajos [15:0] de x^2
        MULH    R3, R0, R0          ; Bits altos [31:16] de x^2
        LD      R1, SN_ONE          ; 16384 = 2^14 (redondeo para >> 15)
        AND     R5, R5, #0
        ADD     R2, R2, R1
        ADC     R3, R3, R5          ; Propagar acarreo a la palabra alta
        LSH     R3, R3, #1          ; Bits altos desplazados para >> 15
        RSH     R2, R2, #15         ; Bit 15 de la palabra baja pasa a bit 0
        OR      R4, R3, R2          ; R4 = u en Q1.14

        ; 2b) num = 1.0 - ((A * u + 2^13) >> 14)
        LD      R1, SN_A            ; A = 3672
        MUL     R2, R4, R1
        MULH    R3, R4, R1
        LD      R1, SN_HALF         ; 8192 = 2^13 (redondeo para >> 14)
        ADD     R2, R2, R1
        ADC     R3, R3, R5
        LSH     R3, R3, #2          ; Bits altos para >> 14
        RSH     R2, R2, #14         ; Bits bajos [15:14] -> [1:0]
        OR      R2, R3, R2          ; R2 = A * u en Q1.14

        LD      R1, SN_ONE          ; 16384 (1.0 en Q1.14)
        NOT     R2, R2
        ADD     R2, R2, #1
        ADD     R2, R1, R2          ; R2 = num = 1 - A*u
        ST      R2, SN_NUM

        ; 2c) den = 1.0 + ((B * u + 2^13) >> 14)
        LD      R1, SN_B            ; B = 1814
        MUL     R2, R4, R1
        MULH    R3, R4, R1
        LD      R1, SN_HALF         ; 8192 = 2^13
        ADD     R2, R2, R1
        ADC     R3, R3, R5
        LSH     R3, R3, #2
        RSH     R2, R2, #14
        OR      R2, R3, R2          ; R2 = B * u en Q1.14

        LD      R1, SN_ONE          ; 16384
        ADD     R4, R1, R2          ; R4 = den = 1 + B*u

        ; 2d) ratio = ((num << 14) + (den >> 1)) / den  (en Q1.14)
        ;     Armar dividendo de 32 bits (R3:R2) = (num << 14) + (den >> 1)
        LD      R0, SN_NUM
        RSH     R3, R0, #2          ; R3 = num >> 2 (parte alta de num << 14)
        LSH     R2, R0, #14         ; R2 = (num & 3) << 14 (parte baja)
        RSH     R1, R4, #1          ; den / 2 (redondeo)
        ADD     R2, R2, R1
        ADC     R3, R3, R5          ; Dividendo de 32 bits listo en R3:R2

        ; Dividir R3:R2 entre den (R4) con cociente en R5 (14 pasos o reducción directa)
        ; Como num <= den, R3 < den: realizamos división restauradora rápida de 14 bits
        ; sobre R3 (resto inicial) bajando los 2 bits altos de R2 y luego 12 ceros:
        ; Alternativa directa O(1) usando DIV y MOD sobre mitades:
        ;   (R3 * 65536 + R2) / den:
        ;   Paso 1 (8 bits altos): tmp1 = (R3 << 8) | (R2 >> 8)
        LSH     R0, R3, #8
        RSH     R1, R2, #8
        OR      R0, R0, R1          ; tmp1 = bits [23:8] del dividendo (<= 65535)
        DIV     R5, R0, R4          ; q_hi = tmp1 / den
        MOD     R3, R0, R4          ; rem1 = tmp1 % den

        ;   Paso 2 (8 bits bajos): tmp2 = (rem1 << 8) | (R2 & x00FF)
        LSH     R3, R3, #8
        LD      R1, SN_M00FF
        AND     R2, R2, R1
        OR      R0, R3, R2          ; tmp2 = (rem1 << 8) | low_byte (<= 65535)
        DIV     R1, R0, R4          ; q_lo = tmp2 / den

        LSH     R5, R5, #8
        OR      R4, R5, R1          ; R4 = ratio en Q1.14

        ; 2e) sen = (x * ratio + 2^13) >> 14
        LD      R0, SN_X
        MUL     R2, R0, R4
        MULH    R3, R0, R4
        LD      R1, SN_HALF         ; 8192 = 2^13
        AND     R5, R5, #0
        ADD     R2, R2, R1
        ADC     R3, R3, R5
        LSH     R3, R3, #2
        RSH     R2, R2, #14
        OR      R0, R3, R2          ; R0 = |sen(x)| en Q1.14

        ; Saturar a 1.0 (16384) si supera 16384
        LD      R1, SN_NEG_ONE      ; -16384
        ADD     R1, R0, R1
        BRnz    SN_APLICAR_SIGNO
        LD      R0, SN_ONE          ; 16384

        ; ---- 3. Aplicar signo del cuadrante ----
SN_APLICAR_SIGNO:
        LD      R1, SN_SIGN
        BRz     SN_EXIT
        NOT     R0, R0
        ADD     R0, R0, #1

        ; ---- 4. Restaurar registros del llamador ----
SN_EXIT:
        LD      R1, SN_R1
        LD      R2, SN_R2
        LD      R3, SN_R3
        LD      R4, SN_R4
        LD      R5, SN_R5
        LD      R7, SN_R7
        ADD     R0, R0, #0          ; Actualizar CC según resultado en R0
        RET

;=====================================================================
; ZONA DE DATOS Y CONSTANTES
;=====================================================================
SN_ONE:         .FILL #16384        ; 1.0 en Q1.14 (2^14)
SN_NEG_ONE:     .FILL #-16384       ; -1.0 en Q1.14
SN_HALF:        .FILL #8192         ; 0.5 en Q1.14 (2^13, redondeo)
SN_N2PI:        .FILL #-25736       ; -2*pi en Q3.12
SN_PI:          .FILL #12868        ; +pi en Q3.12
SN_NPI:         .FILL #-12868       ; -pi en Q3.12
SN_NHALFPI:     .FILL #-6434        ; -pi/2 en Q3.12
SN_A:           .FILL #3672         ; A = 0.2241 en Q1.14
SN_B:           .FILL #1814         ; B = 0.1107 en Q1.14
SN_M00FF:       .FILL x00FF

SN_SIGN:        .FILL #0
SN_X:           .FILL #0
SN_NUM:         .FILL #0

SN_R1:          .FILL #0
SN_R2:          .FILL #0
SN_R3:          .FILL #0
SN_R4:          .FILL #0
SN_R5:          .FILL #0
SN_R7:          .FILL #0

.END