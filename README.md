# FPGA based SAP-1 in Amaranth HDL

I test this project on a Sipeed Tang Nano 20K board. I have successfully made it work on a Nano 9K in the past.

## Setup

- Run `uv sync`. That will ensure the installation of the correct libraries
- After the first `uv` run, set environment variable `YOSYS=$(pwd)/.venv/bin/yowasp-yosys`, to use the provided version of `yosys` (The alternative is building one yourself).

## Development

- Run commands using `uv run ...` to use the uv setup environment
- **Simulate**: `uv run -m sap1.core.sap1 simulate -v simulate.vcd -c 800`
  - The `800` indicate number of clock cycles
- **Build**: `uv run -m sap1.core.sap1 generate output.v`
  - You can also use `--no-src` to make shorter Verilog
- **Synthesize**: `uv run -m sap1.synth`. This builds files in `build/`
  - Constraints are generated in `top.cst`
  - Intermediate representation (RTLIL) in `top.il`
  - Flashable file in `top.fs`
- **Upload**: `openFPGALoader -b tangnano20k build/top.fs`
  - This will also **upload** the synthesized result to the device RAM
  - Use `-f` to persist the config to flash.

## Other resources and links

- This project was [presented at PyConJP2025](https://2025.pycon.jp/en/timetable/talk/8EAGDB)
- Other projects/demos at my [📽️ YouTube channel](https://www.youtube.com/@dmoisset)
- Original design from: *Albert Paul Malvino, “Digital Computer Electronics”. Copyright © McGraw-Hill, Inc. 1977.*
- [Amaranth docs](https://amaranth-lang.org/docs/amaranth/)
