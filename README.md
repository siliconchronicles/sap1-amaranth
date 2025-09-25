# FPGA SAP-1

## Setup

- Run `uv sync`. That will ensure installing correct libraries
- After the first uv run, set environment variable `YOSYS=$(pwd)/.venv/bin/yowasp-yosys`, to use the provided version of yosys (rather than building one).

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

