import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from grupo27.simulador.assembler import Assembler, AssemblyError


class AssemblerTests(unittest.TestCase):
    def test_instruction_encodings_and_word_offsets(self):
        source = """
            .ORIG x3000
            ADD R3, R0, R1
            ADD R5 R2 #6
            BRnzp TARGET
            LD R1, TARGET
        TARGET .FILL xCAFE
            .END
        """
        result = Assembler().assemble(source)

        self.assertEqual(
            result.data,
            bytes.fromhex("13 01 15 56 07 01 21 00 CA FE"),
        )
        self.assertEqual(result.symbols["TARGET"], 0x3008)

    def test_byte_data_aligns_following_words_and_keeps_adjacent_bytes(self):
        source = """
            .ORIG x3000
            .FILLB xAA
            .FILLB xBB
            ADD R0 R0 #0
            .FILLB xCC
            RET
            .END
        """
        result = Assembler().assemble(source)

        self.assertEqual(result.data, bytes.fromhex("AA BB 10 10 CC 00 B0 E0"))

    def test_external_module_is_appended_and_resolved(self):
        sources = {
            "main.asm": ".ORIG x3000\n.EXTERNAL library-FUNC\nJSR FUNC\n.END\n",
            "library.asm": ".ORIG\nFUNC ADD R0 R0 #1\nRET\n.END\n",
        }
        result = Assembler().assemble(sources)

        self.assertEqual(result.data, bytes.fromhex("44 00 10 11 B0 E0"))
        self.assertEqual(result.symbols["FUNC"], 0x3002)
        self.assertEqual(result.modules, ("main.asm", "library"))

    def test_external_filename_may_contain_hyphens(self):
        sources = {
            "main.asm": ".ORIG x3000\n.EXTERNAL my-lib-FUNC\nJSR FUNC\n.END",
            "my-lib.asm": ".ORIG\nFUNC RET\n.END",
        }
        result = Assembler().assemble(sources)

        self.assertEqual(result.data, bytes.fromhex("44 00 B0 E0"))

    def test_external_modules_can_be_supplied_as_ordered_texts(self):
        sources = [
            ".ORIG x3000\n.EXTERNAL library-FUNC\nJSR FUNC\n.END",
            ".ORIG\nFUNC RET\n.END",
        ]
        result = Assembler().assemble(sources)

        self.assertEqual(result.data, bytes.fromhex("44 00 B0 E0"))

    def test_instruction_table_encodes_all_supported_forms(self):
        source = """
            .ORIG x3000
            BRn TARGET
            BRc TARGET
            ADD R0 R0 R1
            ADC R0 R0 #1
            LD R0 TARGET
            LDB R0 TARGET
            ST R0 TARGET
            STB R0 TARGET
            JSR TARGET
            JSRR R1
            AND R0 R0 R1
            LDR R0 R1 #1
            LDRB R0 R1 #1
            STR R0 R1 #1
            STRB R0 R1 #1
            XOR R0 R0 R1
            NOT R0 R1
            LEA R0 TARGET
            RTI
            SEXT R0 R1 R2
            SEXT R0 R1 #8
            BEXT R0 R1
            LDI R0 TARGET
            LDIB R0 TARGET
            STI R0 TARGET
            STIB R0 TARGET
            JMP R1
            RET
            SHF R0 R1 #-1
            LSH R0 R1 #1
            RSH R0 R1 #1
            SHFO R0 R1 #-1
            LSHO R0 R1 #1
            RSHO R0 R1 #1
            SHR R0 R1 R2
            SHRO R0 R1 R2
            OR R0 R1 #1
            MUL R0 R1 R2
            MULH R0 R1 #1
            DIV R0 R1 R2
            MOD R0 R1 #1
            TRAP x20
            GETC
            OUT
        TARGET .FILL #0
            .END
        """
        result = Assembler().assemble(source)

        self.assertEqual(len(result.data), 45 * 2)
        words = [
            int.from_bytes(result.data[index:index + 2], "big")
            for index in range(0, len(result.data), 2)
        ]
        self.assertEqual(words[9], 0x4020)  # JSRR R1
        self.assertEqual(words[26:28], [0xB020, 0xB0E0])  # JMP R1, RET

    def test_output_formats_include_origin_bytes(self):
        source = ".ORIG x1234\n.FILL xABCD\n.END"
        self.assertEqual(
            Assembler().assemble(source, "hex").text,
            "12\n34\nAB\nCD\n",
        )
        self.assertEqual(
            Assembler().assemble(source, "bin").text,
            "00010010\n00110100\n10101011\n11001101\n",
        )
        self.assertEqual(Assembler().assemble(source, "lst").text, "18\n52\n171\n205\n")

    def test_rejects_out_of_range_immediate_with_source_line(self):
        with self.assertRaisesRegex(AssemblyError, r"<memory>:2:.*fuera de rango"):
            Assembler().assemble(".ORIG x3000\nADD R0 R0 #8\n.END")

    def test_stringz_and_comments(self):
        result = Assembler().assemble(
            '.ORIG x3000\n.STRINGZ "A; B" ; comment\n.END'
        )

        self.assertEqual(result.data, b"A; B\0")

    def test_blkw_and_blkb_reserve_zeroed_storage(self):
        source = """
            .ORIG x3000
            .BLKB #3
            .FILL #1
            .BLKW #2
            .END
        """
        result = Assembler().assemble(source)

        self.assertEqual(result.data, bytes.fromhex("00 00 00 00 00 01 00 00 00 00"))

    def test_end_ignores_following_source_and_origin_directive(self):
        source = ".ORIG x3000\n.FILL x1234\n.END\n.BAD_DIRECTIVE"
        result = Assembler().assemble(source)

        self.assertEqual(result.origin, 0x3000)
        self.assertEqual(result.data, bytes.fromhex("12 34"))

    def test_origin_argument_is_optional_and_end_is_required(self):
        result = Assembler().assemble(".ORIG\n.FILL x1234\n.END")
        self.assertEqual(result.origin, 0x3000)
        self.assertEqual(result.data, bytes.fromhex("12 34"))

        with self.assertRaisesRegex(AssemblyError, r"pseudo operación obligatoria \.ORIG"):
            Assembler().assemble(".END")
        with self.assertRaisesRegex(AssemblyError, r"pseudo operación obligatoria \.END"):
            Assembler().assemble(".ORIG x3000\n.FILL x1234")

    def test_origin_rejects_more_than_one_argument(self):
        with self.assertRaisesRegex(AssemblyError, r"\.ORIG acepta cero o un argumento"):
            Assembler().assemble(".ORIG x3000 x4000\n.END")

    def test_external_modules_also_require_origin_and_end(self):
        main = ".ORIG x3000\n.EXTERNAL library-FUNC\n.END"
        invalid_modules = (
            ("FUNC RET\n.END", r"pseudo operación obligatoria \.ORIG"),
            (".ORIG\nFUNC RET", r"pseudo operación obligatoria \.END"),
        )
        for module, error in invalid_modules:
            with self.subTest(module=module):
                with self.assertRaisesRegex(AssemblyError, error):
                    Assembler().assemble(
                        {"main.asm": main, "library.asm": module}
                    )

    def test_assemble_file_writes_default_hex_output(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "program.asm"
            source.write_text(".ORIG x3000\n.FILL xABCD\n.END", encoding="utf-8")

            result = Assembler().assemble_file(source)
            output = source.with_suffix(".hex")

            self.assertEqual(output.read_text(encoding="ascii"), "30\n00\nAB\nCD\n")
            self.assertEqual(result.data, bytes.fromhex("AB CD"))

    def test_external_module_can_be_loaded_from_subdirectory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.asm").write_text(
                ".ORIG x3000\n.EXTERNAL sub/library-FUNC\nJSR FUNC\n.END",
                encoding="utf-8",
            )
            module_dir = root / "sub"
            module_dir.mkdir()
            (module_dir / "library.asm").write_text(
                ".ORIG\nFUNC RET\n.END", encoding="utf-8"
            )

            result = Assembler().assemble(root / "main.asm")

        self.assertEqual(result.data, bytes.fromhex("44 00 B0 E0"))


if __name__ == "__main__":
    unittest.main()
