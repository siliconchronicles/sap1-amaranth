from typing import Iterator, Protocol
from amaranth import Module, Signal
from amaranth.hdl._ast import Statement
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class BusProducer(Protocol):
    data_out: Signal


class BusConsumer(Protocol):
    data_in: Signal
    write_enable: Signal


class DataControlBus(wiring.Component):

    active_input: Signal
    active_outputs: Signal

    def __init__(
        self,
        width: int,
        in_ports: dict[str, BusProducer],
        out_ports: dict[str, BusConsumer],
    ) -> None:
        self.width = width
        self.in_ports = list(in_ports.values())
        self.out_ports = list(out_ports.values())
        self._in_idx = {name: idx for idx, name in enumerate(in_ports)}
        self._out_idx = {name: idx for idx, name in enumerate(out_ports)}
        n_inputs = len(in_ports)
        n_outputs = len(out_ports)

        self.bus_value = Signal(self.width)

        port_signatures = (
            {f"in_{name}": In(port.data_out.shape()) for name, port in in_ports.items()}
            | {
                f"out_{name}": Out(port.data_in.shape())
                for name, port in out_ports.items()
            }
            | {
                f"out_{name}_we": Out(port.data_in.shape())
                for name, port in out_ports.items()
            }
        )

        super().__init__(
            dict(
                active_outputs=In(n_outputs),
                active_input=In(range(n_inputs)),
                **port_signatures,
            )
        )

    def elaborate(self, platform) -> Module:
        m = Module()

        with m.Switch(self.active_input):
            for idx, in_port in enumerate(self.in_ports):
                with m.Case(idx):
                    m.d.comb += self.bus_value.eq(in_port.data_out)

        for idx, out_port in enumerate(self.out_ports):
            with m.If(self.active_outputs[idx]):
                m.d.comb += [
                    out_port.data_in.eq(self.bus_value),
                    out_port.write_enable.eq(1),
                ]
            with m.Else():
                m.d.comb += out_port.write_enable.eq(0)

        return m

    def select_input(self, input: str) -> Statement:
        return self.active_input.eq(self._in_idx[input])

    def select_outputs(self, outputs: str = "") -> Iterator[Statement]:
        yield self.active_outputs.eq(0)
        for name in outputs.split():
            yield self.active_outputs[self._out_idx[name]].eq(1)
