

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

.EXTERNAL to_qm_n-TO_QM_N
.EXTERNAL from_qm_n-FROM_QM_N
sub_to_qm_n     .FILL to_qm_n-TO_QM_N
sub_from_qm_n   .FILL from_qm_n-FROM_QM_N


;
;   Subrutina para obtener un valor por teclato en cierto formato, mostrando el valor obtenido entre parentesis.
;


GETVAL_QM_N

    ; [R0] n .
    
    ST R1 getval_qm_n_r1                ;
    ST R2 getval_qm_n_r2                ;
    ST R3 getval_qm_n_r3                ;
    ST R4 getval_qm_n_r4                ;
    ST R5 getval_qm_n_r5                ;
    ST R7 getval_qm_n_r7                ;

    ST R0 getval_qm_n_n                 ;
    
    LD R0 ext_buffer                    ;
    LD R1 ext_buffer_end                ;
    LD R2 sub_getline                   ;
    JSRR R2                             ;   [R0] buffer = getline()

    LD R2 sub_fromdec                   ;
    JSRR R2                             ;   [R0, R1, R5] = [entero, decimal, errores]

    LD R2 getval_qm_n_n                 ;
    LD R3 sub_to_qm_n                   ;
    JSRR R3                             ;
    ST R0 getval_qm_n_value             ;
    LD R1 getval_qm_n_n                 ;
    LD R2 sub_from_qm_n                 ;   
    JSRR R2                             ;

    LD R2 ext_buffer                    ;
    AND R3 R3 #0                        ;   # (R3 = formato)
    LD R4 sub_todec                     ;
    JSRR R4                             ;   [R2] = buffer   # (con valor actualizado)

    LEA R0 getval_qm_n_lbraket          ;
    PUTS                                ;
    ADD R0 R2 #0                        ;
    PUTS                                ;
    LEA R0 getval_qm_n_rbraket          ;
    PUTS                                ;   print("(" + buffer + ")\n")

    LD R0 getval_qm_n_value             ;
    LD R1 getval_qm_n_r1                ;
    LD R2 getval_qm_n_r2                ;
    LD R3 getval_qm_n_r3                ;
    LD R4 getval_qm_n_r4                ;
    LD R5 getval_qm_n_r5                ;
    LD R7 getval_qm_n_r7                ;
    RET                                 ;

getval_qm_n_value       .FILL #0
getval_qm_n_lbraket     .STRINGZ "[ "
getval_qm_n_rbraket     .STRINGZ " ]\n"
getval_qm_n_n           .FILL #0
getval_qm_n_r1          .FILL #0
getval_qm_n_r2          .FILL #0
getval_qm_n_r3          .FILL #0
getval_qm_n_r4          .FILL #0
getval_qm_n_r5          .FILL #0
getval_qm_n_r7          .FILL #0


.END