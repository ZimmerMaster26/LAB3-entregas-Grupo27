"""Instruction encodings for ISA-G27."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InstructionSpec:
    opcode: int
    form: str

    @property
    def stages(self) -> tuple[str, ...]:
        if self.form in {
            "pc_word", "pc_byte", "base_word", "base_byte",
        }:
            return ("FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITEBACK")
        if self.form in {
            "pc_word_store", "pc_byte_store", "base_word_store", "base_byte_store",
        }:
            return ("FETCH", "DECODE", "EXECUTE", "MEMORY")
        if self.form in {"trap", "trap_alias", "no_operands"}:
            return ("FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITEBACK")
        if self.form in {"branch_nzp", "branch_oc", "jsr", "base_jump", "base_jump_link", "ret"}:
            return ("FETCH", "DECODE", "EXECUTE")
        return ("FETCH", "DECODE", "EXECUTE", "WRITEBACK")


# Forms describe operand layout; encoding is centralized in assembler.py.
INSTRUCTIONS = {}
for _mnemonic in ("BR", "BRNZP", "BRNZ", "BRNP", "BRZP", "BRN", "BRZ", "BRP"):
    INSTRUCTIONS[_mnemonic] = InstructionSpec(0, "branch_nzp")
INSTRUCTIONS.update({
    "BRO": InstructionSpec(1, "branch_oc"),
    "BRC": InstructionSpec(1, "branch_oc"),
    "ADD": InstructionSpec(2, "alu_imm4"),
    "ADC": InstructionSpec(3, "alu_imm4"),
    "LD": InstructionSpec(4, "pc_word"),
    "LDB": InstructionSpec(5, "pc_byte"),
    "ST": InstructionSpec(6, "pc_word_store"),
    "STB": InstructionSpec(7, "pc_byte_store"),
    "JSR": InstructionSpec(8, "jsr"),
    "JSRR": InstructionSpec(8, "base_jump_link"),
    "AND": InstructionSpec(9, "alu_imm4"),
    "LDR": InstructionSpec(10, "base_word"),
    "LDRB": InstructionSpec(11, "base_byte"),
    "STR": InstructionSpec(12, "base_word_store"),
    "STRB": InstructionSpec(13, "base_byte_store"),
    "XOR": InstructionSpec(14, "alu_imm4"),
    "NOT": InstructionSpec(14, "not"),
    "LEA": InstructionSpec(15, "lea"),
    "RTI": InstructionSpec(16, "no_operands"),
    "SEXT": InstructionSpec(17, "sext"),
    "BEXT": InstructionSpec(17, "bext"),
    "LDI": InstructionSpec(18, "pc_word"),
    "LDIB": InstructionSpec(19, "pc_byte"),
    "STI": InstructionSpec(20, "pc_word_store"),
    "STIB": InstructionSpec(21, "pc_byte_store"),
    "JMP": InstructionSpec(22, "base_jump"),
    "RET": InstructionSpec(22, "ret"),
    "SHF": InstructionSpec(23, "shift5"),
    "LSH": InstructionSpec(23, "shift_left"),
    "RSH": InstructionSpec(23, "shift_right"),
    "SHFO": InstructionSpec(24, "shift5"),
    "LSHO": InstructionSpec(24, "shift_left"),
    "RSHO": InstructionSpec(24, "shift_right"),
    "SHR": InstructionSpec(25, "shift_register"),
    "SHRO": InstructionSpec(25, "shift_register_overflow"),
    "OR": InstructionSpec(26, "alu_imm4"),
    "MUL": InstructionSpec(27, "alu_imm4"),
    "MULH": InstructionSpec(28, "alu_imm4"),
    "DIV": InstructionSpec(29, "alu_imm4"),
    "MOD": InstructionSpec(30, "alu_imm4"),
    "TRAP": InstructionSpec(31, "trap"),
    "GETC": InstructionSpec(31, "trap_alias"),
    "OUT": InstructionSpec(31, "trap_alias"),
})


def register_index(token: str) -> int:
    """Parse an ISA register name and reject anything outside R0..R7."""
    upper = token.upper()
    if len(upper) != 2 or upper[0] != "R" or upper[1] not in "01234567":
        raise ValueError(f"registro inválido: {token}")
    return int(upper[1])


def stages_for_word(word: int) -> tuple[str, ...]:
    """Return the architectural stages associated with an encoded instruction."""
    opcode = (word >> 11) & 0x1F
    if opcode == 0:
        return INSTRUCTIONS["BR"].stages
    if opcode == 1:
        return INSTRUCTIONS["BRC" if word & 0x0400 else "BRO"].stages
    if opcode == 8:
        return INSTRUCTIONS["JSR" if word & 0x0400 else "JSRR"].stages
    if opcode == 14 and (word & 0x1F) == 0x1F:
        return INSTRUCTIONS["NOT"].stages
    if opcode == 22:
        return INSTRUCTIONS["JMP"].stages
    if opcode == 25 and word & 0x10:
        return INSTRUCTIONS["SHRO"].stages
    for spec in INSTRUCTIONS.values():
        if spec.opcode == opcode:
            return spec.stages
    raise ValueError(f"opcode inválido: {opcode}")
