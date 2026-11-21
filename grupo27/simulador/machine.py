"""Architectural state and instruction semantics for ISA-G27."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Iterable


WORD_MASK = 0xFFFF
BYTE_MASK = 0xFF
ADDRESS_SPACE = 1 << 16
USER_MODE_BIT = 0x8000
PRIORITY_SHIFT = 8
NZP_MASK = 0x0007
OVERFLOW_MASK = 0x0020
CARRY_MASK = 0x0010
MMIO_KBSR = 0xFE00
MMIO_KBDR = 0xFE02
MMIO_DSR = 0xFE04
MMIO_DDR = 0xFE06


class MachineError(RuntimeError):
    """Raised when an instruction or architectural operation is invalid."""


class MemoryAccessError(MachineError):
    """Raised for invalid or misaligned memory accesses."""


class UnhandledTrapError(MachineError):
    """Raised when a trap/interrupt vector has no installed handler."""


@dataclass(frozen=True)
class InterruptRequest:
    vector: int
    priority: int


class Memory:
    """64 KiB of byte-addressable memory with LC-3-style console devices."""

    def __init__(
        self,
        input_text: str | bytes = "",
        input_provider: Callable[[], str | bytes | None] | None = None,
        output_callback: Callable[[str], None] | None = None,
    ):
        self.data = bytearray(ADDRESS_SPACE)
        self.memory_reads = 0
        self.memory_writes = 0
        self._input: Deque[int] = deque(
            input_text.encode("latin-1") if isinstance(input_text, str) else input_text
        )
        self.input_provider = input_provider
        self.output_callback = output_callback
        self.output: list[str] = []
        self._last_output = 0

    @property
    def output_text(self) -> str:
        return "".join(self.output)

    def load_bytes(self, address: int, values: bytes | bytearray | Iterable[int]) -> None:
        values = bytes(values)
        if not 0 <= address <= ADDRESS_SPACE or address + len(values) > ADDRESS_SPACE:
            raise MemoryAccessError("la imagen excede el espacio de memoria")
        self.data[address:address + len(values)] = values

    def read_byte(self, address: int) -> int:
        self._validate_address(address)
        self.memory_reads += 1
        if address in (MMIO_KBSR, MMIO_KBSR + 1):
            return (self._keyboard_status() >> (8 if address == MMIO_KBSR else 0)) & BYTE_MASK
        if address in (MMIO_KBDR, MMIO_KBDR + 1):
            value = self._keyboard_data(consume=address == MMIO_KBDR + 1)
            return (value >> (8 if address == MMIO_KBDR else 0)) & BYTE_MASK
        if address in (MMIO_DSR, MMIO_DSR + 1):
            return (0x8000 >> (8 if address == MMIO_DSR else 0)) & BYTE_MASK
        if address in (MMIO_DDR, MMIO_DDR + 1):
            return (self._last_output >> (8 if address == MMIO_DDR else 0)) & BYTE_MASK
        return self.data[address]

    def read_word(self, address: int) -> int:
        self._validate_word_address(address)
        self.memory_reads += 1
        if address == MMIO_KBSR:
            return self._keyboard_status()
        if address == MMIO_KBDR:
            return self._keyboard_data(consume=True)
        if address == MMIO_DSR:
            return 0x8000
        if address == MMIO_DDR:
            return self._last_output
        return (self.data[address] << 8) | self.data[address + 1]

    def write_byte(self, address: int, value: int) -> None:
        self._validate_address(address)
        self.memory_writes += 1
        if address == MMIO_DDR + 1:
            self._emit(value)
            return
        if address in range(MMIO_KBSR, MMIO_DDR + 2):
            return
        self.data[address] = value & BYTE_MASK

    def write_word(self, address: int, value: int) -> None:
        self._validate_word_address(address)
        self.memory_writes += 1
        value &= WORD_MASK
        if address == MMIO_DDR:
            self._emit(value)
            return
        if address in (MMIO_KBSR, MMIO_KBDR, MMIO_DSR, MMIO_DDR):
            return
        self.data[address] = value >> 8
        self.data[address + 1] = value & BYTE_MASK

    def _keyboard_status(self) -> int:
        if not self._input and self.input_provider:
            supplied = self.input_provider()
            if supplied:
                encoded = supplied.encode("latin-1") if isinstance(supplied, str) else supplied
                self._input.extend(encoded)
        return 0x8000 if self._input else 0

    def _keyboard_data(self, consume: bool) -> int:
        if not self._input:
            self._keyboard_status()
        if not self._input:
            return 0
        value = self._input[0]
        if consume:
            self._input.popleft()
        return value

    def _emit(self, value: int) -> None:
        self._last_output = value & BYTE_MASK
        character = chr(self._last_output)
        self.output.append(character)
        if self.output_callback:
            self.output_callback(character)

    @staticmethod
    def _validate_address(address: int) -> None:
        if not 0 <= address < ADDRESS_SPACE:
            raise MemoryAccessError(f"dirección fuera de memoria: {address}")

    @staticmethod
    def _validate_word_address(address: int) -> None:
        if not 0 <= address < ADDRESS_SPACE - 1:
            raise MemoryAccessError(f"dirección de palabra fuera de memoria: {address}")
        if address & 1:
            raise MemoryAccessError(f"acceso de palabra sin alinear: x{address:04X}")


class Machine:
    """State and execution semantics for the 16-bit ISA-G27 processor."""

    USER_STACK_TOP = 0xFDFE
    SUPERVISOR_STACK_TOP = 0x2FFE

    def __init__(
        self,
        input_text: str | bytes = "",
        input_provider: Callable[[], str | bytes | None] | None = None,
        output_callback: Callable[[str], None] | None = None,
    ):
        self.memory = Memory(input_text, input_provider, output_callback)
        self.registers = [0] * 8
        self.pc = 0x3000
        self.nzp = 0b010
        self.overflow = False
        self.carry = False
        self.user_mode = True
        self.priority = 0
        self.user_sp = self.USER_STACK_TOP
        self.supervisor_sp = self.SUPERVISOR_STACK_TOP
        self.instructions_executed = 0
        self.traps_taken = 0
        self.interrupts_taken = 0
        self.halted = False
        self._interrupts: list[InterruptRequest] = []

    @property
    def output(self) -> str:
        return self.memory.output_text

    @property
    def oc(self) -> int:
        return (int(self.overflow) << 1) | int(self.carry)

    @property
    def psr(self) -> int:
        value = self.nzp
        value |= int(self.overflow) << 5
        value |= int(self.carry) << 4
        value |= (self.priority & 0x7) << PRIORITY_SHIFT
        if self.user_mode:
            value |= USER_MODE_BIT
        return value

    def reset(self, pc: int = 0x3000, user_mode: bool = True) -> None:
        self.registers = [0] * 8
        self.pc = pc & WORD_MASK
        self.nzp = 0b010
        self.overflow = False
        self.carry = False
        self.user_mode = user_mode
        self.priority = 0
        self.user_sp = self.USER_STACK_TOP
        self.supervisor_sp = self.SUPERVISOR_STACK_TOP
        self.registers[6] = self.user_sp if user_mode else self.supervisor_sp
        self.instructions_executed = 0
        self.traps_taken = 0
        self.interrupts_taken = 0
        self.halted = False
        self._interrupts.clear()
        self.memory.memory_reads = 0
        self.memory.memory_writes = 0

    def set_register(self, index: int, value: int) -> None:
        self._check_register(index)
        value &= WORD_MASK
        self.registers[index] = value
        if index == 6:
            if self.user_mode:
                self.user_sp = value
            else:
                self.supervisor_sp = value

    def request_interrupt(self, vector: int, priority: int = 1) -> None:
        if not 0 <= vector <= BYTE_MASK:
            raise ValueError("el vector de interrupción debe caber en 8 bits")
        if not 0 <= priority <= 7:
            raise ValueError("la prioridad de interrupción debe estar entre 0 y 7")
        self._interrupts.append(InterruptRequest(vector, priority))

    def branch_condition(self, word: int) -> bool | None:
        opcode = (word & WORD_MASK) >> 11
        if opcode == 0:
            return bool(((word >> 8) & 0x7) & self.nzp)
        if opcode == 1:
            return self.carry if word & 0x0400 else self.overflow
        return None

    def service_pending_interrupt(self) -> bool:
        if not self._interrupts:
            return False
        eligible = [
            (index, request)
            for index, request in enumerate(self._interrupts)
            if request.priority > self.priority
        ]
        if not eligible:
            return False
        index, request = max(eligible, key=lambda item: item[1].priority)
        self._interrupts.pop(index)
        self._enter_privileged(request.vector, self.pc, request.priority)
        self.interrupts_taken += 1
        return True

    def step(self) -> int | None:
        """Execute one instruction, or accept one pending interrupt."""
        if self.service_pending_interrupt():
            return None
        instruction_pc = self.pc
        word = self.memory.read_word(instruction_pc)
        self.execute_word(word, instruction_pc)
        return word

    def execute_word(self, word: int, instruction_pc: int) -> None:
        """Execute a fetched instruction and leave PC at its actual successor."""
        word &= WORD_MASK
        next_pc = (instruction_pc + 2) & WORD_MASK
        self.pc = next_pc
        opcode = word >> 11

        if opcode == 0:
            conditions = (word >> 8) & 0x7
            if conditions & self.nzp:
                self.pc = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
        elif opcode == 1:
            carry_branch = bool(word & 0x0400)
            taken = self.carry if carry_branch else self.overflow
            if taken:
                self.pc = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
        elif opcode in (2, 3):
            self._execute_add(word, with_carry=opcode == 3)
        elif opcode == 4:
            address = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
            self._write_register((word >> 8) & 7, self.memory.read_word(address), update_cc=True)
        elif opcode == 5:
            address = (next_pc + self._signed(word & 0xFF, 8)) & WORD_MASK
            self._load_byte((word >> 8) & 7, self.memory.read_byte(address))
        elif opcode == 6:
            address = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
            self.memory.write_word(address, self.registers[(word >> 8) & 7])
        elif opcode == 7:
            address = (next_pc + self._signed(word & 0xFF, 8)) & WORD_MASK
            self.memory.write_byte(address, self.registers[(word >> 8) & 7])
        elif opcode == 8:
            self._execute_jsr(word, next_pc)
        elif opcode == 9:
            self._execute_logic(word, "and")
        elif opcode == 10:
            address = (self.registers[(word >> 5) & 7] + 2 * (word & 0x1F)) & WORD_MASK
            self._write_register((word >> 8) & 7, self.memory.read_word(address), update_cc=True)
        elif opcode == 11:
            address = (self.registers[(word >> 5) & 7] + (word & 0x1F)) & WORD_MASK
            self._load_byte((word >> 8) & 7, self.memory.read_byte(address))
        elif opcode == 12:
            address = (self.registers[(word >> 5) & 7] + 2 * (word & 0x1F)) & WORD_MASK
            self.memory.write_word(address, self.registers[(word >> 8) & 7])
        elif opcode == 13:
            address = (self.registers[(word >> 5) & 7] + (word & 0x1F)) & WORD_MASK
            self.memory.write_byte(address, self.registers[(word >> 8) & 7])
        elif opcode == 14:
            self._execute_xor_not(word)
        elif opcode == 15:
            address = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
            self._write_register((word >> 8) & 7, address, update_cc=True)
        elif opcode == 16:
            self._return_from_interrupt()
        elif opcode == 17:
            self._execute_sext(word)
        elif opcode == 18:
            pointer_address = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
            address = self.memory.read_word(pointer_address)
            self._write_register((word >> 8) & 7, self.memory.read_word(address), update_cc=True)
        elif opcode == 19:
            pointer_address = (next_pc + self._signed(word & 0xFF, 8)) & WORD_MASK
            address = self.memory.read_word(pointer_address)
            self._load_byte((word >> 8) & 7, self.memory.read_byte(address))
        elif opcode == 20:
            pointer_address = (next_pc + 2 * self._signed(word & 0xFF, 8)) & WORD_MASK
            address = self.memory.read_word(pointer_address)
            self.memory.write_word(address, self.registers[(word >> 8) & 7])
        elif opcode == 21:
            pointer_address = (next_pc + self._signed(word & 0xFF, 8)) & WORD_MASK
            address = self.memory.read_word(pointer_address)
            self.memory.write_byte(address, self.registers[(word >> 8) & 7])
        elif opcode == 22:
            self.pc = self.registers[(word >> 5) & 7]
        elif opcode in (23, 24):
            self._execute_shift(word, capture_overflow=opcode == 24)
        elif opcode == 25:
            self._execute_shift_register(word)
        elif opcode == 26:
            self._execute_logic(word, "or")
        elif opcode == 27:
            self._execute_multiply(word, high=False)
        elif opcode == 28:
            self._execute_multiply(word, high=True)
        elif opcode in (29, 30):
            self._execute_divide_modulo(word, remainder=opcode == 30)
        elif opcode == 31:
            self._execute_trap(word & BYTE_MASK)
        else:
            raise MachineError(f"opcode inválido: {opcode}")
        self.instructions_executed += 1

    def _execute_add(self, word: int, with_carry: bool) -> None:
        destination = (word >> 8) & 7
        left = self.registers[(word >> 5) & 7]
        if word & 0x10:
            right = self._signed(word & 0xF, 4)
        else:
            right = self.registers[word & 7]
        carry_in = int(with_carry and self.carry)
        right_word = right & WORD_MASK
        raw = left + right_word + carry_in
        signed_total = self._signed(left, 16) + self._signed(right & WORD_MASK, 16) + carry_in
        self._write_register(destination, raw, update_cc=True)
        self._set_oc(not -0x8000 <= signed_total <= 0x7FFF, raw > WORD_MASK)

    def _execute_logic(self, word: int, operation: str) -> None:
        destination = (word >> 8) & 7
        left = self.registers[(word >> 5) & 7]
        right = self._signed(word & 0xF, 4) if word & 0x10 else self.registers[word & 7]
        if operation == "and":
            result = left & right
        elif operation == "or":
            result = left | right
        else:
            raise MachineError(f"operación lógica no implementada: {operation}")
        self._write_register(destination, result, update_cc=True)
        self._set_oc(False, False)

    def _execute_xor_not(self, word: int) -> None:
        destination = (word >> 8) & 7
        left = self.registers[(word >> 5) & 7]
        if (word & 0x1F) == 0x1F:
            result = ~left
        else:
            right = self._signed(word & 0xF, 4) if word & 0x10 else self.registers[word & 7]
            result = left ^ right
        self._write_register(destination, result, update_cc=True)
        self._set_oc(False, False)

    def _execute_jsr(self, word: int, next_pc: int) -> None:
        self.registers[7] = next_pc
        if word & 0x0400:
            self.pc = (next_pc + 2 * self._signed(word & 0x3FF, 10)) & WORD_MASK
        else:
            self.pc = self.registers[(word >> 5) & 7]

    def _execute_sext(self, word: int) -> None:
        destination = (word >> 8) & 7
        source = (word >> 5) & 7
        bit_count = (word & 0xF) if word & 0x10 else self.registers[word & 7] & 0xF
        value = self.registers[source]
        if bit_count == 0:
            result = 0
        else:
            mask = (1 << bit_count) - 1
            result = value & mask
            if result & (1 << (bit_count - 1)):
                result |= WORD_MASK ^ mask
        self._write_register(destination, result, update_cc=True)
        self._set_oc(False, False)

    def _execute_shift(self, word: int, capture_overflow: bool) -> None:
        destination = (word >> 8) & 7
        source = self.registers[(word >> 5) & 7]
        amount = self._signed(word & 0x1F, 5)
        result, overflow, carry = self._shift_value(source, amount)
        self._write_register(destination, result, update_cc=True)
        if capture_overflow:
            self._set_oc(overflow, carry)

    def _execute_shift_register(self, word: int) -> None:
        destination = (word >> 8) & 7
        source = self.registers[(word >> 5) & 7]
        shift_register = self.registers[word & 7]
        amount = self._signed(shift_register & 0x1F, 5)
        result, overflow, carry = self._shift_value(source, amount)
        self._write_register(destination, result, update_cc=True)
        if word & 0x10:
            self._set_oc(overflow, carry)

    @staticmethod
    def _shift_value(value: int, amount: int) -> tuple[int, bool, bool]:
        value &= WORD_MASK
        if amount == 0:
            return value, False, False
        if amount > 0:
            if amount >= 16:
                carry = bool(value & 1) if amount == 16 else False
                result = 0
            else:
                carry = bool((value >> (16 - amount)) & 1)
                result = (value << amount) & WORD_MASK
            shifted_value = Machine._signed(value, 16) << amount
            overflow = not -0x8000 <= shifted_value <= 0x7FFF
            return result, overflow, carry
        count = -amount
        carry = bool((value >> (count - 1)) & 1) if count <= 16 else False
        result = value >> count if count < 16 else 0
        return result, False, carry

    def _execute_multiply(self, word: int, high: bool) -> None:
        destination = (word >> 8) & 7
        left = self._signed(self.registers[(word >> 5) & 7], 16)
        right = (
            self._signed(word & 0xF, 4)
            if word & 0x10
            else self._signed(self.registers[word & 7], 16)
        )
        product = left * right
        result = (product >> 16) if high else product
        self._write_register(destination, result, update_cc=True)
        overflow = not -0x8000 <= product <= 0x7FFF
        carry = bool(product & 0xFFFF0000)
        self._set_oc(overflow, carry)

    def _execute_divide_modulo(self, word: int, remainder: bool) -> None:
        destination = (word >> 8) & 7
        dividend = self._signed(self.registers[(word >> 5) & 7], 16)
        divisor = (
            self._signed(word & 0xF, 4)
            if word & 0x10
            else self._signed(self.registers[word & 7], 16)
        )
        if divisor == 0:
            self._write_register(destination, 0, update_cc=True)
            self._set_oc(True, False)
            return
        quotient = abs(dividend) // abs(divisor)
        if (dividend < 0) != (divisor < 0):
            quotient = -quotient
        result = dividend - quotient * divisor if remainder else quotient
        self._write_register(destination, result, update_cc=True)
        self._set_oc(False, False)

    def _execute_trap(self, vector: int) -> None:
        self.registers[7] = self.pc
        if vector == 0x25:
            self.halted = True
            self.traps_taken += 1
            return
        self._enter_privileged(vector, self.pc, self.priority)
        self.traps_taken += 1

    def _enter_privileged(self, vector: int, return_pc: int, priority: int) -> None:
        old_psr = self.psr
        was_user = self.user_mode
        if was_user:
            self.user_sp = self.registers[6]
            self.registers[6] = self.supervisor_sp
        self._push(old_psr)
        self._push(return_pc)
        self.supervisor_sp = self.registers[6]
        self.user_mode = False
        self.priority = max(self.priority, priority)
        vector_address = vector * 2
        handler = self.memory.read_word(vector_address)
        if handler == 0:
            raise UnhandledTrapError(f"no hay handler instalado para el vector x{vector:02X}")
        self.pc = handler

    def _return_from_interrupt(self) -> None:
        if self.user_mode:
            raise MachineError("RTI solo puede ejecutarse en modo privilegiado")
        stack_pointer = self.registers[6]
        return_pc = self.memory.read_word(stack_pointer)
        saved_psr = self.memory.read_word(stack_pointer + 2)
        stack_pointer = (stack_pointer + 4) & WORD_MASK
        returning_to_user = bool(saved_psr & USER_MODE_BIT)
        self.supervisor_sp = stack_pointer
        self._restore_psr(saved_psr)
        if returning_to_user:
            self.registers[6] = self.user_sp
        else:
            self.registers[6] = stack_pointer
        self.pc = return_pc

    def _push(self, value: int) -> None:
        stack_pointer = (self.registers[6] - 2) & WORD_MASK
        self.memory.write_word(stack_pointer, value)
        self.registers[6] = stack_pointer

    def _restore_psr(self, value: int) -> None:
        self.user_mode = bool(value & USER_MODE_BIT)
        self.priority = (value >> PRIORITY_SHIFT) & 0x7
        self.nzp = value & NZP_MASK
        self.overflow = bool(value & OVERFLOW_MASK)
        self.carry = bool(value & CARRY_MASK)

    def _load_byte(self, register: int, value: int) -> None:
        result = (self.registers[register] & 0xFF00) | (value & BYTE_MASK)
        self._write_register(register, result, update_cc=True)

    def _write_register(self, index: int, value: int, update_cc: bool = False) -> None:
        self._check_register(index)
        self.registers[index] = value & WORD_MASK
        if index == 6:
            if self.user_mode:
                self.user_sp = self.registers[index]
            else:
                self.supervisor_sp = self.registers[index]
        if update_cc:
            self._set_nzp(self.registers[index])

    def _set_nzp(self, value: int) -> None:
        value &= WORD_MASK
        if value == 0:
            self.nzp = 0b010
        elif value & 0x8000:
            self.nzp = 0b100
        else:
            self.nzp = 0b001

    def _set_oc(self, overflow: bool, carry: bool) -> None:
        self.overflow = bool(overflow)
        self.carry = bool(carry)

    @staticmethod
    def _signed(value: int, width: int) -> int:
        sign_bit = 1 << (width - 1)
        value &= (1 << width) - 1
        return value - (1 << width) if value & sign_bit else value

    @staticmethod
    def _check_register(index: int) -> None:
        if not 0 <= index < 8:
            raise MachineError(f"registro inválido: R{index}")
