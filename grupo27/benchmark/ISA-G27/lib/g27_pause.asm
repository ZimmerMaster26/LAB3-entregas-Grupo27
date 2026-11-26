

;   ============================================================================
;   Subrutina: PAUSE
;       Muestra un prompt y espera a que se pulse una tecla.
;   
;   ============================================================================

PAUSE                                   ;
    ST R0 pause_r0                      ;
    ST R7 pause_r7                      ;

    LEA R0 pause_prompt                 ;
    PUTS                                ;   print("Pulsa una tecla para continuar...")
    GETC                                ;   getc()
    LD R0 pause_endl                    ;   
    OUT                                 ;   print("\n")

    LD R0 pause_r0                      ;
    LD R7 pause_r7                      ;
    RET

pause_r0      .FILL #0
pause_r7      .FILL #0
pause_prompt  .STRINGZ "Pulsa una tecla para continuar..."
pause_endl    .FILLB #10

.END