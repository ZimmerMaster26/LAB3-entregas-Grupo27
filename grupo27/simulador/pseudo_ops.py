"""Pseudo-operation metadata for the assembler."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PseudoOpSpec:
    size: str
    aligned: bool = False


PSEUDO_OPS = {
    ".ORIG": PseudoOpSpec("origin"),
    ".END": PseudoOpSpec("end"),
    ".EXTERNAL": PseudoOpSpec("external"),
    ".FILL": PseudoOpSpec("word", aligned=True),
    ".FILLB": PseudoOpSpec("byte"),
    ".BLKW": PseudoOpSpec("words", aligned=True),
    ".BLKB": PseudoOpSpec("bytes"),
    ".STRINGZ": PseudoOpSpec("string"),
}

