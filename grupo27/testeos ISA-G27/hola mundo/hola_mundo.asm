

.ORIG x3000

    LEA R0 saludo       ; Saludo: "Hola mundo! [ ,('o')/ ]"
    PUTS
    HALT

saludo .STRINGZ "Hola mundo! [ ,('o')/ ]"

.END