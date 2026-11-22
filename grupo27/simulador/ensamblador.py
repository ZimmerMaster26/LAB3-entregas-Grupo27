'''
Ensamblador para la arquitectura ISA-G27.

Traduce programas escritos en lenguaje ensamblador de la ISA-G27 a código máquina
ejecutable por el simulador.

Características principales:
- Ensamblado de dos pasadas (Pass 1: tabla de símbolos y cálculo de direcciones;
  Pass 2: resolución de etiquetas y generación de código binario).
- Resolución y enlazado continuo de módulos externos mediante .EXTERNAL.
- Soporte para formatos de entrada: archivo .asm, texto directo, o mapa de archivos.
- Soporte para formatos de salida: archivo .hex (2 caracteres hex por línea, por defecto),
  archivo .bin (8 caracteres binarios por línea), o lista en memoria de valores.
- Inclusión por defecto de la dirección .ORIG en los dos primeros bytes de la salida.
- Manejo automático de alineación y padding de 1 Byte para instrucciones y Words
  tras datos impares de 8 bits (.FILLB o .STRINGZ).
- Generación opcional de archivo de tabla de símbolos (.sym).
'''

import os
import sys
import re
import argparse
from pathlib import Path

try:
    from . import instrucciones
    from . import pseudoops
except ImportError:
    import instrucciones
    import pseudoops


# ---------------------------------------------------------------------------
# Utilidades de Parseo y Formato
# ---------------------------------------------------------------------------

def strip_comments(line: str) -> str:
    """
    Elimina los comentarios iniciados con ';' respetando las cadenas entre comillas.
    """
    in_quote = False
    quote_char = ''
    result = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if in_quote:
            result.append(c)
            if c == '\\':
                if i + 1 < n:
                    i += 1
                    result.append(line[i])
            elif c == quote_char:
                in_quote = False
        else:
            if c in ('"', "'"):
                in_quote = True
                quote_char = c
                result.append(c)
            elif c == ';':
                break
            else:
                result.append(c)
        i += 1
    return ''.join(result).strip()


def unescape_string(s: str) -> str:
    """
    Parsea las secuencias de escape estándar (\n, \t, \r, \0, \\, \", \') en una cadena.
    """
    escape_map = {
        'n': '\n',
        't': '\t',
        'r': '\r',
        '0': '\0',
        '\\': '\\',
        '"': '"',
        "'": "'",
    }
    result = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == '\\' and i + 1 < n:
            next_char = s[i + 1]
            if next_char in escape_map:
                result.append(escape_map[next_char])
                i += 2
                continue
        result.append(s[i])
        i += 1
    return ''.join(result)


def is_register(token: str) -> bool:
    """Verifica si un token representa un registro válido (R0 a R7, insensible a mayúsculas)."""
    if not isinstance(token, str):
        return False
    t = token.strip()
    return bool(re.match(r'^[rR][0-7]$', t))


def parse_register(token: str) -> int:
    """Convierte un token de registro (ej. 'R3' o 'r3') a su índice entero (0 a 7)."""
    t = token.strip()
    if is_register(t):
        return int(t[1])
    raise ValueError(f"Registro inválido: '{token}'. Se esperaba R0..R7.")


def is_number(token: str) -> bool:
    """Determina si un token puede ser interpretado como un valor numérico."""
    if not isinstance(token, str):
        return isinstance(token, int)
    t = token.strip()
    if not t:
        return False

    # Decimal con prefijo #: #123, #-123
    if t.startswith('#'):
        try:
            int(t[1:], 10)
            return True
        except ValueError:
            return False

    # Hexadecimal con prefijo x/X: x3000, xFFA0, x-10, -x10
    if re.match(r'^[+-]?[xX][0-9a-fA-F]+$', t) or re.match(r'^[xX][+-][0-9a-fA-F]+$', t):
        return True

    # Hexadecimal con prefijo 0x/0X
    if re.match(r'^[+-]?0[xX][0-9a-fA-F]+$', t):
        return True

    # Binario con prefijo b/B o 0b/0B
    if re.match(r'^[+-]?[bB][01]+$', t) or re.match(r'^[+-]?0[bB][01]+$', t):
        return True

    # Carácter entre comillas simples: 'c', '\n'
    if len(t) >= 3 and t.startswith("'") and t.endswith("'"):
        return True

    # Decimal simple sin prefijo
    try:
        int(t, 10)
        return True
    except ValueError:
        return False


def parse_number(token: str) -> int:
    """Parsea un token numérico en decimal, hexadecimal, binario o carácter literal a entero."""
    if isinstance(token, int):
        return token
    t = token.strip()

    # Prefijo decimal #: #123, #-45
    if t.startswith('#'):
        return int(t[1:], 10)

    # Carácter entre comillas simples: 'A', '\n'
    if len(t) >= 3 and t.startswith("'") and t.endswith("'"):
        inner = unescape_string(t[1:-1])
        if len(inner) == 1:
            return ord(inner)
        raise ValueError(f"Literal de carácter inválido: '{token}'")

    # Hexadecimal: x... o X...
    if t.upper().startswith('X'):
        hex_part = t[1:]
        if hex_part.startswith('-'):
            return -int(hex_part[1:], 16)
        return int(hex_part, 16)
    if t.startswith('-X') or t.startswith('-x'):
        return -int(t[2:], 16)
    if t.startswith('+X') or t.startswith('+x'):
        return int(t[2:], 16)

    # 0x...
    if t.lower().startswith('0x') or t.lower().startswith('-0x') or t.lower().startswith('+0x'):
        return int(t, 16)

    # Binario: b... o B... o 0b...
    if t.upper().startswith('B'):
        return int(t[1:], 2)
    if t.lower().startswith('0b') or t.lower().startswith('-0b') or t.lower().startswith('+0b'):
        return int(t, 2)

    # Decimal plano
    return int(t, 10)


def _instruction_classes():
    """Obtiene clases de instrucción desde los registros disponibles."""
    classes = list(getattr(instrucciones, "INSTRUCTIONS", ()) or ())
    for registry_name in ("INSTRUCTION_BY_OPCODE", "INSTRUCTIONS_BY_OPCODE",
                          "INSTRUCTION_BY_MNEMONIC"):
        registry = getattr(instrucciones, registry_name, None)
        if isinstance(registry, dict):
            classes.extend(registry.values())

    unique_classes = []
    seen = set()
    for inst_cls in classes:
        class_id = id(inst_cls)
        if class_id not in seen:
            unique_classes.append(inst_cls)
            seen.add(class_id)
    return unique_classes


def _instruction_class_for(mnemonic: str):
    """Busca una instrucción usando los índices y metadatos del módulo."""
    name = mnemonic.upper()
    by_mnemonic = getattr(instrucciones, "INSTRUCTION_BY_MNEMONIC", {})
    if isinstance(by_mnemonic, dict) and name in by_mnemonic:
        return by_mnemonic[name]

    for inst_cls in _instruction_classes():
        names = getattr(inst_cls, "MNEMONICS", ())
        if any(str(candidate).upper() == name for candidate in names):
            return inst_cls
    return None


def _known_instruction_mnemonics():
    names = set()
    by_mnemonic = getattr(instrucciones, "INSTRUCTION_BY_MNEMONIC", {})
    if isinstance(by_mnemonic, dict):
        names.update(str(name).upper() for name in by_mnemonic)
    for inst_cls in _instruction_classes():
        names.update(str(name).upper()
                     for name in getattr(inst_cls, "MNEMONICS", ()))
    return names


def _pseudoop_classes():
    """Obtiene pseudo-operaciones desde las listas y tablas disponibles."""
    classes = list(getattr(pseudoops, "PSEUDOOPS", ()) or ())
    classes.extend(getattr(pseudoops, "PRESUDOOPS", ()) or ())
    for registry_name in ("PSEUDOOP_BY_MNEMONIC",):
        registry = getattr(pseudoops, registry_name, None)
        if isinstance(registry, dict):
            classes.extend(registry.values())

    unique_classes = []
    seen = set()
    for pseudoop_cls in classes:
        class_id = id(pseudoop_cls)
        if class_id not in seen:
            unique_classes.append(pseudoop_cls)
            seen.add(class_id)
    return unique_classes


def _pseudoop_class_for(mnemonic: str):
    """Busca una pseudo-operación por mnemónico en sus registros."""
    name = mnemonic.upper()
    by_mnemonic = getattr(pseudoops, "PSEUDOOP_BY_MNEMONIC", {})
    if isinstance(by_mnemonic, dict) and name in by_mnemonic:
        return by_mnemonic[name]

    for pseudoop_cls in _pseudoop_classes():
        names = getattr(pseudoop_cls, "MNEMONICS", ())
        if any(str(candidate).upper() == name for candidate in names):
            return pseudoop_cls
    return None


def _known_pseudoop_mnemonics():
    names = set()
    by_mnemonic = getattr(pseudoops, "PSEUDOOP_BY_MNEMONIC", {})
    if isinstance(by_mnemonic, dict):
        names.update(str(name).upper() for name in by_mnemonic)
    for pseudoop_cls in _pseudoop_classes():
        names.update(str(name).upper()
                     for name in getattr(pseudoop_cls, "MNEMONICS", ()))
    return names


# ---------------------------------------------------------------------------
# Resultado del Ensamblado
# ---------------------------------------------------------------------------

class AssemblyResult:
    """
    Objeto que almacena el resultado del ensamblado de un programa ISA-G27.
    Ofrece interfaces como lista, string y métodos de volcado a diferentes formatos.
    """
    def __init__(self, data_bytes, orig_address, program_bytes, output_file=None, symbol_table=None, modules=None):
        self.bytes = bytearray(data_bytes)
        self.orig_address = orig_address
        self.program_bytes = bytearray(program_bytes)
        self.output_file = output_file
        self.symbol_table = symbol_table or {}
        self.modules = modules or []

    def to_hex_lines(self):
        """Retorna una lista con las líneas en formato hexadecimal (2 caracteres por byte)."""
        return [f"{b:02X}" for b in self.bytes]

    def to_bin_lines(self):
        """Retorna una lista con las líneas en formato binario (8 caracteres por byte)."""
        return [f"{b:08b}" for b in self.bytes]

    def to_int_list(self):
        """Retorna una lista con los valores numéricos enteros de cada byte."""
        return list(self.bytes)

    def __iter__(self):
        return iter(self.to_hex_lines())

    def __len__(self):
        return len(self.bytes)

    def __getitem__(self, idx):
        return self.to_hex_lines()[idx]

    def __str__(self):
        if self.output_file:
            return str(self.output_file)
        return "\n".join(self.to_hex_lines())

    def __repr__(self):
        file_desc = f" file='{self.output_file}'" if self.output_file else ""
        return f"<AssemblyResult bytes={len(self.bytes)} orig={self.orig_address:#06x}{file_desc}>"


# ---------------------------------------------------------------------------
# Estructuras intermedias de Parseo
# ---------------------------------------------------------------------------

class ParsedLine:
    """Representa una línea analizada del código fuente ensamblador."""
    def __init__(self, line_num: int, raw_line: str, label=None, mnemonic=None, operands=None):
        self.line_num = line_num
        self.raw_line = raw_line
        self.label = label
        self.mnemonic = mnemonic.upper() if mnemonic else None
        self.operands = operands or []

        self.is_instruction = False
        self.is_pseudoop = False
        self.address = 0
        self.pad_bytes = 0
        self.pseudoop_result = None

        if self.mnemonic:
            if _instruction_class_for(self.mnemonic) is not None or self.mnemonic == "NOP":
                self.is_instruction = True
            elif _pseudoop_class_for(self.mnemonic) is not None:
                self.is_pseudoop = True


class ModuleAST:
    """Representa el conjunto de líneas analizadas y símbolos de un módulo/archivo."""
    def __init__(self, name: str, lines=None, file_path=None):
        self.name = name
        self.lines = lines or []
        self.file_path = file_path
        self.symbols = {}
        self.start_address = 0
        self.end_address = 0
        self.external_dependencies = []


# ---------------------------------------------------------------------------
# Clase Principal del Ensamblador
# ---------------------------------------------------------------------------

class Assembler:
    """
    Ensamblador de programas para la ISA-G27.

    Traduce código fuente ensamblador a código máquina Little-Endian en bytes,
    resolviendo símbolos internos y referencias externas (.EXTERNAL).
    """

    def __init__(self, por_defecto=None, output_format="hex", output_file=None,
                 include_orig=True, links=False, search_dirs=None):
        """
        Inicializa las opciones por defecto del ensamblador.

        Parámetros:
        - por_defecto (str o dict): Formato de salida inicial o configuración base.
        - output_format (str): 'hex' (por defecto), 'bin', o 'list'/'python'.
        - output_file (str o Path): Ruta del archivo de salida.
        - include_orig (bool): Si es True (por defecto), incluye la dirección de inicio
                               en los dos primeros bytes del archivo ensamblado.
        - links (bool): Si es True, genera un archivo de símbolos (.sym).
        - search_dirs (list): Directorios adicionales donde buscar módulos para .EXTERNAL.
        """
        if isinstance(por_defecto, dict):
            self.output_format = por_defecto.get("output_format", output_format)
            self.output_file = por_defecto.get("output_file", output_file)
            self.include_orig = por_defecto.get("include_orig", include_orig)
            self.links = por_defecto.get("links", links)
            self.search_dirs = por_defecto.get("search_dirs", search_dirs or [])
        elif isinstance(por_defecto, str) and por_defecto in ("hex", "bin", "list", "python"):
            self.output_format = por_defecto
            self.output_file = output_file
            self.include_orig = include_orig
            self.links = links
            self.search_dirs = search_dirs or []
        else:
            self.output_format = output_format
            self.output_file = output_file
            self.include_orig = include_orig
            self.links = links
            self.search_dirs = search_dirs or []

    def __call__(self, source=None, *args, **kwargs):
        """Permite invocar la instancia directamente: Assemble('programa.asm')."""
        if source is None and args:
            source = args[0]
            args = args[1:]
        return self.assemble(source, *args, **kwargs)

    def assemble(self, source, output_format=None, output_file=None,
                 include_orig=None, links=None, search_dirs=None,
                 file_map=None, main_file="main") -> AssemblyResult:
        """
        Ensambla un programa ISA-G27 completo.

        Parámetros:
        - source: Ruta a archivo .asm, texto con el programa, o diccionario de archivos.
        - output_format: 'hex', 'bin', o 'list' (invalida la opción por defecto).
        - output_file: Nombre/ruta del archivo resultante.
        - include_orig: Incluir .ORIG en los primeros dos bytes (bool).
        - links: Generar archivo de símbolos (.sym) (bool).
        - search_dirs: Directorios adicionales donde buscar archivos .EXTERNAL.
        - file_map: Diccionario opcional {'nombre_archivo': 'contenido_asm'}.
        - main_file: Nombre clave del archivo principal en file_map.
        """
        out_fmt = (output_format or self.output_format or "hex").lower()
        inc_orig = self.include_orig if include_orig is None else bool(include_orig)
        gen_links = self.links if links is None else bool(links)

        effective_search_dirs = list(self.search_dirs or [])
        if search_dirs:
            if isinstance(search_dirs, (list, tuple)):
                effective_search_dirs.extend(search_dirs)
            else:
                effective_search_dirs.append(search_dirs)

        input_file_path = None
        source_is_file = False

        # Determinar el tipo de origen (archivo, diccionario o texto directo)
        if isinstance(source, dict):
            f_map = dict(source)
            main_code = f_map.get(main_file) or next(iter(f_map.values()))
            main_name = main_file
            base_dir = os.getcwd()
        elif isinstance(source, (str, Path)) and os.path.isfile(str(source)):
            input_file_path = Path(source).resolve()
            source_is_file = True
            base_dir = str(input_file_path.parent)
            main_name = input_file_path.stem
            with open(input_file_path, 'r', encoding='utf-8', errors='replace') as f:
                main_code = f.read()
            f_map = dict(file_map or {})
        elif isinstance(source, (str, Path)) and not str(source).count('\n') and Path(str(source)).suffix.lower() == '.asm':
            # Se pasó una ruta de archivo que no existe directamente
            input_file_path = Path(source)
            raise FileNotFoundError(f"No se pudo encontrar el archivo fuente especificado: {source}")
        else:
            # Cadena de texto directa
            main_code = str(source)
            main_name = "main"
            base_dir = os.getcwd()
            f_map = dict(file_map or {})

        # Agregar base_dir y el directorio actual a search_dirs
        if base_dir not in effective_search_dirs:
            effective_search_dirs.insert(0, base_dir)
        project_root = self._find_project_root(base_dir)
        if project_root and project_root not in effective_search_dirs:
            effective_search_dirs.append(project_root)

        # Cargar y parsear módulos principales y externos
        modules_ast = self._load_all_modules(
            main_code=main_code,
            main_name=main_name,
            main_file_path=str(input_file_path) if input_file_path else None,
            file_map=f_map,
            search_dirs=effective_search_dirs
        )

        # Primera pasada: asignación de memoria y tabla de símbolos
        symbol_table, orig_address = self._pass_1(modules_ast)

        # Resolver .EXTERNAL cuando ya existen las direcciones de todos los módulos.
        self._assemble_external_pseudoops(modules_ast, symbol_table)

        # Segunda pasada: generación de instrucciones y bytes
        emitted_bytes = self._pass_2(modules_ast, symbol_table, orig_address)

        # Preparar bytes finales con o sin dirección de origen
        if inc_orig:
            orig_high = (orig_address >> 8) & 0xFF
            orig_low = orig_address & 0xFF
            final_bytes = bytearray([orig_high, orig_low]) + emitted_bytes
        else:
            final_bytes = emitted_bytes

        # Determinar nombre del archivo de salida
        actual_output_file = output_file or self.output_file
        if not actual_output_file:
            ext = ".bin" if out_fmt == "bin" else ".hex"
            if source_is_file and input_file_path:
                actual_output_file = str(input_file_path.with_suffix(ext))
            else:
                actual_output_file = f"program{ext}"

        result = AssemblyResult(
            data_bytes=final_bytes,
            orig_address=orig_address,
            program_bytes=emitted_bytes,
            output_file=actual_output_file,
            symbol_table=symbol_table,
            modules=[m.name for m in modules_ast]
        )

        # Escribir archivo de salida si el formato lo requiere
        if out_fmt in ("hex", "bin") or output_file is not None:
            self._write_output_file(result, out_fmt, actual_output_file)

        # Generar archivo de enlaces/símbolos si se solicitó
        if gen_links:
            sym_file_path = str(Path(actual_output_file).with_suffix(".sym"))
            self._write_symbol_file(symbol_table, sym_file_path)

        return result

    # -----------------------------------------------------------------------
    # Carga y Resolución de Módulos Externos (.EXTERNAL)
    # -----------------------------------------------------------------------

    def _find_project_root(self, start_dir: str):
        """Intenta localizar el directorio raíz 'grupo27' ascendiendo en el árbol de carpetas."""
        cur = Path(start_dir).resolve()
        for p in [cur] + list(cur.parents):
            if (p / "grupo27").is_dir():
                return str(p / "grupo27")
            if p.name.lower() == "grupo27":
                return str(p)
        return None

    def _tokenize_line(self, line_num: int, raw_line: str) -> ParsedLine:
        """Divide una línea de código fuente en etiqueta, mnemónico y operandos."""
        cleaned = strip_comments(raw_line)
        if not cleaned:
            return ParsedLine(line_num, raw_line)

        # Caso especial para pseudo-operación .STRINGZ (conserva espacios y comas dentro de comillas)
        stringz_match = re.search(r'(?i)\.STRINGZ\s*("(?:\\.|[^"\\])*")', cleaned)
        if stringz_match:
            before_str = cleaned[:stringz_match.start()].strip()
            str_content = stringz_match.group(1)[1:-1] # Quitar las comillas exteriores
            tokens_before = [t for t in re.split(r'[,\s]+', before_str) if t] if before_str else []
            label = tokens_before[0].rstrip(':') if tokens_before else None
            return ParsedLine(line_num, raw_line, label=label, mnemonic=".STRINGZ", operands=[str_content])

        # Tokenización estándar separando por comas y espacios en blanco
        tokens = [t for t in re.split(r'[,\s]+', cleaned) if t]
        if not tokens:
            return ParsedLine(line_num, raw_line)

        first = tokens[0].upper()
        # Verificar si el primer token es una instrucción o pseudo-operación
        if first in _known_instruction_mnemonics() or first in _known_pseudoop_mnemonics() or first == "NOP":
            return ParsedLine(line_num, raw_line, label=None, mnemonic=tokens[0], operands=tokens[1:])

        # Si el primer token no es mnemónico, actúa como etiqueta
        label = tokens[0].rstrip(':')
        if len(tokens) == 1:
            return ParsedLine(line_num, raw_line, label=label, mnemonic=None, operands=[])

        return ParsedLine(line_num, raw_line, label=label, mnemonic=tokens[1], operands=tokens[2:])

    def _assemble_pseudoop(self, pline: ParsedLine, resolver=None,
                            allow_unresolved=False, operands=None) -> dict:
        """Invoca la pseudo-operación registrada y valida su descriptor de retorno."""
        pseudoop_cls = _pseudoop_class_for(pline.mnemonic)
        if pseudoop_cls is None:
            raise ValueError(f"Pseudo-operación no registrada: '{pline.mnemonic}'")

        formats = getattr(pseudoop_cls, "FORMATS", ())
        if not formats:
            raise ValueError(
                f"La pseudo-operación '{pline.mnemonic}' no declara formatos ensamblables"
            )

        operands = list(pline.operands if operands is None else operands)
        if not operands:
            for pseudo_format in formats:
                operand_types = [str(field).upper() for field in pseudo_format
                                 if str(field).upper() != "MNEMONIC"]
                if operand_types == ["COUNT"]:
                    operands = ["1"]
                    break
                if operand_types == ["STRING"]:
                    operands = [""]
                    break

        conversion_errors = []
        selected = None
        for format_idx, pseudo_format in enumerate(formats):
            operand_types = [str(field).upper() for field in pseudo_format
                             if str(field).upper() != "MNEMONIC"]
            if len(operand_types) != len(operands):
                if not (operand_types == ["EXT_SYMBOL"] and operands):
                    continue
                operand_types *= len(operands)

            try:
                arguments = [pline.mnemonic]
                for operand_type, operand in zip(operand_types, operands):
                    if operand_type == "STRING":
                        value = unescape_string(operand)
                    elif operand_type == "EXT_SYMBOL":
                        value = operand
                    elif operand_type in (
                        "ADDRESS", "COUNT", "VALUE", "VALUE_8", "VALUE_16"
                    ):
                        if is_number(operand):
                            value = parse_number(operand)
                        elif resolver is not None and operand_type.startswith("VALUE"):
                            value = resolver(operand)
                        elif allow_unresolved and operand_type.startswith("VALUE"):
                            value = 0
                        else:
                            raise ValueError(
                                f"se esperaba un valor numérico para {operand_type}: '{operand}'"
                            )
                    else:
                        value = operand
                    arguments.append(value)
            except (KeyError, ValueError) as error:
                conversion_errors.append(error)
                continue
            selected = (format_idx, arguments)
            break

        if selected is None:
            if conversion_errors:
                raise ValueError(
                    f"Operandos inválidos para '{pline.mnemonic}': {conversion_errors[0]}"
                ) from conversion_errors[0]
            expected = sorted({len(pseudo_format) - 1 for pseudo_format in formats})
            raise ValueError(
                f"Cantidad de operandos inválida para '{pline.mnemonic}': "
                f"{len(pline.operands)}; se esperaba "
                f"{', '.join(str(count) for count in expected)}"
            )

        format_idx, arguments = selected
        assemble_method = getattr(pseudoop_cls, "s_asemble_method", None)
        if not callable(assemble_method):
            raise TypeError(
                f"La pseudo-operación '{pline.mnemonic}' no implementa s_asemble_method"
            )
        result = assemble_method(format_idx, arguments)
        if not isinstance(result, dict) or "KIND" not in result or "DATA" not in result:
            raise TypeError(
                f"Retorno inválido de '{pline.mnemonic}': se esperaba un descriptor "
                "con KIND y DATA"
            )
        data = result["DATA"]
        if not isinstance(data, list) or any(
            type(value) is not int or not 0 <= value <= 0xFF
            for value in data
        ):
            raise ValueError(
                f"DATA inválido en '{pline.mnemonic}' (línea {pline.line_num}): "
                "se esperaba una lista de enteros entre 0 y 255"
            )
        if result["KIND"] == "ORIG" and len(data) != 2:
            raise ValueError(
                f"DATA inválido en '{pline.mnemonic}' (línea {pline.line_num}): "
                "ORIG debe devolver dos bytes"
            )
        return result

    def _load_all_modules(self, main_code: str, main_name: str, main_file_path: str,
                          file_map: dict, search_dirs: list) -> list:
        """Carga y analiza el módulo principal y resuelve todas sus dependencias .EXTERNAL."""
        loaded_modules = {}
        queue = [(main_name, main_code, main_file_path)]
        modules_ast = []

        while queue:
            mod_name, code, f_path = queue.pop(0)
            norm_name = self._normalize_mod_name(mod_name)
            if norm_name in loaded_modules:
                continue

            parsed_lines = []
            external_deps = []

            for line_idx, raw_line in enumerate(code.splitlines(), start=1):
                pline = self._tokenize_line(line_idx, raw_line)
                parsed_lines.append(pline)

                if pline.is_pseudoop:
                    if pline.mnemonic == ".EXTERNAL":
                        for op in pline.operands:
                            # La sintaxis es nombre_de_archivo-etiqueta o nombre_de_archivo.
                            dep_file = str(op).split('-', 1)[0].strip()
                            if dep_file and dep_file not in external_deps:
                                external_deps.append(dep_file)
                        continue

                    result = self._assemble_pseudoop(
                        pline, allow_unresolved=True
                    )
                    pline.pseudoop_result = result
                    kind = result["KIND"]
                    if kind == "END":
                        break

            mod_ast = ModuleAST(name=mod_name, lines=parsed_lines, file_path=f_path)
            mod_ast.external_dependencies = external_deps
            loaded_modules[norm_name] = mod_ast
            modules_ast.append(mod_ast)

            # Cargar dependencias externas requeridas
            for dep in external_deps:
                norm_dep = self._normalize_mod_name(dep)
                if norm_dep not in loaded_modules:
                    dep_code, dep_path = self._resolve_external_file(dep, file_map, search_dirs)
                    queue.append((dep, dep_code, dep_path))

        return modules_ast

    def _normalize_mod_name(self, name: str) -> str:
        """Normaliza el nombre del módulo para búsquedas insensibles a mayúsculas y prefijos."""
        s = name.strip().lower()
        if s.endswith(".asm"):
            s = s[:-4]
        if s.startswith("g27_"):
            s = s[4:]
        return s

    def _resolve_external_file(self, mod_name: str, file_map: dict, search_dirs: list):
        """Busca el contenido de un módulo externo en el mapa de archivos o en el disco."""
        norm = self._normalize_mod_name(mod_name)

        # 1. Buscar en file_map
        for k, v in file_map.items():
            if self._normalize_mod_name(k) == norm:
                return v, None

        # 2. Buscar en directorios de disco
        candidates = [
            f"{mod_name}.asm",
            f"{mod_name.lower()}.asm",
            f"{mod_name.upper()}.asm",
        ]
        if mod_name.lower().startswith("g27_"):
            stripped = mod_name[4:]
            candidates.extend([f"{stripped}.asm", f"{stripped.lower()}.asm", f"{stripped.upper()}.asm"])
        else:
            candidates.extend([f"g27_{mod_name}.asm", f"g27_{mod_name.lower()}.asm"])

        for sdir in search_dirs:
            if not sdir or not os.path.exists(sdir):
                continue
            # Búsqueda en el directorio raíz indicado y subdirectorios
            for root, _, files in os.walk(sdir):
                files_lower = {f.lower(): f for f in files}
                for cand in candidates:
                    cand_lower = cand.lower()
                    if cand_lower in files_lower:
                        full_path = os.path.join(root, files_lower[cand_lower])
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                                return f.read(), full_path
                        except OSError as e:
                            raise OSError(f"Error al leer el archivo externo '{full_path}': {e}")

        raise FileNotFoundError(
            f"No se pudo encontrar el archivo fuente para el módulo externo '{mod_name}'. "
            f"Directorios explorados: {search_dirs}"
        )

    # -----------------------------------------------------------------------
    # Pasada 1: Asignación de Direcciones de Memoria y Tabla de Símbolos
    # -----------------------------------------------------------------------

    def _pass_1(self, modules_ast: list) -> tuple:
        """
        Calcula las direcciones de memoria de cada instrucción/pseudo-op y genera
        la tabla global de símbolos. Maneja alineación y padding de Bytes.
        """
        current_pc = 0x3000
        orig_address = 0x3000
        symbol_table = {}

        for mod_idx, mod in enumerate(modules_ast):
            is_main = (mod_idx == 0)

            mod.start_address = current_pc
            pending_labels = []

            for pline in mod.lines:
                if pline.label:
                    pending_labels.append(pline.label)

                if pline.mnemonic is None:
                    # Línea que solo contiene etiqueta
                    continue

                if pline.mnemonic == ".EXTERNAL":
                    continue

                if pline.is_instruction:
                    data_size = 2
                    pline.pad_bytes = (-current_pc) % 2
                    current_pc += pline.pad_bytes
                else:
                    result = pline.pseudoop_result
                    if result is None:
                        result = self._assemble_pseudoop(
                            pline, allow_unresolved=True
                        )
                        pline.pseudoop_result = result
                    kind = result["KIND"]
                    if kind == "END":
                        break
                    if kind == "EXTERNAL":
                        continue
                    if kind == "ORIG":
                        if is_main:
                            orig_data = result["DATA"]
                            orig_address = (orig_data[0] << 8) | orig_data[1]
                            current_pc = orig_address
                            for lbl in pending_labels:
                                self._register_symbol(
                                    symbol_table, mod, lbl, current_pc
                                )
                            pending_labels.clear()
                        continue
                    if kind != "MEMORY":
                        raise ValueError(
                            f"Tipo de pseudo-operación no soportado: '{kind}' "
                            f"en la línea {pline.line_num}"
                        )

                    try:
                        data_size = len(bytearray(result["DATA"]))
                    except (TypeError, ValueError) as error:
                        raise ValueError(
                            f"DATA inválido en '{pline.mnemonic}' "
                            f"(línea {pline.line_num}): {error}"
                        ) from error
                    pline.pad_bytes = 0

                # Asignar dirección a las etiquetas pendientes
                pline.address = current_pc
                for lbl in pending_labels:
                    self._register_symbol(symbol_table, mod, lbl, current_pc)
                pending_labels.clear()

                current_pc += data_size

            # Asignar dirección final a etiquetas al final del módulo
            for lbl in pending_labels:
                self._register_symbol(symbol_table, mod, lbl, current_pc)
            pending_labels.clear()

            mod.end_address = current_pc

        return symbol_table, orig_address

    def _assemble_external_pseudoops(self, modules_ast: list, symbol_table: dict):
        """Ensambla cada referencia externa con su dirección ya resuelta."""
        for mod in modules_ast:
            resolver = self._create_symbol_resolver(mod, symbol_table)
            for pline in mod.lines:
                if pline.mnemonic != ".EXTERNAL":
                    continue
                if not pline.operands:
                    raise ValueError(
                        f"La directiva .EXTERNAL requiere al menos una referencia "
                        f"(línea {pline.line_num})"
                    )

                for reference in pline.operands:
                    address = resolver(reference)
                    result = self._assemble_pseudoop(
                        pline, operands=[address]
                    )
                    if result["KIND"] != "EXTERNAL":
                        raise ValueError(
                            f".EXTERNAL retornó KIND='{result['KIND']}' "
                            f"en la línea {pline.line_num}"
                        )
                    pline.pseudoop_result = result

    def _register_symbol(self, symbol_table: dict, mod: ModuleAST, label: str, address: int):
        """Registra un símbolo tanto en el ámbito local del módulo como en la tabla global."""
        mod.symbols[label] = address
        mod.symbols[label.upper()] = address
        mod.symbols[label.lower()] = address

        # Formato calificado: MODULO-ETIQUETA
        full_ref = f"{mod.name}-{label}"
        symbol_table[full_ref] = address
        symbol_table[full_ref.upper()] = address
        symbol_table[full_ref.lower()] = address

        # Variantes con y sin prefijo g27_
        if mod.name.lower().startswith("g27_"):
            stripped_ref = f"{mod.name[4:]}-{label}"
            symbol_table[stripped_ref] = address
            symbol_table[stripped_ref.upper()] = address
            symbol_table[stripped_ref.lower()] = address
        else:
            prefixed_ref = f"g27_{mod.name}-{label}"
            symbol_table[prefixed_ref] = address
            symbol_table[prefixed_ref.upper()] = address
            symbol_table[prefixed_ref.lower()] = address

        # Registro simple como fallback global si no colisiona
        if label not in symbol_table:
            symbol_table[label] = address
        if label.upper() not in symbol_table:
            symbol_table[label.upper()] = address
        if label.lower() not in symbol_table:
            symbol_table[label.lower()] = address

    # -----------------------------------------------------------------------
    # Pasada 2: Generación de Código Máquina y Resolución de Operandos
    # -----------------------------------------------------------------------

    def _pass_2(self, modules_ast: list, symbol_table: dict, orig_address: int) -> bytearray:
        """Traduce cada línea a bytes de memoria en orden contiguo."""
        emitted_bytes = bytearray()

        for mod in modules_ast:
            resolver = self._create_symbol_resolver(mod, symbol_table)

            for pline in mod.lines:
                if pline.mnemonic is None:
                    continue

                pseudo_result = None
                if pline.is_pseudoop:
                    pseudo_result = pline.pseudoop_result
                    if pseudo_result is None or pseudo_result["KIND"] == "MEMORY":
                        pseudo_result = self._assemble_pseudoop(
                            pline, resolver=resolver
                        )
                    kind = pseudo_result["KIND"]
                    if kind == "END":
                        break
                    if kind in ("ORIG", "EXTERNAL"):
                        continue
                    if kind != "MEMORY":
                        raise ValueError(
                            f"Tipo de pseudo-operación no soportado: '{kind}' "
                            f"en la línea {pline.line_num}"
                        )

                # 1. Emitir padding de byte si fue requerido para alinear
                if pline.pad_bytes > 0:
                    emitted_bytes.extend(b"\x00" * pline.pad_bytes)

                # 2. Instrucciones de máquina
                if pline.is_instruction:
                    # Soporte para pseudoinstrucción NOP (alias de BR #0)
                    if pline.mnemonic == "NOP":
                        inst_cls = _instruction_class_for("BR")
                        if inst_cls is None:
                            raise ValueError("No se encontró BR en los registros de instrucciones")
                        inst_obj = inst_cls.s_asemble_method(0, ["BR", 0])
                    else:
                        inst_cls = _instruction_class_for(pline.mnemonic)
                        if inst_cls is None:
                            raise ValueError(f"Instrucción no registrada: '{pline.mnemonic}'")
                        format_idx, args = self._match_instruction_format(
                            inst_cls, pline.mnemonic, pline.operands, pline.address, resolver
                        )
                        inst_obj = inst_cls.s_asemble_method(format_idx, args)

                    val = int(inst_obj) & 0xFFFF
                    # Formato Little-Endian para palabras de 16 bits:
                    # parte alta en dirección base, parte baja en dirección + 1
                    emitted_bytes.append((val >> 8) & 0xFF)
                    emitted_bytes.append(val & 0xFF)

                elif pseudo_result is not None:
                    try:
                        emitted_bytes.extend(bytearray(pseudo_result["DATA"]))
                    except (TypeError, ValueError) as error:
                        raise ValueError(
                            f"DATA inválido en '{pline.mnemonic}' "
                            f"(línea {pline.line_num}): {error}"
                        ) from error

        return emitted_bytes

    def _create_symbol_resolver(self, mod: ModuleAST, symbol_table: dict):
        """Crea una función de resolución de símbolos para un módulo dado."""
        def resolve(sym_str: str) -> int:
            s = sym_str.strip()

            # 1. Búsqueda local en el módulo actual
            if s in mod.symbols:
                return mod.symbols[s]
            if s.upper() in mod.symbols:
                return mod.symbols[s.upper()]
            if s.lower() in mod.symbols:
                return mod.symbols[s.lower()]

            # 2. Búsqueda global (incluyendo referencias MODULO-ETIQUETA)
            if s in symbol_table:
                return symbol_table[s]
            if s.upper() in symbol_table:
                return symbol_table[s.upper()]
            if s.lower() in symbol_table:
                return symbol_table[s.lower()]

            # 3. Búsqueda con o sin prefijo g27_
            if s.lower().startswith("g27_"):
                stripped = s[4:]
                if stripped in symbol_table:
                    return symbol_table[stripped]
                if stripped.upper() in symbol_table:
                    return symbol_table[stripped.upper()]
            else:
                prefixed = f"g27_{s}"
                if prefixed in symbol_table:
                    return symbol_table[prefixed]
                if prefixed.upper() in symbol_table:
                    return symbol_table[prefixed.upper()]

            # 4. Búsqueda de expresiones aritméticas simples: ETIQUETA + N o ETIQUETA - N
            m = re.match(r"^(.+?)\s*([+-])\s*(#?[xX0-9a-fA-F-]+)$", s)
            if m:
                base_sym = m.group(1).strip()
                sign = m.group(2)
                offset_val = parse_number(m.group(3).strip())
                base_addr = resolve(base_sym)
                return (base_addr + offset_val) if sign == '+' else (base_addr - offset_val)

            raise KeyError(
                f"Etiqueta o símbolo no encontrado: '{sym_str}' en módulo '{mod.name}'. "
                f"Símbolos disponibles: {list(mod.symbols.keys())[:10]}..."
            )
        return resolve

    def _resolve_pcoffset(self, op_str: str, current_pc: int, bits: int,
                          is_byte: bool, resolver) -> int:
        """
        Calcula el desplazamiento relativo al PC (PCOFFSET) para saltos o accesos a memoria.
        Verifica que el desplazamiento quepa en la cantidad de bits asignada.
        """
        if is_number(op_str):
            return parse_number(op_str)

        target_addr = resolver(op_str)
        pc_next = current_pc + 2

        if is_byte:
            offset = target_addr - pc_next
        else:
            diff = target_addr - pc_next
            offset = diff // 2

        min_val = -(1 << (bits - 1))
        max_val = (1 << (bits - 1)) - 1
        if not (min_val <= offset <= max_val):
            raise ValueError(
                f"PCOffset fuera de rango para {bits} bits (offset={offset}, rango=[{min_val}, {max_val}]) "
                f"al referenciar '{op_str}' (destino={target_addr:#06x}, pc+2={pc_next:#06x})"
            )
        return offset

    def _match_instruction_format(self, inst_cls, mnemonic: str, operands: list,
                                  current_pc: int, resolver) -> tuple:
        """
        Selecciona un formato a partir de FORMATS y convierte sus operandos.
        La decisión no depende del nombre ni de la jerarquía de la clase.
        """
        m = mnemonic.upper()
        formats = getattr(inst_cls, "FORMATS", ())
        if not formats:
            raise ValueError(f"La instrucción '{m}' no declara formatos ensamblables")

        candidates = []
        conversion_errors = []
        for format_idx, inst_format in enumerate(formats):
            operand_types = [str(field).upper() for field in inst_format
                             if str(field).upper() != "MNEMONIC"]
            if len(operand_types) != len(operands):
                continue
            try:
                parsed = [m]
                for operand_type, operand in zip(operand_types, operands):
                    parsed.append(self._parse_format_operand(
                        operand_type, operand, current_pc, resolver
                    ))
            except (KeyError, ValueError) as error:
                conversion_errors.append(error)
                continue
            candidates.append((format_idx, parsed))

        # Algunas familias declaran un formato por cada mnemónico (por ejemplo,
        # SHF/LSH/RSH); en ese caso el índice de ambos metadatos es el mismo.
        mnemonics = [str(name).upper()
                     for name in getattr(inst_cls, "MNEMONICS", ())]
        if len(formats) == len(mnemonics) and m in mnemonics:
            preferred_idx = mnemonics.index(m)
            for format_idx, parsed in candidates:
                if format_idx == preferred_idx:
                    return format_idx, parsed

        if candidates:
            return candidates[0]
        if conversion_errors:
            raise ValueError(
                f"Operandos inválidos para '{m}': {conversion_errors[0]}"
            ) from conversion_errors[0]

        expected = sorted({len(inst_format) - 1 for inst_format in formats})
        raise ValueError(
            f"Cantidad de operandos inválida para '{m}': {len(operands)}; "
            f"se esperaba {', '.join(str(count) for count in expected)}"
        )

    def _parse_format_operand(self, operand_type: str, operand: str,
                              current_pc: int, resolver) -> int:
        """Convierte un operando según el tipo declarado en FORMATS."""
        if operand_type == "REG":
            return parse_register(operand)
        if operand_type in ("PCOFFSET8", "PCOFFSET10", "BPCOFFSET8"):
            bits = 10 if operand_type == "PCOFFSET10" else 8
            is_byte = operand_type.startswith("BPCOFFSET")
            return self._resolve_pcoffset(
                operand, current_pc, bits=bits, is_byte=is_byte, resolver=resolver
            )
        if is_number(operand):
            return parse_number(operand)
        raise ValueError(f"se esperaba un valor numérico para {operand_type}: '{operand}'")

    # -----------------------------------------------------------------------
    # Escritura de Archivos de Salida
    # -----------------------------------------------------------------------

    def _write_output_file(self, result: AssemblyResult, output_format: str, output_file: str):
        """Escribe el archivo resultante en disco (.hex o .bin)."""
        parent = os.path.dirname(os.path.abspath(output_file))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        if output_format == "bin":
            lines = result.to_bin_lines()
        else: # "hex" por defecto
            lines = result.to_hex_lines()

        with open(output_file, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(line + '\n')

    def _write_symbol_file(self, symbol_table: dict, sym_file_path: str):
        """Genera un archivo de tabla de símbolos legible (.sym)."""
        parent = os.path.dirname(os.path.abspath(sym_file_path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        with open(sym_file_path, 'w', encoding='utf-8') as f:
            f.write("// Symbol Table - ISA-G27 Assembler\n")
            f.write(f"// {'Symbol Name':<32} {'Address':<8}\n")
            f.write(f"// {'-' * 32} {'-' * 8}\n")
            for name in sorted(symbol_table.keys()):
                addr = symbol_table[name]
                f.write(f"{name:<34} x{addr:04X}\n")


# ---------------------------------------------------------------------------
# Instancia Global por Defecto
# ---------------------------------------------------------------------------

Assemble = Assembler()


# ---------------------------------------------------------------------------
# Interfaz de Línea de Comandos (CLI)
# ---------------------------------------------------------------------------

def main():
    """Punto de entrada de línea de comandos para el ensamblador."""
    parser = argparse.ArgumentParser(
        description="Ensamblador para la arquitectura ISA-G27 (Little-Endian, direccionada por Byte)"
    )
    parser.add_argument("source", help="Archivo ensamblador (.asm) o cadena con el código fuente")
    parser.add_argument("-o", "--output", dest="output_file", default=None,
                        help="Ruta del archivo de salida (.hex, .bin)")
    parser.add_argument("-f", "--format", dest="format", choices=["hex", "bin", "list", "python"],
                        default="hex", help="Formato de salida (hex, bin, list). Por defecto: hex")
    parser.add_argument("--no-orig", dest="no_orig", action="store_true",
                        help="No incluir la dirección de inicio .ORIG en los primeros 2 bytes de salida")
    parser.add_argument("-s", "--sym", "--links", dest="links", action="store_true",
                        help="Generar archivo de tabla de símbolos (.sym)")
    parser.add_argument("-I", "--include", dest="include_dirs", action="append", default=[],
                        help="Directorios adicionales para buscar módulos externos (.EXTERNAL)")

    args = parser.parse_args()

    asm = Assembler(
        output_format=args.format,
        output_file=args.output_file,
        include_orig=not args.no_orig,
        links=args.links,
        search_dirs=args.include_dirs
    )

    try:
        res = asm(args.source)
        if args.format in ("list", "python"):
            print(res.to_hex_lines())
        else:
            print(f"Ensamblado exitoso: '{res.output_file}' ({len(res.bytes)} bytes, .ORIG {res.orig_address:#06x})")
            if args.links:
                sym_path = str(Path(res.output_file).with_suffix(".sym"))
                print(f"Archivo de símbolos generado: '{sym_path}'")
    except Exception as e:
        print(f"Error durante el ensamblado: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
