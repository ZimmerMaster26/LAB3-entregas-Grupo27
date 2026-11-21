"""Importable and command-line ISA-G27 simulator."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .assembler import Assembler, AssemblyError, AssemblyResult
from .execution import (
    EXECUTION_MODES,
    ExecutionContext,
    SimulationResult,
    SimulationStats,
)
from .machine import ADDRESS_SPACE, Machine
from .predictors import BranchPredictor, create_predictor


DEFAULT_ORIGIN = 0x3000
DEFAULT_OS = Path(__file__).with_name("os.asm")


@dataclass(frozen=True)
class _Image:
    origin: int
    data: bytes
    carries_origin: bool


class Simulator:
    """Load and execute ISA-G27 programs using the configured execution mode."""

    def __init__(
        self,
        program: str | Path | bytes | bytearray | Sequence[int | str] | AssemblyResult,
        *,
        program_format: str = "auto",
        origin: int | None = None,
        use_origin_header: bool = True,
        mode: str = "single",
        predictor: str | BranchPredictor = "never",
        load_os: bool = True,
        os_source: str | Path | None = None,
        include_dirs: Iterable[str | Path] = (),
        input_text: str | bytes = "",
        input_provider: Callable[[], str | bytes | None] | None = None,
        output_callback: Callable[[str], None] | None = None,
    ):
        self.mode_name = self._normalize_mode(mode)
        try:
            self.execution_mode = EXECUTION_MODES[self.mode_name]()
        except KeyError as error:
            raise ValueError(
                f"modo desconocido: {mode}; use single, multicycle o pipeline"
            ) from error
        self.predictor = create_predictor(predictor)
        self.machine = Machine(input_text, input_provider, output_callback)
        self.memory = self.machine.memory
        self.include_dirs = tuple(include_dirs)
        self._loaded_regions: list[tuple[int, int]] = []
        self.os_image: _Image | None = None

        if load_os:
            self.os_image = self._load_os(os_source)
            self._load_image(self.os_image.origin, self.os_image.data)

        image, assembled_origin = self._load_program(program, program_format)
        if image.carries_origin and use_origin_header and len(image.data) < 2:
            raise ValueError("el programa debe incluir dos bytes de origen")
        if origin is not None:
            program_origin = self._validate_origin(origin)
        elif use_origin_header and assembled_origin is not None:
            program_origin = self._validate_origin(assembled_origin)
        elif use_origin_header and image.carries_origin:
            program_origin = self._validate_origin(image.origin)
        else:
            program_origin = DEFAULT_ORIGIN
        if image.carries_origin and not isinstance(program, AssemblyResult):
            image_data = image.data[2:] if use_origin_header else image.data
        else:
            image_data = image.data
        self.program_origin = program_origin
        self._load_image(program_origin, image_data)
        self.machine.reset(program_origin, user_mode=True)

    @property
    def output(self) -> str:
        return self.machine.output

    @property
    def registers(self) -> tuple[int, ...]:
        return tuple(self.machine.registers)

    def request_interrupt(self, vector: int, priority: int = 1) -> None:
        self.machine.request_interrupt(vector, priority)

    def run(self, max_instructions: int = 100_000) -> SimulationResult:
        if max_instructions <= 0:
            raise ValueError("max_instructions debe ser mayor que cero")
        before_instructions = self.machine.instructions_executed
        before_reads = self.memory.memory_reads
        before_writes = self.memory.memory_writes
        before_traps = self.machine.traps_taken
        before_interrupts = self.machine.interrupts_taken

        cycles, predictions, mispredictions = self.execution_mode.run(
            ExecutionContext(
                self.machine,
                self._is_executable,
                max_instructions,
                self.predictor,
            )
        )
        instructions = self.machine.instructions_executed - before_instructions
        stopped_at_limit = instructions >= max_instructions and self._is_executable(
            self.machine.pc
        )
        stats = SimulationStats(
            instructions=instructions,
            cycles=cycles,
            memory_reads=self.memory.memory_reads - before_reads,
            memory_writes=self.memory.memory_writes - before_writes,
            traps=self.machine.traps_taken - before_traps,
            interrupts=self.machine.interrupts_taken - before_interrupts,
            branch_predictions=predictions,
            branch_mispredictions=mispredictions,
        )
        return SimulationResult(
            stats=stats,
            output=self.machine.output,
            registers=tuple(self.machine.registers),
            pc=self.machine.pc,
            stop_reason=(
                "halt" if self.machine.halted
                else "instruction_limit" if stopped_at_limit
                else "program_end"
            ),
        )

    def _load_program(
        self,
        program: str | Path | bytes | bytearray | Sequence[int | str] | AssemblyResult,
        program_format: str,
    ) -> tuple[_Image, int | None]:
        if isinstance(program, AssemblyResult):
            return _Image(program.origin, program.data, False), program.origin

        if isinstance(program, Path):
            image = self._load_path(program, program_format)
            assembled_origin = image.origin if program.suffix.lower() == ".asm" else None
            return image, assembled_origin
        if isinstance(program, str):
            path = Path(program)
            if "\n" not in program and "\r" not in program and path.is_file():
                image = self._load_path(path, program_format)
                assembled_origin = image.origin if path.suffix.lower() == ".asm" else None
                return image, assembled_origin
            return self._parse_object_text(program, program_format), None
        if isinstance(program, (bytes, bytearray)):
            return _Image(0, bytes(program), True), None
        if isinstance(program, Sequence):
            if all(isinstance(item, int) for item in program):
                data = self._validate_bytes(program)
            elif all(isinstance(item, str) for item in program):
                data = self._parse_object_text("\n".join(program), program_format).data
            else:
                raise TypeError("el programa debe contener bytes o líneas de texto")
            return _Image(0, data, True), None
        raise TypeError("program debe ser texto, ruta, bytes, lista o AssemblyResult")

    def _load_path(self, path: Path, program_format: str) -> _Image:
        if path.suffix.lower() == ".asm":
            result = Assembler(include_dirs=self.include_dirs).assemble(path)
            return _Image(result.origin, result.data, False)
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise OSError(f"no se pudo leer el programa '{path}': {error}") from error
        selected_format = path.suffix.lower().lstrip(".")
        if selected_format not in {"hex", "bin", "lst"}:
            selected_format = program_format
        return self._parse_object_text(content, selected_format)

    def _load_os(self, os_source: str | Path | None) -> _Image:
        source = Path(os_source) if os_source else DEFAULT_OS
        if source.suffix.lower() == ".asm":
            result = Assembler(include_dirs=self.include_dirs).assemble(source)
            return _Image(result.origin, result.data, False)
        try:
            content = source.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise OSError(f"no se pudo leer el sistema operativo '{source}': {error}") from error
        selected_format = source.suffix.lower().lstrip(".")
        if selected_format not in {"hex", "bin", "lst"}:
            selected_format = "auto"
        return self._image_from_object_text(content, selected_format)

    @classmethod
    def _parse_object_text(cls, text: str, object_format: str) -> _Image:
        object_format = object_format.lower().lstrip(".")
        if object_format not in {"auto", "hex", "bin", "lst"}:
            raise ValueError("program_format debe ser auto, hex, bin o lst")
        values = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            token = line.split(";", 1)[0].strip()
            if not token:
                continue
            try:
                values.append(cls._parse_byte(token, object_format))
            except ValueError as error:
                raise ValueError(f"byte inválido en línea {line_number}: {token}") from error
        data = bytes(values)
        origin = (data[0] << 8) | data[1] if len(data) >= 2 else 0
        return _Image(origin, data, True)

    @classmethod
    def _image_from_object_text(cls, text: str, object_format: str) -> _Image:
        image = cls._parse_object_text(text, object_format)
        if len(image.data) < 2:
            raise ValueError("la imagen del SO debe incluir dos bytes de origen")
        origin = (image.data[0] << 8) | image.data[1]
        return _Image(origin, image.data[2:], False)

    @staticmethod
    def _parse_byte(token: str, object_format: str) -> int:
        value = token
        selected = object_format
        if value[:1].lower() == "x":
            selected, value = "hex", value[1:]
        elif value.lower().startswith("0x"):
            selected, value = "hex", value[2:]
        elif value.lower().startswith("0b"):
            selected, value = "bin", value[2:]
        elif selected == "auto":
            if len(value) == 8 and set(value) <= {"0", "1"}:
                selected = "bin"
            elif len(value) == 2 or any(character in "abcdefABCDEF" for character in value):
                selected = "hex"
            else:
                selected = "lst"
        base = {"hex": 16, "bin": 2, "lst": 10}.get(selected)
        if base is None:
            raise ValueError(f"formato desconocido: {selected}")
        byte = int(value, base)
        if not 0 <= byte <= 0xFF:
            raise ValueError("el valor debe estar entre 0 y 255")
        return byte

    @staticmethod
    def _validate_bytes(values: Sequence[int]) -> bytes:
        result = bytearray()
        for value in values:
            if not 0 <= value <= 0xFF:
                raise ValueError(f"valor de byte fuera de rango: {value}")
            result.append(value)
        return bytes(result)

    def _load_image(self, origin: int, data: bytes) -> None:
        origin = self._validate_origin(origin)
        if origin + len(data) > ADDRESS_SPACE:
            raise ValueError("la imagen excede el espacio de memoria")
        self.memory.load_bytes(origin, data)
        if data:
            self._loaded_regions.append((origin, origin + len(data)))

    def _is_executable(self, address: int) -> bool:
        return address % 2 == 0 and any(
            start <= address < end for start, end in self._loaded_regions
        )

    @staticmethod
    def _validate_origin(origin: int) -> int:
        if not isinstance(origin, int) or not 0 <= origin < ADDRESS_SPACE or origin & 1:
            raise ValueError("el origen debe ser una dirección par entre 0 y 65534")
        return origin

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = mode.lower().replace("-", "").replace("_", "")
        aliases = {
            "singlecycle": "single",
            "monocycle": "mono",
            "multicycle": "multicycle",
        }
        return aliases.get(normalized, normalized)


def _parse_address(value: str) -> int:
    if value.lower().startswith("x"):
        return int(value[1:], 16)
    if value.lower().startswith("0x"):
        return int(value[2:], 16)
    return int(value, 10)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulador de la ISA-G27")
    parser.add_argument("program", help="programa ensamblado .hex, .bin, .lst o fuente .asm")
    parser.add_argument("--format", choices=("auto", "hex", "bin", "lst"), default="auto")
    parser.add_argument("--origin", type=_parse_address, help="dirección de carga")
    parser.add_argument(
        "--no-origin-header",
        action="store_true",
        help="no tomar los dos primeros bytes como dirección; carga por defecto en x3000",
    )
    parser.add_argument(
        "--mode",
        choices=("single", "multicycle", "pipeline"),
        default="single",
    )
    parser.add_argument(
        "--predictor",
        choices=("never", "always", "1bit", "2bit"),
        default="never",
    )
    parser.add_argument("--os", help="imagen del SO (.asm, .hex, .bin o .lst)")
    parser.add_argument("--no-os", action="store_true", help="no cargar el SO predeterminado")
    parser.add_argument("--input", default="", help="texto disponible para GETC")
    parser.add_argument("--max-instructions", type=int, default=100_000)
    parser.add_argument("-I", "--include", action="append", default=[])
    parser.add_argument("--stats", action="store_true", help="mostrar métricas en stderr")
    args = parser.parse_args(argv)
    try:
        simulator = Simulator(
            args.program,
            program_format=args.format,
            origin=args.origin,
            use_origin_header=not args.no_origin_header,
            mode=args.mode,
            predictor=args.predictor,
            load_os=not args.no_os,
            os_source=args.os,
            include_dirs=args.include,
            input_text=args.input,
            input_provider=None if args.input else lambda: sys.stdin.read(1),
            output_callback=lambda character: print(character, end="", flush=True),
        )
        result = simulator.run(args.max_instructions)
    except (AssemblyError, OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    if args.stats:
        stats = result.stats
        print(
            f"\ninstrucciones={stats.instructions} ciclos={stats.cycles} "
            f"lecturas={stats.memory_reads} escrituras={stats.memory_writes} "
            f"traps={stats.traps} interrupciones={stats.interrupts} "
            f"predicciones={stats.branch_predictions} "
            f"fallos_predicción={stats.branch_mispredictions} "
            f"fin={result.stop_reason}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
