
.ORIG x3000

    LEA R0 prompt
    PUTS

loop
    GETC
    OUT
    ADD R0 R0 #-8
    ADD R0 R0 #-2
    BRnp loop

    HALT

prompt  .STRINGZ "pulse teclas - pulse INTRO para salir\n"


.END