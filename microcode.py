from dataclasses import dataclass
import enum
from typing import Literal, TypeAlias


@dataclass
class uInstr:
    # What is moved over the data bus
    dst: str = ""
    src: str = "a"
    # ALU settings
    subtract: bool = False
    update_flags: bool = False
    # Other flags
    count: bool = False  # increase PC
    halt: bool = False


class Mnemonic(enum.Enum):
    NOP = 0x0
    LDA = 0x1
    ADD = 0x2
    SUB = 0x3
    STA = 0x4
    LDI = 0x5
    JMP = 0x6
    JZ = 0x7
    JC = 0x8
    OUT = 0xE
    HLT = 0xF


OPCODES: dict[Mnemonic, list[uInstr]] = {
    Mnemonic.NOP: [],
    Mnemonic.LDA: [
        uInstr(dst="memory_address", src="instruction"),
        uInstr(dst="a", src="memory"),
    ],
    Mnemonic.ADD: [
        uInstr(dst="memory_address", src="instruction"),
        uInstr(dst="b", src="memory"),
        uInstr(dst="a", src="alu", update_flags=True),
    ],
    Mnemonic.SUB: [
        uInstr(dst="memory_address", src="instruction"),
        uInstr(dst="b", src="memory"),
        uInstr(dst="a", src="alu", subtract=True, update_flags=True),
    ],
    Mnemonic.STA: [
        uInstr(dst="memory_address", src="instruction"),
        uInstr(dst="memory", src="a"),
    ],
    Mnemonic.LDI: [
        uInstr(dst="a", src="instruction"),
    ],
    Mnemonic.JMP: [
        uInstr(dst="pc", src="instruction"),
    ],
    Mnemonic.OUT: [
        uInstr(dst="output", src="a"),
    ],
    Mnemonic.HLT: [uInstr(halt=True)],
}
