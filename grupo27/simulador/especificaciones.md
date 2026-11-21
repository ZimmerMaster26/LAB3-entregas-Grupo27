
# Especificaciones para el proyecto:

### Estructuración del código:

- El proyecto se realizara en Python.
- Se puede utilizar únicamente el directorio `grupo27/simulador/`.
- Se debe realizar un documento de detalles y guía de como utilizar este proyecto.
- Se pueden usar módulos, clases, y toda estructuración que convenga para que el código sea fácil de entender y editar.
- Se debe mantener el código limpio y fácil de leer, para que no sea necesario comentar cada línea del mismo, pero si comentar funciones clases y operaciones que no sean tan sencillas de entender dentro del código.
- Todas las instrucciones de la ISA-G27 tienen que estar en el código estructuradas en un archivo o modulo, de manera que se pueda agregar o eliminar instrucciones, o modificar fácilmente el comportamiento y funcionalidad de las que ya están. Se puede hacer tanto una lista, tabla o preferentemente clases separadas para cada instrucción para lograr este punto. Lo mismo va para los predictores de salto, y las pseudo operaciones, se deben estructurar en un archivo o modulo separado, para que sea fácil editar el código, eliminar o agregar nuevos predictores de salto y pseudo operaciones.
- Tambien las instrucciones tienen que definir que operaciones realizan sobre los componentes del simulador, y en que etapa (FETCH, DECODE, EXECUTE, MEMORY, WRITEBACK, etc.) por si se esta ejecutando en modo pipeline.
- La información necesaria para la realización del proyecto puede ser encontrada en este archivo, en el archivo `ISA-G27.pdf`, en el libro "introduction to computing systems" de yale n. patt, sanjay j. patel, tercera edición, que contiene la ISA de la LC-3 e implementación de una arquitectura de computadoras, de la cual la ISA-G27 esta basada, y tambien puede buscarse otras fuentes, libros o internet.


### Programa ensamblado para la ISA-G27 que correrá el simulador

- El programa ensamblado para la ISA-G27 consiste en conjuntos de datos de 8 bits, que representan la memoria del programa.
- Los dos primeros datos de 8 bits (en conjunto 16 bits) pueden corresponder (o no) a la dirección de origen del programa.
- Puede estar en formato numérico, con números de 8 bits, y en caso de ser un archivo tendrá extensión `.lst` y un numero por línea.
- Puede estar en formato binario, con palabras de 8 caracteres `0` o `1`, y en caso de ser un archivo tendrá extensión `.bin` y una palabra por línea.
- Puede estar en formato hexadecimal, con palabras de 2 caracteres hexadecimales, y en caso de ser un archivo tendrá extensión `.hex` y una palabra por línea.

### Sistema Operativo del Simulador

- El sistema operativo se deberá poder leer en archivo por separado como un código en ensamblador, archivo ensamblado en binario y hexadecimal, aunque se cargue automáticamente al iniciar el simulador.
- Debe implementar funciones TRAP que permitan leer caracteres por teclado y mostrar caracteres en consola.
- Debe implementar un sistema de pilas de modo usuario y modo privilegiado, interrupciones y volver de las TRAP utilizando RTI.

### Datos extra respecto a la ISA-G27
- Se dispone de una Memoria de $2^16$ espacios de 8 bits. (Similar al de la LC-3, con espacios de vector TRAP, espacio para el sistema operativo, en `0x3000` espacio para programa de usuario, y al final de la memoria el espacio para dispositivos de entrada y salida, pero teniendo en cuenta que ahora cada dirección apunta a 8 bits, y las instrucciones y datos varios, están alineados ocupando 16 bits)
- Se dispone de 8 registros de propósito general de 16 bits, los cuales se pueden cargar 16 bits, y 8 bits bajos (manteniendo los 8 bits altos).
- Se dispone de un registro de condiciones *nzp* (negativo, cero, positivo) y otro *oc* (overflow, carry).


### Simulador

- El simulador consiste en una clase o programa, que puede ejecutar un programa ensamblado para la ISA-G27.
- Recibe como argumento una texto, una lista de textos, o un archivo que se tomará como el programa ensamblado para la ISA-G27.
- Se considerara por defecto, los dos primeros datos como dirección de origen, pero se podrá pasar una bandera para desactivarlo y otra para especificar una dirección origen especifica. (La prioridad será, dirección especificada, si no se especifica pero si se desactiva será `0x3000`, y si no se busca la opción por defecto que son los dos primeros datos).
- El simulador se deberá poder utilizar tanto como una clase importable desde un modulo, o como programa ejecutable desde la consola.
- Deberá poder contar y medir factores como:
  - Cantidad de instrucciones ejecutadas.
  - Ciclos ejecutados.
  - Lecturas de la Memoria.
  - Escrituras de la Memoria.
  - (entre otros)
- Tambien se deberá poder iniciar el simulador en distintos modos de ejecución:
  - Por defecto será mono ciclo, donde cada instrucción se ejecuta como un ciclo del reloj.
  - Multi ciclo, donde cada instrucción ocurre en un periodo de varios ciclos (los necesarios para completar la instrucción).
  - Pipeline, donde varias instrucciones pueden estar ejecutando una etapa diferente. Para este ultimo, tambien se contara con distintos modos de predictor de salto. De momento se implementara únicamente los predictores *salto nunca tomado*, *salto siempre tomado*, *predictor de 1 bit*, *predictor de 2 bits*. (Se debe intentar implementar en estructuras o clases, para que se pueda añadir con facilidad mas predictores de salto en un futuro, como *predictor de 2 bits con historial*, etc.)
  

### Ensamblador
- El ensamblador consiste en una clase o programa, que puede ensamblar un texto, conjuntos de textos o archivo, que contiene un programa o proyecto en ensamblador de la ISA-G27.
- Tomara el primer texto, o archivo como principal, y luego se encargara de buscar los demás textos o archivos necesarios.
- El ensamblador se deberá poder utilizar tanto como una clase importable desde un modulo, o como programa ejecutable desde la consola.
- Retornara por defecto un archivo hexadecimal, pero con banderas se debe poder elegir cual de los formatos de programa ensamblado para la ISA-G27 se quiere.
- Se ignoraran las comas ',' permitiendo tomar tanto `ADD R3, R4, R4` como `ADD R3 R4 R4`.
- Se ignoraran líneas en blanco y los comentarios, que están definidos como texto que va desde un punto y coma ';' hasta final de línea.
- Muchas características se esperan que sean similares al lenguaje ensamblador de la LC-3.
- Se dispondrán de las siguientes pseudo operaciones (pero se debe poder cambiar la estructura o clases del código con facilidad, para añadir, eliminar y modificar pseudo operaciones soportadas):
  - `.ORIG` define el inicio en memoria del programa (solo afecta al programa principal)
  - `.END` define el final del programa en el archivo actual.
  - `.EXTERNAL` define etiquetas que se encuentran en otros archivos o programas, que serán utilizadas en el programa actual.
  - `.FILL` define 1 Word de memoria.
  - `.FILLB` define 1 Byte de memoria.
  - `.BLKW` define un numero de Words en blanco.
  - `.BLKB` define un numero de Bytes en blanco.
  - `.STRINGZ` define una cadena de caracteres de 8 bits seguidos por un espacio en blanco (que actúa como carácter '\0').
- En caso de haber 1 `.FILLB` (o un dato de 8 bits) y a continuación un dato de 1 Word (instrucción, dato de 16 bits, etc.), se llenara con un padding de un Byte (8 bits en 0).
- En caso de haber 2 `.FILLB` (o datos de 8 bits) consecutivos actuaria correctamente llenando únicamente 16 bits de memoria.

- Para la pseudo operación `.EXTERNAL`:
  - Se espera que la sintaxis sea `.EXTERNAL nombre_de_archivo-etiqueta`
    - *nombre_de_archivo* corresponde al nombre que tendría un archivo dentro del directorio actual o subdirectorios dentro de este (sin el `.asm` que se supone implícito) (digo tendría ya que se puede buscar el código fuente en ensamblador del modulo tanto como archivos, como pedirlo como texto al usuario)
    - *etiqueta* corresponde a la etiqueta vinculada a una dirección de memoria que tendrá una línea del modulo externo una vez todos los módulos estén ensamblados uno tras otro en memoria.
  - Se ensamblaran todos los módulos, continuos uno tras otro en memoria después del programa principal.
  - Para ensamblar un método que se propone (no es necesario seguirlo tal cual, puede ser optimizado y cambiado parcial o totalmente, si se puede implementar un mejor método de ensamblado), es de realizar dos etapas (lecturas) de cada archivo, donde se generan tablas de datos necesarios y luego se ensambla al formato especifico:
    - La primer etapa, se encarga de buscar todas las direcciones efectivas de las etiquetas necesarias y calcular el tamaño que ocupara en la memoria, el programa actual. Por lo tanto habrá una tabla global con nombre de archivo, dirección de inicio, y tamaño total en memoria, asi tambien como una sub tabla con las etiquetas y direcciones de memoria correspondientes presentes en ese archivo.
    Cada vez que se encuentre `.EXTERNAL` se tendrá que agregar a la tabla el nombre de archivo, para luego, antes de pasar a la segunda etapa, buscar el archivo correspondiente en el directorio actual o subdirectorios, y de no estar presente se puede pedir al usuario que brinde como texto el contenido que tendría este archivo. Cuando se consiga el programa de este archivo, se procede a procesar la primera etapa de este archivo para completar sus datos (teniendo en cuenta que la dirección de inicio será a continuación del archivo anterior, y que este tambien puede tener `.EXTERNAL` a mas archivos).
    - La segunda pasada se encarga de ensamblar las instrucciones y datos del programa actual utilizando los datos obtenidos en las tablas en la primera etapa (que deberían ser suficientes para calcular todos los valores de dirección efectiva que necesiten las instrucciones).

