

.EXTERNAL GETVAL_BUFFER-BUFFER
.EXTERNAL GETVAL_BUFFER-BUFFER_END
ext_buffer      .FILL GETVAL_BUFFER-BUFFER
ext_buffer_end  .FILL GETVAL_BUFFER-BUFFER_END

.EXTERNAL GETLINE-GETLINE
.EXTERNAL FROMDEC-FROMDEC
.EXTERNAL TODEC-TODEC
sub_getline     .FILL GETLINE-GETLINE
sub_fromdec     .FILL FROMDEC-FROMDEC
sub_todec       .FILL TODEC-TODEC


;
;   Subrutina para obtener un valor por teclato en cierto formato, mostrando el valor obtenido entre parentesis.
;


GETVAL

    ST R2 getval_r2                     ;
    ST R3 getval_r3                     ;
    ST R4 getval_r4                     ;
    ST R5 getval_r5                     ;
    ST R7 getval_r7                     ;

    LD R0 ext_buffer                    ;
    LD R1 ext_buffer_end                ;
    LD R2 sub_getline                   ;
    JSRR R2                             ;   [R0] buffer = getline()

    LD R2 sub_fromdec                   ;
    JSRR R2                             ;   [R0, R1, R5] = [entero, decimal, errores]

    ST R0 getval_entero                 ;
    ST R1 getval_decimal                ;

    LD R2 ext_buffer                    ;
    AND R3 R3 #0                        ;   # (R3 = formato)
    LD R4 sub_todec                     ;
    JSRR R4                             ;   [R2] = buffer   # (con valor actualizado)

    LEA R0 getval_lbraket               ;
    PUTS                                ;
    ADD R0 R2 #0                        ;
    PUTS                                ;
    LEA R0 getval_rbraket               ;
    PUTS                                ;   print("(" + buffer + ")\n")

    LD R0 getval_entero                 ;
    LD R1 getval_decimal                ;
    LD R2 getval_r2                     ;
    LD R3 getval_r3                     ;
    LD R4 getval_r4                     ;
    LD R5 getval_r5                     ;
    LD R7 getval_r7                     ;
    RET                                 ;


getval_lbraket  .STRINGZ "[ "
getval_rbraket  .STRINGZ " ]\n"
getval_entero   .FILL #0
getval_decimal  .FILL #0
getval_r2       .FILL #0
getval_r3       .FILL #0
getval_r4       .FILL #0
getval_r5       .FILL #0
getval_r7       .FILL #0


.END