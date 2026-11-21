import unittest

from grupo27.simulador import Assembler, Simulator


class MachineTests(unittest.TestCase):
    def test_signed_immediate_add_updates_carry_and_overflow(self):
        subtract_one = Assembler().assemble(
            ".ORIG x3000\nADD R0 R0 #-1\n.END"
        )
        simulator = Simulator(subtract_one, load_os=False)
        simulator.machine.set_register(0, 1)
        result = simulator.run()

        self.assertEqual(result.registers[0], 0)
        self.assertTrue(simulator.machine.carry)
        self.assertFalse(simulator.machine.overflow)
        self.assertEqual(simulator.machine.nzp, 0b010)

        add_one = Assembler().assemble(".ORIG x3000\nADD R0 R0 #1\n.END")
        simulator = Simulator(add_one, load_os=False)
        simulator.machine.set_register(0, 0x7FFF)
        result = simulator.run()

        self.assertEqual(result.registers[0], 0x8000)
        self.assertTrue(simulator.machine.overflow)
        self.assertFalse(simulator.machine.carry)
        self.assertEqual(simulator.machine.nzp, 0b100)

    def test_byte_load_preserves_register_high_byte(self):
        source = """
            .ORIG x3000
            LDB R0 DATA
            BR END
        DATA .FILLB xCD
            .FILLB #0
        END .END
        """
        simulator = Simulator(Assembler().assemble(source), load_os=False)
        simulator.machine.set_register(0, 0xAB00)
        result = simulator.run()

        self.assertEqual(result.registers[0], 0xABCD)

    def test_memory_metrics_include_fetch_and_data_access(self):
        source = """
            .ORIG x3000
            LD R0 DATA
            ST R0 DEST
            BR END
        DATA .FILL x1234
        DEST .FILL #0
        END .END
        """
        result = Simulator(
            Assembler().assemble(source), load_os=False
        ).run()

        self.assertEqual(result.stats.instructions, 3)
        self.assertEqual(result.stats.memory_reads, 4)
        self.assertEqual(result.stats.memory_writes, 1)

    def test_indirect_byte_instructions_read_a_word_sized_pointer(self):
        load_source = """
            .ORIG x3000
            LDIB R0 PTR
            BR END
        PTR .FILL DATA
        DATA .FILLB xAB
            .FILLB #0
        END .END
        """
        simulator = Simulator(Assembler().assemble(load_source), load_os=False)
        simulator.machine.set_register(0, 0xCD00)
        result = simulator.run()
        self.assertEqual(result.registers[0], 0xCDAB)

        store_source = """
            .ORIG x3000
            STIB R0 PTR
            BR END
        PTR .FILL DATA
        DATA .FILLB #0
            .FILLB #0
        END .END
        """
        simulator = Simulator(Assembler().assemble(store_source), load_os=False)
        simulator.machine.set_register(0, 0xABCD)
        simulator.run()
        self.assertEqual(simulator.memory.read_byte(0x3006), 0xCD)

    def test_shift_overflow_and_right_shift_count_follow_isa_encoding(self):
        shift_left = Assembler().assemble(
            ".ORIG x3000\nSHFO R0 R1 #1\n.END"
        )
        simulator = Simulator(shift_left, load_os=False)
        simulator.machine.set_register(1, 0x4000)
        result = simulator.run()

        self.assertEqual(result.registers[0], 0x8000)
        self.assertTrue(simulator.machine.overflow)
        self.assertFalse(simulator.machine.carry)

        shift_right = Assembler().assemble(".ORIG x3000\nRSH R0 R1 #9\n.END")
        simulator = Simulator(shift_right, load_os=False)
        simulator.machine.set_register(1, 0xFF80)
        result = simulator.run()
        self.assertEqual(result.registers[0], 0x01FF)

    def test_division_overflow_is_reserved_for_divide_by_zero(self):
        divide = Assembler().assemble(".ORIG x3000\nDIV R0 R1 #-1\n.END")
        simulator = Simulator(divide, load_os=False)
        simulator.machine.set_register(1, 0x8000)
        result = simulator.run()

        self.assertEqual(result.registers[0], 0x8000)
        self.assertFalse(simulator.machine.overflow)

        divide_by_zero = Assembler().assemble(
            ".ORIG x3000\nDIV R0 R1 R2\n.END"
        )
        simulator = Simulator(divide_by_zero, load_os=False)
        simulator.machine.set_register(1, 123)
        result = simulator.run()
        self.assertEqual(result.registers[0], 0)
        self.assertTrue(simulator.machine.overflow)


if __name__ == "__main__":
    unittest.main()
