'''Simulador de la arquitectura espesificada'''

# El simulador será similar al ensamblador.
# Estara desacoplado de los demas modulos, pero buscara en instrucciones.py las instrucciones
# a travez de las listas dedicadas para esto como son INSTRUCTIONS, INSTRUCTIONS_BY_OPCODE y INSTRUCTIONS_BY_MNEMONIC
# Tambien tendrá capacidad para ejecutarce como clase de python y a travez de la funcion main que correra cuando se ejecute
# este archivo solo (igual que como funciona el ensamblador)
#
# Se tendra una o mas banderas para mostrar estadisticas como:
# - Instrucciones ejecutadas (en espacio del programa, en espacio del sistema operativo, totales)
# - Ciclos ejecutados (depende de si se ejecuta en modo de un solo ciclo, multi ciclo, o pipeline)
# - Lectura de memoria (en espacio del programa, en espacio del sistema operativo, totales)
# - Escritura de memoria (en espacio del programa, en espacio del sistema operativo, totales)
# - Total de accesos a memoria (en espacio del programa, en espacio del sistema operativo, totales)
