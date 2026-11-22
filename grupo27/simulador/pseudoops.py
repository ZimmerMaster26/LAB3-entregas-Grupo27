'''
Módulo de Pseudo-operaciones (Directivas del Ensamblador) para la ISA-G27.

Este archivo define y documenta todas las directivas y pseudo-operaciones
reconocidas por el ensamblador para la arquitectura ISA-G27 (arquitectura de
16 bits basada en la LC-3, con direccionamiento por bytes y formato Little-Endian).

A diferencia de las instrucciones de máquina de la ISA (definidas en instrucciones.py),
las pseudo-operaciones no corresponden a códigos de operación (OPCODES) ejecutados
directamente por el procesador, sino que son instrucciones dirigidas al ensamblador
para guiar la organización del código, la reserva y asignación de memoria, y el
enlace entre diferentes módulos y archivos fuente.

=============================================================================
LISTADO DE DIRECTIVAS Y PSEUDO-OPERACIONES DE LA ISA-G27:
=============================================================================

1. .ORIG <direccion>
   - Define la dirección de inicio en memoria del programa principal.
   - Solo afecta al programa principal (los módulos externos se ensamblan a
     continuación del programa principal en memoria contigua).
   - Ejemplo: .ORIG x3000

2. .END
   - Marca el final del programa o módulo en el archivo actual.
   - El ensamblador detiene el procesamiento de líneas tras encontrar esta directiva.
   - Ejemplo: .END

3. .EXTERNAL <archivo-etiqueta>
   - Declara etiquetas definidas en otros archivos o programas que serán
     utilizadas en el archivo actual.
   - Sintaxis: .EXTERNAL nombre_archivo-etiqueta
   - Permite que el ensamblador en su primera pasada registre la dependencia
     y cargue el archivo correspondiente para resolver la dirección de la etiqueta.
   - Ejemplo: .EXTERNAL math_lib-sqrt

4. .FILL <valor>
   - Inicializa 1 Word (16 bits / 2 Bytes) de memoria con el valor numérico especificado
     o la dirección de una etiqueta.
   - En memoria, almacena la parte alta a la izquierda y la parte baja a la derecha
     siguiendo la convención Little-Endian definida para la ISA-G27.
   - Ejemplo: .FILL #42, .FILL xFFFF

5. .FILLB <valor>
   - Inicializa 1 Byte (8 bits) de memoria con el valor numérico especificado.
   - Ejemplo: .FILLB #10, .FILLB x0A

6. .BLKW <cantidad>
   - Reserva un bloque de memoria de <cantidad> Words (cada Word ocupa 2 Bytes).
   - El espacio reservado se inicializa por defecto en blanco (ceros).
   - Ejemplo: .BLKW #10 (reserva 10 Words = 20 Bytes de memoria)

7. .BLKB <cantidad>
   - Reserva un bloque de memoria de <cantidad> Bytes (8 bits cada uno).
   - Ejemplo: .BLKB #5 (reserva 5 Bytes de memoria)

8. .STRINGZ "<cadena>"
   - Inicializa una secuencia continua de memoria con los caracteres ASCII de
     la cadena de texto (1 Byte por carácter), seguida automáticamente por
     un carácter nulo '\\0' (1 Byte con valor 0) que actúa como delimitador.
   - Ejemplo: .STRINGZ "Hola Mundo"

=============================================================================
REGLAS DE ALINEACIÓN Y PADDING EN MEMORIA:
=============================================================================
- La memoria de la ISA-G27 está direccionada por Byte (2^16 posiciones de 8 bits).
- Las instrucciones ocupan exactamente 1 Word (2 Bytes) y deben estar alineadas.
- En caso de haber un dato de 8 bits (.FILLB o similar) y a continuación un dato
  de 1 Word (instrucción, .FILL, etc.), el ensamblador insertará un padding de
  un Byte (8 bits en 0x00) para preservar la alineación de palabra.
- En caso de haber 2 .FILLB (o datos de 8 bits) consecutivos, se ubican
  directamente en memoria llenando exactamente 1 Word (16 bits) sin padding.
=============================================================================
'''


# Clase base para las pseudo-operaciones
class BASE_PSEUDOOP:
    MNEMONICS = []
    FORMATS = []

    def __init__(self, *args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Directivas de control de ensamblado
# ---------------------------------------------------------------------------

class PseudoOp_ORIG(BASE_PSEUDOOP):
    """Define la dirección de inicio en memoria del programa principal."""
    MNEMONICS = [".ORIG"]
    FORMATS = [["MNEMONIC", "ADDRESS"]]


class PseudoOp_END(BASE_PSEUDOOP):
    """Define el final del programa o módulo en el archivo actual."""
    MNEMONICS = [".END"]
    FORMATS = [["MNEMONIC"]]


class PseudoOp_EXTERNAL(BASE_PSEUDOOP):
    """Declara una etiqueta perteneciente a otro archivo o módulo externo."""
    MNEMONICS = [".EXTERNAL"]
    FORMATS = [["MNEMONIC", "EXT_SYMBOL"]]


# ---------------------------------------------------------------------------
# Directivas de asignación y reserva de memoria
# ---------------------------------------------------------------------------

class PseudoOp_FILL(BASE_PSEUDOOP):
    """Define e inicializa 1 Word (16 bits / 2 Bytes) en memoria."""
    MNEMONICS = [".FILL"]
    FORMATS = [["MNEMONIC", "VALUE"]]


class PseudoOp_FILLB(BASE_PSEUDOOP):
    """Define e inicializa 1 Byte (8 bits) en memoria."""
    MNEMONICS = [".FILLB"]
    FORMATS = [["MNEMONIC", "VALUE"]]


class PseudoOp_BLKW(BASE_PSEUDOOP):
    """Reserva un bloque de Words en blanco (2 Bytes por Word)."""
    MNEMONICS = [".BLKW"]
    FORMATS = [["MNEMONIC", "COUNT"]]


class PseudoOp_BLKB(BASE_PSEUDOOP):
    """Reserva un bloque de Bytes en blanco (1 Byte por posición)."""
    MNEMONICS = [".BLKB"]
    FORMATS = [["MNEMONIC", "COUNT"]]


class PseudoOp_STRINGZ(BASE_PSEUDOOP):
    """Define una cadena de caracteres ASCII de 8 bits terminada en nulo ('\\0')."""
    MNEMONICS = [".STRINGZ"]
    FORMATS = [["MNEMONIC", "STRING"]]


# Lista de todas las pseudo-operaciones disponibles
PSEUDOOPS = [
    PseudoOp_ORIG,
    PseudoOp_END,
    PseudoOp_EXTERNAL,
    PseudoOp_FILL,
    PseudoOp_FILLB,
    PseudoOp_BLKW,
    PseudoOp_BLKB,
    PseudoOp_STRINGZ,
]

# Diccionario de búsqueda por directiva
PSEUDOOP_BY_MNEMONIC = {}
for _pop in PSEUDOOPS:
    for _m in _pop.MNEMONICS:
        PSEUDOOP_BY_MNEMONIC[_m.upper()] = _pop
