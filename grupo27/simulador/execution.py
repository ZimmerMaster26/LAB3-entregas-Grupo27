"""Execution modes and simulator metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .isa import stages_for_word
from .machine import Machine
from .predictors import BranchPredictor


@dataclass(frozen=True)
class SimulationStats:
    instructions: int
    cycles: int
    memory_reads: int
    memory_writes: int
    traps: int
    interrupts: int
    branch_predictions: int = 0
    branch_mispredictions: int = 0


@dataclass(frozen=True)
class SimulationResult:
    stats: SimulationStats
    output: str
    registers: tuple[int, ...]
    pc: int
    stop_reason: str


@dataclass
class _PipelineEntry:
    pc: int
    word: int
    predicted_taken: bool | None = None
    predicted_next: int | None = None


@dataclass(frozen=True)
class ExecutionContext:
    machine: Machine
    is_executable: Callable[[int], bool]
    max_instructions: int
    predictor: BranchPredictor


class ExecutionMode(Protocol):
    def run(self, context: ExecutionContext) -> tuple[int, int, int]:
        ...


class SingleCycleMode(ExecutionMode):
    def run(self, context: ExecutionContext):
        machine = context.machine
        cycles = 0
        start = machine.instructions_executed
        while (
            not machine.halted
            and machine.instructions_executed - start < context.max_instructions
        ):
            if not context.is_executable(machine.pc):
                return cycles, 0, 0
            instruction = machine.step()
            cycles += 1
            if machine.halted:
                return cycles, 0, 0
            if instruction is None and not context.is_executable(machine.pc):
                return cycles, 0, 0
        return cycles, 0, 0


class MultiCycleMode(ExecutionMode):
    def run(self, context: ExecutionContext):
        machine = context.machine
        cycles = 0
        start = machine.instructions_executed
        while (
            not machine.halted
            and machine.instructions_executed - start < context.max_instructions
        ):
            if not context.is_executable(machine.pc):
                return cycles, 0, 0
            instruction = machine.step()
            if instruction is None:
                cycles += 1
            else:
                cycles += _multi_cycle_cost(instruction)
            if machine.halted:
                return cycles, 0, 0
        return cycles, 0, 0


class PipelineMode(ExecutionMode):
    """Five-stage in-order pipeline with decode-time branch prediction."""

    STAGE_COUNT = 5

    def run(self, context: ExecutionContext):
        machine = context.machine
        is_executable = context.is_executable
        max_instructions = context.max_instructions
        predictor = context.predictor
        stages: list[_PipelineEntry | None] = [None] * self.STAGE_COUNT
        fetch_pc = machine.pc
        cycles = 0
        predictions = 0
        mispredictions = 0
        start = machine.instructions_executed

        while (
            not machine.halted
            and machine.instructions_executed - start < max_instructions
        ):
            if not any(stages) and not is_executable(fetch_pc):
                break
            cycles += 1

            if machine.service_pending_interrupt():
                stages = [None] * self.STAGE_COUNT
                fetch_pc = machine.pc
                continue

            for stage in range(self.STAGE_COUNT - 1, 0, -1):
                stages[stage] = stages[stage - 1]
            stages[0] = None

            decoded = stages[1]
            if decoded is not None and decoded.predicted_next is None:
                opcode = decoded.word >> 11
                decoded.predicted_next = (decoded.pc + 2) & 0xFFFF
                if opcode in (0, 1):
                    decoded.predicted_taken = predictor.predict(decoded.pc)
                    if decoded.predicted_taken:
                        displacement = Machine._signed(decoded.word & 0xFF, 8)
                        decoded.predicted_next = (
                            decoded.pc + 2 + 2 * displacement
                        ) & 0xFFFF
                    fetch_pc = decoded.predicted_next

            if is_executable(fetch_pc):
                instruction = machine.memory.read_word(fetch_pc)
                stages[0] = _PipelineEntry(fetch_pc, instruction)
                fetch_pc = (fetch_pc + 2) & 0xFFFF

            completed = stages[4]
            if completed is not None:
                actual_taken = machine.branch_condition(completed.word)
                machine.execute_word(completed.word, completed.pc)
                if machine.halted:
                    break
                if actual_taken is not None:
                    if completed.predicted_taken is None:
                        completed.predicted_taken = predictor.predict(completed.pc)
                    predictions += 1
                    if actual_taken != completed.predicted_taken:
                        mispredictions += 1
                    predictor.update(completed.pc, actual_taken)
                    redirect = actual_taken != completed.predicted_taken
                else:
                    redirect = machine.pc != ((completed.pc + 2) & 0xFFFF)
                if redirect:
                    stages = [None] * self.STAGE_COUNT
                    fetch_pc = machine.pc
                else:
                    stages[4] = None
                if machine.instructions_executed - start >= max_instructions:
                    break

        return cycles, predictions, mispredictions


def _multi_cycle_cost(word: int) -> int:
    return len(stages_for_word(word))


EXECUTION_MODES = {
    "single": SingleCycleMode,
    "mono": SingleCycleMode,
    "multicycle": MultiCycleMode,
    "multi": MultiCycleMode,
    "pipeline": PipelineMode,
}

