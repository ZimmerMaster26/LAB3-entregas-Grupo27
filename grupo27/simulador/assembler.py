"""Two-pass assembler and command-line interface for ISA-G27."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Callable, Iterable, Mapping, Sequence

if __package__:
    from .isa import INSTRUCTIONS, InstructionSpec, register_index
    from .pseudo_ops import PSEUDO_OPS
else:
    from isa import INSTRUCTIONS, InstructionSpec, register_index
    from pseudo_ops import PSEUDO_OPS


DEFAULT_ORIGIN = 0x3000
MEMORY_SIZE = 1 << 16
_TOKEN_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s,]+')
_LABEL_RE = re.compile(r"[A-Za-z_.$][A-Za-z0-9_.$]*\Z")


class AssemblyError(ValueError):
    """An assembly source or ISA encoding error."""

    def __init__(self, message: str, source: str = "<input>", line: int | None = None):
        self.source = source
        self.line = line
        location = f"{source}:{line}" if line is not None else source
        super().__init__(f"{location}: {message}")


@dataclass
class Statement:
    source: str
    line: int
    label: str | None
    operation: str | None
    operands: list[str]
    address: int | None = None


@dataclass
class Module:
    name: str
    path: Path | None
    statements: list[Statement]
    labels: dict[str, int] = field(default_factory=dict)
    external_specs: list[tuple[str, Statement]] = field(default_factory=list)
    end_address: int = 0


@dataclass(frozen=True)
class ExternalTarget:
    module: Module
    label: str
    declaration: Statement


@dataclass(frozen=True)
class AssemblyResult:
    """Assembled bytes, starting address, and symbol table."""

    origin: int
    data: bytes
    symbols: Mapping[str, int]
    format: str
    modules: tuple[str, ...]

    @property
    def text(self) -> str:
        """Return the load address followed by one formatted byte per line."""
        values = [self.origin >> 8, self.origin & 0xFF, *self.data]
        if self.format == "hex":
            return "".join(f"{value:02X}\n" for value in values)
        if self.format == "bin":
            return "".join(f"{value:08b}\n" for value in values)
        return "".join(f"{value}\n" for value in values)

    def write(self, path: str | Path) -> Path:
        output = Path(path)
        output.write_text(self.text, encoding="ascii", newline="\n")
        return output


class Assembler:
    """Assemble ISA-G27 source text, files, or named source collections."""

    def __init__(
        self,
        include_dirs: Iterable[str | Path] = (),
        external_source_provider: Callable[[str], str | None] | None = None,
    ):
        self.include_dirs = tuple(Path(directory).resolve() for directory in include_dirs)
        self.external_source_provider = external_source_provider
        self._modules: list[Module] = []
        self._module_index: dict[str, Module] = {}
        self._source_map: dict[str, str] = {}
        self._queued_external_texts: list[str] = []
        self._source_paths: list[Path] = []
        self._external_targets: dict[int, list[ExternalTarget]] = {}
        self._resolved_external_modules: dict[tuple[int, str], Module] = {}
        self._symbols: dict[str, int] = {}
        self._memory: dict[int, int] = {}
        self._origin = DEFAULT_ORIGIN

    def assemble(
        self,
        source: str | Path | Mapping[str, str] | Sequence[str | Path],
        output_format: str = "hex",
    ) -> AssemblyResult:
        """Assemble a file, source string, or mapping (main module first)."""
        output_format = output_format.lower().lstrip(".")
        if output_format not in {"hex", "bin", "lst"}:
            raise ValueError("el formato debe ser 'hex', 'bin' o 'lst'")

        self._reset()
        main_name, main_text, main_path, supplied, external_texts = self._read_main_source(source)
        self._source_map = {self._source_key(name): text for name, text in supplied.items()}
        self._queued_external_texts = list(external_texts)
        self._source_paths = [main_path.parent] if main_path else []
        self._source_paths.extend(self.include_dirs)
        self._source_paths.append(Path.cwd())
        self._add_module(main_name, main_text, main_path)

        origin_directives = self._find_origin_directives(self._modules[0])
        if len(origin_directives) > 1:
            statement = origin_directives[1]
            self._error(statement, ".ORIG solo puede aparecer una vez en el programa principal")
        if origin_directives:
            statement = origin_directives[0]
            if len(statement.operands) > 1:
                self._error(statement, ".ORIG acepta cero o un argumento")
            if statement.operands:
                self._origin = self._parse_number(statement.operands[0], statement)
        if not 0 <= self._origin < MEMORY_SIZE:
            raise AssemblyError("la dirección .ORIG debe estar entre 0 y 65535", main_name)
        if self._origin & 1:
            raise AssemblyError(".ORIG debe ser una dirección par", main_name)

        self._layout_modules()
        self._resolve_external_targets()
        self._encode_modules()
        end = max(self._memory, default=self._origin - 1) + 1
        data = bytes(self._memory.get(address, 0) for address in range(self._origin, end))
        return AssemblyResult(
            self._origin,
            data,
            dict(self._symbols),
            output_format,
            tuple(module.name for module in self._modules),
        )

    def assemble_file(
        self,
        path: str | Path,
        output_format: str = "hex",
        output_path: str | Path | None = None,
    ) -> AssemblyResult:
        """Assemble a source file and write its object file."""
        input_path = Path(path)
        result = self.assemble(input_path, output_format)
        destination = Path(output_path) if output_path else input_path.with_suffix(
            f".{result.format}"
        )
        result.write(destination)
        return result

    def _reset(self) -> None:
        self._modules = []
        self._module_index = {}
        self._source_map = {}
        self._queued_external_texts = []
        self._source_paths = []
        self._external_targets = {}
        self._resolved_external_modules = {}
        self._symbols = {}
        self._memory = {}
        self._origin = DEFAULT_ORIGIN

    def _read_main_source(
        self, source: str | Path | Mapping[str, str] | Sequence[str | Path]
    ) -> tuple[str, str, Path | None, Mapping[str, str], Sequence[str]]:
        if isinstance(source, Mapping):
            if not source:
                raise ValueError("la colección de fuentes está vacía")
            name, text = next(iter(source.items()))
            if any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in source.items()
            ):
                raise TypeError("los nombres y contenidos de las fuentes deben ser texto")
            return str(name), text, None, source, ()

        if isinstance(source, Path):
            path = source.resolve()
            return str(path), self._read_file(path), path, {}, ()

        if isinstance(source, Sequence) and not isinstance(source, str):
            if not source:
                raise ValueError("la colección de fuentes está vacía")
            main_name, main_text, main_path, _, _ = self._read_main_source(source[0])
            supplied: dict[str, str] = {}
            queued: list[str] = []
            for item in source[1:]:
                if isinstance(item, Path) or (
                    isinstance(item, str) and "\n" not in item and Path(item).is_file()
                ):
                    path = Path(item).resolve()
                    supplied[str(path)] = self._read_file(path)
                elif isinstance(item, str):
                    queued.append(item)
                else:
                    raise TypeError("cada fuente debe ser texto o una ruta")
            return main_name, main_text, main_path, supplied, queued

        if not isinstance(source, str):
            raise TypeError("source debe ser texto, una ruta o un mapeo de fuentes")
        possible_path = Path(source)
        if "\n" not in source and "\r" not in source:
            if possible_path.is_file():
                path = possible_path.resolve()
                return str(path), self._read_file(path), path, {}, ()
            if possible_path.suffix.lower() == ".asm":
                raise FileNotFoundError(possible_path)
        return "<memory>", source, None, {}, ()

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise OSError(f"no se pudo leer el archivo '{path}': {error}") from error

    @staticmethod
    def _source_key(name: str) -> str:
        normalized = str(name).replace("\\", "/")
        if normalized.lower().endswith(".asm"):
            normalized = normalized[:-4]
        return normalized.casefold()

    def _add_module(self, name: str, text: str, path: Path | None) -> Module:
        key = self._source_key(name)
        if key in self._module_index:
            return self._module_index[key]
        module = Module(name, path, self._parse_source(name, text))
        self._modules.append(module)
        self._module_index[key] = module
        if path:
            self._module_index[self._source_key(path.stem)] = module
            self._module_index[self._source_key(str(path))] = module
        return module

    def _parse_source(self, source: str, text: str) -> list[Statement]:
        statements = []
        known_operations = set(INSTRUCTIONS) | set(PSEUDO_OPS)
        for line_number, original in enumerate(text.splitlines(), start=1):
            code = self._without_comment(original).strip()
            if not code:
                continue
            tokens = _TOKEN_RE.findall(code)
            if not tokens:
                continue

            label = None
            first = tokens[0]
            if first.endswith(":"):
                label = first[:-1]
                tokens = tokens[1:]
                if not _LABEL_RE.fullmatch(label):
                    raise AssemblyError(f"etiqueta inválida: {label}", source, line_number)
            elif first.upper() not in known_operations:
                if first.startswith("."):
                    raise AssemblyError(f"pseudo operación desconocida: {first}", source, line_number)
                label = first
                tokens = tokens[1:]
                if not _LABEL_RE.fullmatch(label):
                    raise AssemblyError(f"etiqueta inválida: {label}", source, line_number)

            operation = tokens[0].upper() if tokens else None
            if operation is not None and operation not in known_operations:
                if operation.startswith("."):
                    raise AssemblyError(
                        f"pseudo operación desconocida: {operation}", source, line_number
                    )
                raise AssemblyError(f"instrucción desconocida: {operation}", source, line_number)
            operands = tokens[1:] if operation else []
            statements.append(
                Statement(source, line_number, label, operation, operands)
            )
            if operation == ".END":
                break
        if not any(statement.operation == ".END" for statement in statements):
            raise AssemblyError("falta la pseudo operación obligatoria .END", source)
        origin_directives = [
            statement for statement in statements if statement.operation == ".ORIG"
        ]
        if not origin_directives:
            raise AssemblyError("falta la pseudo operación obligatoria .ORIG", source)
        if len(origin_directives) > 1:
            self._error(origin_directives[1], ".ORIG solo puede aparecer una vez")
        return statements

    @staticmethod
    def _without_comment(line: str) -> str:
        quote = None
        escaped = False
        for index, character in enumerate(line):
            if escaped:
                escaped = False
            elif character == "\\" and quote:
                escaped = True
            elif quote and character == quote:
                quote = None
            elif not quote and character in {"'", '"'}:
                quote = character
            elif not quote and character == ";":
                return line[:index]
        return line

    def _find_origin_directives(self, module: Module) -> list[Statement]:
        directives = []
        for statement in module.statements:
            if statement.operation == ".END":
                break
            if statement.operation == ".ORIG":
                directives.append(statement)
        return directives

    def _layout_modules(self) -> None:
        cursor = self._origin
        index = 0
        while index < len(self._modules):
            module = self._modules[index]
            if index:
                cursor = self._align(cursor)
            cursor = self._layout_module(module, cursor)
            for external_spec, statement in module.external_specs:
                target_name, _ = self._split_external(external_spec, statement)
                target_module = self._find_external_module(target_name, statement)
                self._resolved_external_modules[(id(module), external_spec)] = target_module
            index += 1

    def _layout_module(self, module: Module, start: int) -> int:
        address = start
        pending_labels: list[Statement] = []
        ended = False
        for statement in module.statements:
            operation = statement.operation
            if ended:
                break
            if operation == ".ORIG":
                if len(statement.operands) > 1:
                    self._error(statement, ".ORIG acepta cero o un argumento")
                if statement.label:
                    self._error(statement, "no se puede asociar una etiqueta a .ORIG")
                continue
            if operation == ".END":
                self._require_operands(statement, 0)
                if statement.label:
                    pending_labels.append(statement)
                for label_statement in pending_labels:
                    self._define_label(module, label_statement, address)
                pending_labels.clear()
                ended = True
                continue
            if operation == ".EXTERNAL":
                self._require_operands(statement, 1)
                if statement.label:
                    self._error(statement, "no se puede asociar una etiqueta a .EXTERNAL")
                module.external_specs.append((statement.operands[0], statement))
                continue
            if operation is None:
                if statement.label:
                    pending_labels.append(statement)
                continue

            size, aligned = self._statement_size(statement)
            if aligned and address & 1:
                address += 1
            statement.address = address
            for label_statement in pending_labels:
                self._define_label(module, label_statement, address)
            pending_labels.clear()
            if statement.label:
                self._define_label(module, statement, address)
            if address + size > MEMORY_SIZE:
                self._error(statement, "el programa excede el espacio de memoria")
            address += size

        for label_statement in pending_labels:
            self._define_label(module, label_statement, address)
        module.end_address = address
        return address

    def _statement_size(self, statement: Statement) -> tuple[int, bool]:
        operation = statement.operation
        if operation in INSTRUCTIONS:
            return 2, True
        spec = PSEUDO_OPS[operation]
        if spec.size == "word":
            self._require_operands(statement, 1)
            return 2, spec.aligned
        if spec.size == "byte":
            self._require_operands(statement, 1)
            return 1, spec.aligned
        if spec.size == "words":
            self._require_operands(statement, 1)
            return 2 * self._nonnegative_count(statement.operands[0], statement), spec.aligned
        if spec.size == "bytes":
            self._require_operands(statement, 1)
            return self._nonnegative_count(statement.operands[0], statement), spec.aligned
        if spec.size == "string":
            self._require_operands(statement, 1)
            size = len(self._parse_string(statement.operands[0], statement).encode("latin-1")) + 1
            return size, spec.aligned
        self._error(statement, f"pseudo operación {operation} no puede generar datos aquí")
        raise AssertionError("unreachable")

    def _define_label(self, module: Module, statement: Statement, address: int) -> None:
        label = statement.label
        if label is None:
            return
        key = label.upper()
        if key in module.labels:
            self._error(statement, f"etiqueta duplicada: {label}")
        module.labels[key] = address

    def _resolve_external_targets(self) -> None:
        for module in self._modules:
            targets = []
            for external_spec, statement in module.external_specs:
                _, target_label = self._split_external(external_spec, statement)
                external_module = self._resolved_external_modules[(id(module), external_spec)]
                targets.append(ExternalTarget(external_module, target_label.upper(), statement))
            self._external_targets[id(module)] = targets

        for module in self._modules:
            for target in self._external_targets[id(module)]:
                if target.label not in target.module.labels:
                    self._error(
                        target.declaration,
                        f"el módulo '{target.module.name}' no define la etiqueta "
                        f"'{target.label}'",
                    )
                if target.label in module.labels:
                    self._error(
                        target.declaration,
                        f"la etiqueta externa '{target.label}' está oculta por una etiqueta local",
                    )
                current = self._symbols.get(target.label)
                value = target.module.labels[target.label]
                if current is not None and current != value:
                    self._error(
                        target.declaration,
                        f"la etiqueta externa '{target.label}' es ambigua; use nombres únicos",
                    )
                self._symbols[target.label] = value
            for label, address in module.labels.items():
                self._symbols.setdefault(label, address)

    @staticmethod
    def _split_external(value: str, statement: Statement) -> tuple[str, str]:
        if "-" not in value:
            raise AssemblyError(
                ".EXTERNAL requiere nombre_de_archivo-etiqueta",
                statement.source,
                statement.line,
            )
        module_name, label = value.rsplit("-", 1)
        if not module_name or not _LABEL_RE.fullmatch(label):
            raise AssemblyError(
                f"referencia externa inválida: {value}",
                statement.source,
                statement.line,
            )
        return module_name, label

    def _find_external_module(self, requested: str, statement: Statement) -> Module:
        direct = self._module_index.get(self._source_key(requested))
        if direct:
            return direct

        supplied = self._source_map.get(self._source_key(requested))
        if supplied is not None:
            return self._add_module(requested, supplied, None)

        normalized = requested.replace("\\", "/")
        requested_path = PurePosixPath(normalized)
        if (
            requested_path.is_absolute()
            or PureWindowsPath(normalized).drive
            or ".." in requested_path.parts
        ):
            self._error(statement, "la ruta externa debe estar dentro de un directorio de búsqueda")
        candidate_paths: list[Path] = []
        roots = list(dict.fromkeys(self._source_paths))
        if statement.source != "<memory>":
            source_path = Path(statement.source)
            if source_path.is_absolute():
                roots.insert(0, source_path.parent)
        for root in roots:
            candidate = root.joinpath(*normalized.split("/"))
            if candidate.suffix.lower() != ".asm":
                candidate = Path(f"{candidate}.asm")
            if candidate.is_file():
                candidate_paths.append(candidate.resolve())
            if not candidate_paths and root.is_dir():
                requested_key = self._source_key(normalized)
                for found in root.rglob("*.asm"):
                    relative_key = self._source_key(str(found.relative_to(root)))
                    if relative_key == requested_key:
                        candidate_paths.append(found.resolve())
                        break
                if candidate_paths:
                    break

        if candidate_paths:
            path = candidate_paths[0]
            return self._add_module(str(path), self._read_file(path), path)

        if self._queued_external_texts:
            return self._add_module(requested, self._queued_external_texts.pop(0), None)
        if self.external_source_provider:
            text = self.external_source_provider(requested)
            if text is not None:
                return self._add_module(requested, text, None)
        self._error(statement, f"no se encontró el módulo externo '{requested}' (.asm)")
        raise AssertionError("unreachable")

    def _encode_modules(self) -> None:
        for module in self._modules:
            for statement in module.statements:
                if statement.operation is None or statement.address is None:
                    continue
                address = statement.address
                if statement.operation in INSTRUCTIONS:
                    word = self._encode_instruction(statement, module, address)
                    self._write_word(address, word, statement)
                elif statement.operation == ".FILL":
                    value = self._resolve_value(statement.operands[0], module, statement)
                    if not -0x8000 <= value <= 0xFFFF:
                        self._error(statement, ".FILL requiere un valor entre -32768 y 65535")
                    self._write_word(address, value & 0xFFFF, statement)
                elif statement.operation == ".FILLB":
                    value = self._resolve_value(statement.operands[0], module, statement)
                    if not -0x80 <= value <= 0xFF:
                        self._error(statement, ".FILLB requiere un valor entre -128 y 255")
                    self._write_byte(address, value & 0xFF, statement)
                elif statement.operation == ".BLKW":
                    count = self._nonnegative_count(statement.operands[0], statement)
                    for offset in range(count * 2):
                        self._write_byte(address + offset, 0, statement)
                elif statement.operation == ".BLKB":
                    count = self._nonnegative_count(statement.operands[0], statement)
                    for offset in range(count):
                        self._write_byte(address + offset, 0, statement)
                elif statement.operation == ".STRINGZ":
                    encoded = self._parse_string(statement.operands[0], statement).encode("latin-1")
                    for offset, value in enumerate(encoded + b"\0"):
                        self._write_byte(address + offset, value, statement)

    def _encode_instruction(self, statement: Statement, module: Module, pc: int) -> int:
        mnemonic = statement.operation
        spec = INSTRUCTIONS[mnemonic]
        try:
            return self._encode_by_form(spec, mnemonic, statement, module, pc)
        except AssemblyError:
            raise
        except (ValueError, IndexError) as error:
            self._error(statement, str(error))
        raise AssertionError("unreachable")

    def _encode_by_form(
        self, spec: InstructionSpec, mnemonic: str, statement: Statement, module: Module, pc: int
    ) -> int:
        operands = statement.operands
        opcode = spec.opcode << 11
        form = spec.form

        if form == "no_operands":
            self._require_operands(statement, 0)
            return opcode
        if form == "branch_nzp":
            self._require_operands(statement, 1)
            flags = 7
            if mnemonic not in {"BR", "BRNZP"}:
                flags = sum(bit for flag, bit in (("N", 4), ("Z", 2), ("P", 1)) if flag in mnemonic[2:])
            offset = self._pc_offset(operands[0], module, pc, 8, True, statement)
            return opcode | (flags << 8) | offset
        if form == "branch_oc":
            self._require_operands(statement, 1)
            offset = self._pc_offset(operands[0], module, pc, 8, True, statement)
            return opcode | ((1 if mnemonic == "BRC" else 0) << 10) | offset
        if form == "alu_imm4":
            self._require_operands(statement, 3)
            dr, sr1 = register_index(operands[0]), register_index(operands[1])
            if operands[2].upper().startswith("R"):
                sr2 = register_index(operands[2])
                return opcode | (dr << 8) | (sr1 << 5) | sr2
            immediate = self._parse_number(operands[2], statement)
            return opcode | (dr << 8) | (sr1 << 5) | 0x10 | self._signed_field(
                immediate, 4, statement
            )
        if form in {"pc_word", "pc_byte", "pc_word_store", "pc_byte_store", "lea"}:
            byte = "byte" in form
            self._require_operands(statement, 2)
            reg = register_index(operands[0])
            offset = self._pc_offset(operands[1], module, pc, 8, not byte, statement)
            return opcode | (reg << 8) | offset
        if form == "jsr":
            self._require_operands(statement, 1)
            offset = self._pc_offset(operands[0], module, pc, 10, True, statement)
            return opcode | 0x400 | offset
        if form == "base_jump_link":
            self._require_operands(statement, 1)
            return opcode | (register_index(operands[0]) << 5)
        if form == "base_jump":
            self._require_operands(statement, 1)
            return opcode | (register_index(operands[0]) << 5)
        if form in {"base_word", "base_byte", "base_word_store", "base_byte_store"}:
            self._require_operands(statement, 3)
            reg, base = register_index(operands[0]), register_index(operands[1])
            offset = self._parse_number(operands[2], statement)
            self._unsigned_field(offset, 5, statement)
            return opcode | (reg << 8) | (base << 5) | offset
        if form == "not":
            self._require_operands(statement, 2)
            dr, sr = register_index(operands[0]), register_index(operands[1])
            return opcode | (dr << 8) | (sr << 5) | 0x1F
        if form == "ret":
            self._require_operands(statement, 0)
            return opcode | (7 << 5)
        if form == "sext":
            self._require_operands(statement, 3)
            dr, sr1 = register_index(operands[0]), register_index(operands[1])
            if operands[2].upper().startswith("R"):
                sr2 = register_index(operands[2])
                return opcode | (dr << 8) | (sr1 << 5) | sr2
            bits = self._parse_number(operands[2], statement)
            self._unsigned_field(bits, 4, statement)
            return opcode | (dr << 8) | (sr1 << 5) | 0x10 | bits
        if form == "bext":
            self._require_operands(statement, 2)
            dr, sr = register_index(operands[0]), register_index(operands[1])
            return opcode | (dr << 8) | (sr << 5) | 0x18
        if form == "shift5":
            self._require_operands(statement, 3)
            dr, sr = register_index(operands[0]), register_index(operands[1])
            shift = self._signed_field(self._parse_number(operands[2], statement), 5, statement)
            return opcode | (dr << 8) | (sr << 5) | shift
        if form == "shift_left":
            self._require_operands(statement, 3)
            dr, sr = register_index(operands[0]), register_index(operands[1])
            amount = self._parse_number(operands[2], statement)
            self._unsigned_field(amount, 4, statement)
            return opcode | (dr << 8) | (sr << 5) | amount
        if form == "shift_right":
            self._require_operands(statement, 3)
            dr, sr = register_index(operands[0]), register_index(operands[1])
            amount = self._parse_number(operands[2], statement)
            self._unsigned_field(amount, 4, statement)
            return opcode | (dr << 8) | (sr << 5) | 0x10 | amount
        if form in {"shift_register", "shift_register_overflow"}:
            self._require_operands(statement, 3)
            dr, sr1, sr2 = (register_index(token) for token in operands)
            mode = 0x10 if form == "shift_register_overflow" else 0
            return opcode | (dr << 8) | (sr1 << 5) | mode | sr2
        if form == "trap":
            self._require_operands(statement, 1)
            vector = self._parse_number(operands[0], statement)
            self._unsigned_field(vector, 8, statement)
            return opcode | vector
        if form == "trap_alias":
            self._require_operands(statement, 0)
            return opcode | (0x20 if mnemonic == "GETC" else 0x21)
        self._error(statement, f"formato de instrucción no implementado: {form}")
        raise AssertionError("unreachable")

    def _resolve_value(self, token: str, module: Module, statement: Statement) -> int:
        try:
            return self._parse_number(token, statement)
        except AssemblyError:
            pass

        match = re.fullmatch(
            r"([A-Za-z_.$][A-Za-z0-9_.$]*)(?:([+-])((?:#|x|X|b|B)?[0-9A-Fa-f]+))?",
            token,
        )
        if not match:
            self._error(statement, f"valor o etiqueta inválida: {token}")
        name, sign, adjustment_text = match.groups()
        key = name.upper()
        if key in module.labels:
            value = module.labels[key]
        else:
            candidates = [
                target for target in self._external_targets.get(id(module), [])
                if target.label == key
            ]
            if not candidates:
                self._error(statement, f"etiqueta no definida: {name}")
            addresses = {target.module.labels[target.label] for target in candidates}
            if len(addresses) != 1:
                self._error(statement, f"referencia externa ambigua: {name}")
            value = addresses.pop()
        if adjustment_text:
            adjustment = self._parse_number(adjustment_text, statement)
            value += adjustment if sign == "+" else -adjustment
        return value

    def _pc_offset(
        self,
        token: str,
        module: Module,
        pc: int,
        width: int,
        word_offset: bool,
        statement: Statement,
    ) -> int:
        target = self._resolve_value(token, module, statement)
        delta = target - (pc + 2)
        if word_offset:
            if delta & 1:
                self._error(statement, f"la dirección '{token}' no está alineada a palabra")
            delta //= 2
        return self._signed_field(delta, width, statement)

    @staticmethod
    def _parse_number(token: str, statement: Statement) -> int:
        value = token
        sign = 1
        if value.startswith(("+", "-")):
            if value[0] == "-":
                sign = -1
            value = value[1:]
        if value.startswith("#"):
            base, digits = 10, value[1:]
        elif value[:1].lower() == "x":
            base, digits = 16, value[1:]
        elif value[:1].lower() == "b":
            base, digits = 2, value[1:]
        elif value.lower().startswith("0x"):
            base, digits = 16, value[2:]
        elif value.lower().startswith("0b"):
            base, digits = 2, value[2:]
        else:
            base, digits = 10, value
        try:
            if not digits:
                raise ValueError
            return sign * int(digits, base)
        except ValueError:
            raise AssemblyError(f"número inválido: {token}", statement.source, statement.line)

    def _nonnegative_count(self, token: str, statement: Statement) -> int:
        count = self._parse_number(token, statement)
        if count < 0:
            self._error(statement, "el tamaño reservado no puede ser negativo")
        return count

    @staticmethod
    def _signed_field(value: int, width: int, statement: Statement) -> int:
        minimum, maximum = -(1 << (width - 1)), (1 << (width - 1)) - 1
        if not minimum <= value <= maximum:
            raise AssemblyError(
                f"valor {value} fuera de rango con signo de {width} bits [{minimum}, {maximum}]",
                statement.source,
                statement.line,
            )
        return value & ((1 << width) - 1)

    @staticmethod
    def _unsigned_field(value: int, width: int, statement: Statement) -> int:
        maximum = (1 << width) - 1
        if not 0 <= value <= maximum:
            raise AssemblyError(
                f"valor {value} fuera de rango sin signo de {width} bits [0, {maximum}]",
                statement.source,
                statement.line,
            )
        return value

    @staticmethod
    def _parse_string(token: str, statement: Statement) -> str:
        try:
            value = ast.literal_eval(token)
        except (SyntaxError, ValueError) as error:
            raise AssemblyError(
                f"cadena inválida: {token}", statement.source, statement.line
            ) from error
        if not isinstance(value, str):
            raise AssemblyError(
                ".STRINGZ requiere una cadena entre comillas",
                statement.source,
                statement.line,
            )
        try:
            value.encode("latin-1")
        except UnicodeEncodeError as error:
            raise AssemblyError(
                ".STRINGZ solo admite caracteres de 8 bits",
                statement.source,
                statement.line,
            ) from error
        return value

    @staticmethod
    def _require_operands(statement: Statement, count: int) -> None:
        if len(statement.operands) != count:
            raise AssemblyError(
                f"{statement.operation} requiere {count} operando(s), "
                f"se recibieron {len(statement.operands)}",
                statement.source,
                statement.line,
            )

    @staticmethod
    def _align(address: int) -> int:
        return address + (address & 1)

    def _write_word(self, address: int, value: int, statement: Statement) -> None:
        self._write_byte(address, (value >> 8) & 0xFF, statement)
        self._write_byte(address + 1, value & 0xFF, statement)

    def _write_byte(self, address: int, value: int, statement: Statement) -> None:
        if not 0 <= address < MEMORY_SIZE:
            self._error(statement, "escritura fuera del espacio de memoria")
        if address in self._memory:
            self._error(statement, f"dirección de memoria duplicada: x{address:04X}")
        self._memory[address] = value

    @staticmethod
    def _error(statement: Statement, message: str) -> None:
        raise AssemblyError(message, statement.source, statement.line)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ensamblador de la ISA-G27")
    parser.add_argument("source", help="archivo fuente .asm")
    parser.add_argument(
        "-f", "--format", choices=("hex", "bin", "lst"), default="hex",
        help="formato de salida (por defecto: hex)",
    )
    parser.add_argument("-o", "--output", help="ruta del archivo de salida")
    parser.add_argument(
        "-I", "--include", action="append", default=[],
        help="directorio adicional para buscar módulos .EXTERNAL",
    )
    args = parser.parse_args(argv)
    try:
        assembler = Assembler(include_dirs=args.include)
        assembler.assemble_file(args.source, args.format, args.output)
    except (AssemblyError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
