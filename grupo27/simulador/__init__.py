"""ISA-G27 assembler package."""

__all__ = ["Assembler", "AssemblyError", "AssemblyResult", "Machine", "Memory", "Simulator"]


def __getattr__(name: str):
    if name in __all__:
        if name in {"Assembler", "AssemblyError", "AssemblyResult"}:
            from . import assembler as module
        elif name == "Simulator":
            from . import simulator as module
        else:
            from . import machine as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
