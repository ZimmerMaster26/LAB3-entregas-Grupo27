import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from grupo27.simulador import Assembler, Simulator
from grupo27.simulador.machine import Machine, UnhandledTrapError
from grupo27.simulador.predictors import OneBitPredictor, TwoBitPredictor


class SimulatorTests(unittest.TestCase):
    def test_default_os_executes_getc_and_out_in_every_mode(self):
        source = Assembler().assemble(".ORIG x3000\nGETC\nOUT\n.END")
        for mode in ("single", "multicycle", "pipeline"):
            with self.subTest(mode=mode):
                simulator = Simulator(source, input_text="A", mode=mode)
                simulator.machine.set_register(1, 0xBEEF)
                result = simulator.run(max_instructions=100)

                self.assertEqual(result.output, "A")
                self.assertEqual(result.registers[0], ord("A"))
                self.assertEqual(result.registers[1], 0xBEEF)
                self.assertEqual(result.registers[6], Machine.USER_STACK_TOP)
                self.assertTrue(simulator.machine.user_mode)
                self.assertEqual(result.stats.traps, 2)
                self.assertEqual(result.stop_reason, "program_end")

    def test_puts_in_and_putsw_work_through_nested_traps(self):
        programs = (
            (
                """
                .ORIG x3000
                LEA R0 MESSAGE
                TRAP x22
                BR END
            MESSAGE .STRINGZ "Hi"
                .FILLB #0
            END .END
                """,
                "Hi",
                "",
                0x3006,
            ),
            (
                """
                .ORIG x3000
                LEA R0 MESSAGE
                TRAP x24
                BR END
            MESSAGE .FILL x0041
                .FILL x0042
                .FILL #0
            END .END
                """,
                "AB",
                "",
                0x3006,
            ),
            (
                ".ORIG x3000\nTRAP x23\nBR END\nEND .END",
                "Q",
                "Q",
                ord("Q"),
            ),
        )
        for mode in ("single", "multicycle", "pipeline"):
            for source, expected_output, input_text, expected_r0 in programs:
                with self.subTest(mode=mode, expected_output=expected_output):
                    simulator = Simulator(
                        Assembler().assemble(source),
                        mode=mode,
                        input_text=input_text,
                    )
                    result = simulator.run(max_instructions=1000)
                    self.assertEqual(result.output, expected_output)
                    self.assertEqual(result.registers[0], expected_r0)
                    self.assertEqual(result.registers[6], Machine.USER_STACK_TOP)
                    self.assertEqual(result.stop_reason, "program_end")
                    self.assertTrue(simulator.machine.user_mode)

    def test_halt_trap_stops_before_following_instruction_in_every_mode(self):
        source = Assembler().assemble(
            ".ORIG x3000\nTRAP x25\nADD R0 R0 #1\n.END"
        )
        for mode in ("single", "multicycle", "pipeline"):
            with self.subTest(mode=mode):
                result = Simulator(source, mode=mode).run()
                self.assertEqual(result.stop_reason, "halt")
                self.assertEqual(result.stats.instructions, 1)
                self.assertEqual(result.registers[0], 0)

    def test_branch_prediction_changes_pipeline_misprediction_count(self):
        source = """
            .ORIG x3000
            ADD R0 R0 #-1
            BRn TARGET
            ADD R1 R1 #1
        TARGET ADD R1 R1 #1
            .END
        """
        source = Assembler().assemble(source)
        never = Simulator(
            source, mode="pipeline", predictor="never", load_os=False
        ).run(max_instructions=20)
        always = Simulator(
            source, mode="pipeline", predictor="always", load_os=False
        ).run(max_instructions=20)

        self.assertEqual(never.registers[1], 1)
        self.assertEqual(always.registers[1], 1)
        self.assertEqual(never.stats.branch_predictions, 1)
        self.assertEqual(never.stats.branch_mispredictions, 1)
        self.assertEqual(always.stats.branch_mispredictions, 0)

    def test_execution_modes_report_different_cycle_counts(self):
        source = Assembler().assemble(".ORIG x3000\nADD R0 R0 #1\n.END")
        single = Simulator(source, mode="single", load_os=False).run()
        multi = Simulator(source, mode="multicycle", load_os=False).run()
        pipeline = Simulator(source, mode="pipeline", load_os=False).run()

        self.assertEqual(single.stats.instructions, 1)
        self.assertEqual(single.stats.cycles, 1)
        self.assertEqual(multi.stats.cycles, 4)
        self.assertEqual(pipeline.stats.cycles, 5)

    def test_assembled_file_formats_and_origin_override(self):
        for output_format in ("hex", "bin", "lst"):
            with self.subTest(output_format=output_format):
                text = Assembler().assemble(
                    ".ORIG x1234\n.FILL xABCD\n.END", output_format
                ).text
                simulator = Simulator(
                    text, load_os=False, program_format=output_format
                )
                override = Simulator(
                    text,
                    load_os=False,
                    origin=0x4000,
                    program_format=output_format,
                )

                self.assertEqual(simulator.program_origin, 0x1234)
                self.assertEqual(override.program_origin, 0x4000)
                self.assertEqual(simulator.memory.read_word(0x1234), 0xABCD)
                self.assertEqual(override.memory.read_word(0x4000), 0xABCD)

    def test_os_loads_from_hex_binary_and_numeric_images(self):
        os_path = Path(__file__).with_name("os.asm")
        user_program = Assembler().assemble(".ORIG x3000\nGETC\nOUT\n.END")
        with TemporaryDirectory() as directory:
            for output_format in ("hex", "bin", "lst"):
                image_path = Path(directory) / f"os.{output_format}"
                image_path.write_text(
                    Assembler().assemble(os_path, output_format).text,
                    encoding="ascii",
                )
                simulator = Simulator(
                    user_program,
                    os_source=image_path,
                    input_text="Z",
                )
                result = simulator.run()
                with self.subTest(output_format=output_format):
                    self.assertEqual(result.output, "Z")


    def test_one_bit_and_two_bit_predictors_update_state(self):
        one_bit = OneBitPredictor()
        two_bit = TwoBitPredictor()

        self.assertFalse(one_bit.predict(0x3000))
        one_bit.update(0x3000, True)
        self.assertTrue(one_bit.predict(0x3000))
        self.assertFalse(two_bit.predict(0x3000))
        two_bit.update(0x3000, True)
        self.assertTrue(two_bit.predict(0x3000))

    def test_interrupt_switches_to_supervisor_stack_and_rti_restores_user_state(self):
        machine = Machine()
        machine.memory.write_word(0x22 * 2, 0x0200)
        machine.memory.write_word(0x0200, 0x8000)
        original_sp = machine.registers[6]
        machine.request_interrupt(0x22, priority=3)

        self.assertIsNone(machine.step())
        self.assertFalse(machine.user_mode)
        self.assertEqual(machine.registers[6], Machine.SUPERVISOR_STACK_TOP - 4)
        machine.step()

        self.assertTrue(machine.user_mode)
        self.assertEqual(machine.registers[6], original_sp)
        self.assertEqual(machine.pc, 0x3000)
        self.assertEqual(machine.interrupts_taken, 1)

    def test_unhandled_trap_is_reported(self):
        machine = Machine()
        with self.assertRaises(UnhandledTrapError):
            machine.execute_word(0xF820, 0x3000)


if __name__ == "__main__":
    unittest.main()
