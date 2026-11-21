# Simulador y ensamblador ISA-G27

Este directorio contiene el ensamblador, el simulador y el SO mínimo de la
ISA-G27. No modifica los programas existentes en `grupo27/main_menu/` y no
requiere paquetes externos.

## Uso desde Python

```python
from grupo27.simulador import Assembler

source = """
.ORIG x3000
    ADD R0, R0, #1
    BRnzp inicio
inicio RET
.END
"""

result = Assembler().assemble(source)
print(result.text)                 # hexadecimal por defecto, un byte por línea
result.write("programa.hex")
```

`assemble()` acepta texto, una ruta `Path`, un diccionario ordenado o una lista
de fuentes. En el diccionario, la primera entrada es el programa principal y
las siguientes se pueden referenciar mediante `.EXTERNAL`; en una lista, los
textos adicionales se asocian en orden a las dependencias externas que falten.
Para especificar la salida, use
`assemble(source, "bin")` o `"lst"`. El resultado contiene `origin`, `data`,
`symbols`, `modules` y el texto formateado.

## Uso desde consola

Desde la raíz del repositorio:

```text
python -m grupo27.simulador.assembler ruta\al\programa.asm
python -m grupo27.simulador.assembler programa.asm --format bin
python -m grupo27.simulador.assembler programa.asm -I ruta\a\modulos -o salida.hex
```

El formato predeterminado es hexadecimal (`.hex`); también se admiten `bin`
(`.bin`) y `lst` (`.lst`). El archivo empieza con dos bytes que codifican la
dirección de origen (byte alto primero), seguidos por los bytes ensamblados.
Las instrucciones y `.FILL` se emiten con el byte alto primero, como se define
para una palabra en las especificaciones del proyecto.

## Simulador

El simulador se puede importar o ejecutar desde la raíz del repositorio:

```python
from grupo27.simulador import Simulator

sim = Simulator("programa.hex", mode="pipeline", predictor="2bit", input_text="A")
result = sim.run(max_instructions=10000)
print(result.output)
print(result.stats)
```

```text
python -m grupo27.simulador.simulator programa.asm
python -m grupo27.simulador.simulator programa.hex --mode pipeline --predictor 2bit --stats
python -m grupo27.simulador.simulator programa.bin --format bin --origin x3000 --no-os
```

Se cargan automáticamente el SO predeterminado y el programa de usuario. Para
cargar otro SO, use `--os archivo.asm` (también admite `.hex`, `.bin` y `.lst`);
`--no-os` lo desactiva. El simulador acepta fuentes `.asm`, objetos de texto o
listas de bytes. Por defecto consume los dos primeros bytes del objeto como
origen; `origin`/`--origin` lo sobrescribe, y `use_origin_header=False` o
`--no-origin-header` carga en `x3000` sin consumirlos. Los archivos `.lst`,
`.bin` y `.hex` se reconocen por extensión o mediante `program_format`.

Los modos disponibles son `single` (un ciclo por instrucción), `multicycle`
(ciclos según las etapas declaradas por la instrucción) y `pipeline` (cinco
etapas en orden, emisión por ciclo, resolución de saltos y vaciado ante
predicción incorrecta). El pipeline conserva ejecución arquitectónica en orden
y no modela forwarding ni retardos de caché. Los predictores son `never`,
`always`, `1bit` y `2bit`. `run()` devuelve registros, PC, salida, motivo de
detención y métricas de instrucciones, ciclos, lecturas/escrituras, traps,
interrupciones y predicciones. Los programas sin una instrucción de parada
terminan al salir de una región cargada o al alcanzar `max_instructions`.

## Sistema operativo y dispositivos

`os.asm` contiene la tabla de vectores y handlers de las llamadas documentadas
por la ISA: `GETC` (`x20`), `OUT` (`x21`), `PUTS` (`x22`), `IN` (`x23`) y
`PUTSW` (`x24`). `HALT` (`x25`) detiene la máquina en el simulador y no retorna
por `RTI`. `PUTS` lee una cadena terminada en cero desde bytes en la dirección
de `R0`; `PUTSW` usa palabras de 16 bits, y `IN` lee y hace eco del carácter.
El mapa MMIO seleccionado, inspirado en LC-3, es `KBSR=xFE00`, `KBDR=xFE02`,
`DSR=xFE04` y `DDR=xFE06`; el bit 15 indica que el teclado o la consola están
listos. En modo consola, `--input` suministra caracteres a `GETC`/`IN`; sin esa
opción, el simulador lee de stdin. `OUT` y las rutinas de cadenas escriben en
stdout.

Al entrar a un trap o interrupción, la máquina guarda PSR y PC en la pila
privilegiada, cambia de modo y consulta el vector en `2 * vector`. `RTI`
restaura el contexto y la pila de usuario. La API permite solicitar una
interrupción con `sim.request_interrupt(vector, priority)`; se acepta cuando
su prioridad supera la actual. El SO predeterminado solo instala handlers para
`GETC` y `OUT`; otros vectores requieren que el usuario cargue un SO que los
defina.

## Sintaxis admitida

- Los mnemónicos y registros no distinguen mayúsculas de minúsculas.
- Los operandos pueden separarse por comas o espacios.
- `;` inicia un comentario hasta el fin de línea; se ignora dentro de cadenas.
- Números: decimal (`#12` o `12`), hexadecimal (`x2A` o `0x2A`) y binario
  (`b1010` o `0b1010`). Los campos con signo aceptan valores negativos.
- Las etiquetas se pueden escribir como `etiqueta instrucción ...` o
  `etiqueta: instrucción ...`.
- El origen predeterminado es `x3000`; `.ORIG` lo cambia para el programa
  principal si incluye una dirección. Cada módulo debe incluir `.ORIG` y
  `.END`; `.ORIG` admite omitir la dirección. Sin ella, el programa principal
  usa `x3000` y los módulos externos se colocan a continuación, en orden de
  declaración. La dirección indicada por un módulo externo no cambia su
  ubicación.
- Las referencias PC-relativas a palabras calculan el desplazamiento en
  palabras desde `PC + 2`; las referencias a bytes calculan el desplazamiento
  en bytes desde `PC + 2`. Los valores que no caben en el campo producen un
  error con archivo y línea.

Se implementan las instrucciones y alias enumerados en `isa.py`, incluidos
`BRn`/`BRnzp`, `BRO`/`BRC`, `RET`, `BEXT`, `LSH`/`RSH`, `LSHO`/`RSHO`,
`GETC` y `OUT`. Los operandos, rangos y códigos se derivan de `ISA-G27.pdf`.
Las pseudooperaciones se describen por separado en `pseudo_ops.py`:

| Operación | Resultado |
| --- | --- |
| `.ORIG [dirección]` | Obligatoria; establece el origen del programa principal cuando se indica. |
| `.END` | Obligatoria; termina el archivo actual e ignora lo que sigue. |
| `.EXTERNAL archivo-etiqueta` | Incluye un módulo `.asm` y expone la etiqueta. |
| `.FILL valor` | Emite una palabra de 16 bits. |
| `.FILLB valor` | Emite un byte. |
| `.BLKW cantidad` / `.BLKB cantidad` | Reserva palabras o bytes inicializados en cero. |
| `.STRINGZ "texto"` | Emite caracteres de 8 bits y un byte NUL final. |

Las palabras e instrucciones se alinean en direcciones pares; si el byte previo
deja el contador impar, se inserta un byte cero. Dos bytes consecutivos no
reciben padding entre sí. Para módulos externos, se buscan archivos `.asm` en
el directorio del programa principal, el directorio de trabajo y los directorios
pasados con `-I`. En la API se pueden proporcionar fuentes en memoria mediante
un diccionario, o configurar `external_source_provider` para entregar el texto
de un módulo que no esté en disco.

## Pruebas

Desde la raíz del repositorio:

```text
python -m unittest discover -s grupo27\simulador -p "test_*.py" -v
```
