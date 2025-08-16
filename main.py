from amaranth.cli import main

from beneater import BenEater

FIBONACCI = [
    0x51,  # LDI 1
    0x4E,  # STA e
    0x50,  # LDI 0
    0xE0,  # OUT
    0x2E,  # ADD e
    0x4F,  # STA f
    0x1E,  # LDA e
    0x4D,  # STA d
    0x1F,  # LDA f
    0x4E,  # STA e
    0x1D,  # LDA d
    0x70,  # JC 0
    0x63,  # JMP 3
]

if __name__ == "__main__":
    be8 = BenEater(FIBONACCI)
    main(be8, ports=[])
