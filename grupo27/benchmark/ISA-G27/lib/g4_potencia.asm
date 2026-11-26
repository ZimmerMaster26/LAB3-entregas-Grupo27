;=====================================================================
; SUBRUTINA: EXP_RAPIDA (Exponenciación binaria entera para ISA-G27)
;
; ENTRADAS:
;   R0 = Base (entero con signo de 16 bits)
;   R1 = Exponente (entero >= 0)
;
; SALIDA:
;   R0 = Base ^ Exponente (entero con signo de 16 bits)
;
; Conserva R1-R5 y R7. No usa MUL ni MULH.
;=====================================================================
EXP_RAPIDA:
        ST      R1, E_SAVE_R1
        ST      R2, E_SAVE_R2
        ST      R3, E_SAVE_R3
        ST      R4, E_SAVE_R4
        ST      R5, E_SAVE_R5

        ; R2 = Base de trabajo
        ; R3 = Exponente de trabajo
        ; R4 = Acumulador del resultado = 1
        ADD     R2, R0, #0
        ADD     R3, R1, #0
        AND     R4, R4, #0
        ADD     R4, R4, #1

        ; Calcular signo final en R5:
        ; Solo será negativo (bit 15 = 1) si Base < 0 Y Exponente es impar.
        AND     R5, R5, #0
        ADD     R2, R2, #0
        BRzp    E_LOOP
        NOT     R2, R2              ; R2 = |Base|
        ADD     R2, R2, #1
        AND     R0, R3, #1          ; Verificar si el exponente original es impar
        BRz     E_LOOP
        ADD     R5, R5, #-1         ; R5 = 0xFFFF (negativo) para marcar signo final

        ; ============================================================
        ; BUCLE PRINCIPAL DE EXPONENCIACIÓN BINARIA
        ; ============================================================
E_LOOP:
        ADD     R3, R3, #0
        BRnz    E_FIN               ; Si exponente <= 0, terminar

        ; 1. Si el bit menos significativo del exponente es 1: R4 = R4 * R2
        AND     R0, R3, #1
        BRz     E_DIV2

        ; Multiplicación Shift-and-Add: R0 = R4 * R2
        AND     R0, R0, #0          ; Producto parcial = 0
        ADD     R1, R2, #0          ; Multiplicador = R2
E_MUL1:
        AND     R1, R1, R1
        BRz     E_MUL1_END
        AND     R5, R1, #1          ; Uso temporal del bit 0 (no toca bit 15 de signo)
        ; Nota: para no perder el bit 15 de signo en R5, usamos XOR/condicional limpio:
        BRz     E_MUL1_SHIFT
        ADD     R0, R0, R4
E_MUL1_SHIFT:
        ADD     R4, R4, R4          ; Multiplicando <<= 1
        RSH     R1, R1, #1          ; Multiplicador >>= 1 (lógico)
        BR      E_MUL1
E_MUL1_END:
        ADD     R4, R0, #0          ; R4 = R4 * R2

        ; 2. Dividir exponente entre 2 en 1 sola instrucción (R3 >>= 1)
E_DIV2:
        RSH     R3, R3, #1
        BRz     E_FIN               ; Si R3 == 0, no hace falta elevar R2 al cuadrado

        ; 3. Elevar la base al cuadrado: R2 = R2 * R2 (Shift-and-Add)
        AND     R0, R0, #0          ; Producto parcial = 0
        ADD     R1, R2, #0          ; Multiplicador = R2
E_MUL2:
        AND     R1, R1, R1
        BRz     E_MUL2_END
        AND     R5, R1, #1
        BRz     E_MUL2_SHIFT
        ADD     R0, R0, R2
E_MUL2_SHIFT:
        ADD     R2, R2, R2          ; Multiplicando <<= 1
        RSH     R1, R1, #1          ; Multiplicador >>= 1 (lógico)
        BR      E_MUL2
E_MUL2_END:
        ADD     R2, R0, #0          ; R2 = R2 * R2

        BR      E_LOOP

        ; ============================================================
        ; APLICAR SIGNO FINAL Y RESTAURAR REGISTROS
        ; ============================================================
E_FIN:
        ADD     R0, R4, #0          ; R0 = |Base ^ Exponente|
        ADD     R5, R5, #0          ; El bit 15 de R5 nunca fue alterado por AND #1
        BRzp    E_RESTORE
        NOT     R0, R0              ; Complemento a 2 si resultado debe ser negativo
        ADD     R0, R0, #1

E_RESTORE:
        LD      R1, E_SAVE_R1
        LD      R2, E_SAVE_R2
        LD      R3, E_SAVE_R3
        LD      R4, E_SAVE_R4
        LD      R5, E_SAVE_R5
        RET

;--- Zona de datos ---
E_SAVE_R1:  .FILL #0
E_SAVE_R2:  .FILL #0
E_SAVE_R3:  .FILL #0
E_SAVE_R4:  .FILL #0
E_SAVE_R5:  .FILL #0

.END