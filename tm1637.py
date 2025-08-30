import sys
from typing import Literal
from amaranth import Array, Const, Module, Signal, Mux, EnableInserter, Cat

from amaranth.lib import wiring


class SlowEnable(wiring.Component):

    pulse: wiring.Out(1)

    def __init__(self, delay: int):
        super().__init__()
        self.delay = delay

    def elaborate(self, platform):
        m = Module()
        count = Signal(range(self.delay), init=0)
        m.d.sync += count.eq(Mux(count < self.delay - 1, count + 1, 0))
        m.d.comb += self.pulse.eq(count == 0)
        return m


class DecimalDecoder(wiring.Component):

    value: wiring.In(13)  # We can represent up to 2 ** 13 in 4 decimal digits
    segments: wiring.Out(32)

    def elaborate(self, platform):
        m = Module()

        WIDTH = 16  # 4 digits
        assert WIDTH % 4 == 0, "WIDTH must be multiple of 4"
        assert 10 ** (WIDTH // 4) >= 2**len(self.value), "WIDTH too small"

        bcd = Signal(WIDTH, init=0xdead)

        # Double dabble algorithm, combinational
        def dd_step(value):
            return Mux(value > 4, (value + 3), value)[:4]

        result_initial = result = Signal(3)
        m.d.comb += result_initial.eq(self.value[-3:])
        for step in range(len(self.value)-4, -1, -1):
            current_bit = self.value[step]
            # Adjust digits that could be > 5
            for nibble_idx in range((len(result)+1) // 4):
                nibble_old = result.word_select(nibble_idx, 4)
                result = Cat(result[:4*nibble_idx], dd_step(nibble_old), result[4*nibble_idx + 4:])
            result_next = Signal(len(result)+1, name=f"result_{step}")
            # Shift in the current bit
            m.d.comb += result_next.eq(Cat(current_bit, result))
            result = result_next

        assert len(result) <= WIDTH+1 # We can end with an extra 0 bit at the end. ignore
        m.d.comb += bcd.eq(result)

        previous_digit_visible = 0
        for digit_pos in reversed(range(4)):
            m.submodules[f"digit_{digit_pos}"] = digits = Seven_Segment_Decoder()
            bcd_digit = bcd.word_select(digit_pos, 4)
            m.d.comb += (
                digits.bcd.eq(bcd_digit),
                digits.dot.eq(0),
                digits.visible.eq((digit_pos == 0) | (bcd_digit != 0) | previous_digit_visible),
            )
            m.d.sync += self.segments.word_select(3 - digit_pos, 8).eq(digits.segments)
            previous_digit_visible = digits.visible
        return m


class Seven_Segment_Decoder(wiring.Component):

    bcd: wiring.In(4)
    dot: wiring.In(1)
    visible: wiring.In(1, init=1)

    segments: wiring.Out(8)  # 7 segments + dot

    BCD_TO_SEGMENTS = Array([
        0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07,
        0x7F, 0x6F, 0x77, 0x7C, 0x39, 0x5E, 0x79, 0x71
    ])

    def elaborate(self, platform):
        m = Module()
        with m.If(self.visible):
            m.d.comb += self.segments.eq(self.BCD_TO_SEGMENTS[self.bcd])
        with m.Else():
            m.d.comb += self.segments.eq(0)
        with m.If(self.dot):
            m.d.comb += self.segments[7].eq(1)
   
        return m


class TM1637(wiring.Component):

    SEGMENT_COUNT = 4
    display_data: wiring.In(SEGMENT_COUNT * 8)  # 4 7-segments.

    scl: wiring.Out(1)
    dio: wiring.Out(1)

    def __init__(self):
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        initialized = Signal()

        START = [self.dio.eq(0), self.scl.eq(0)]
        STOP = [self.dio.eq(0), self.scl.eq(1), self.dio.eq(1)]
        PULSE = [self.scl.eq(1), self.scl.eq(0)]

        def send_bit(bit: Literal[0, 1]):
            return [self.dio.eq(bit)] + PULSE

        def send_byte(byte: int):
            result = []
            for i in range(8):
                result += send_bit((byte >> i) & 1)
            result += PULSE  # ACK bit
            return result

        def send_data_command(read: bool = False, fixed_address: bool = False):
            return START + send_byte(0x40 | (read << 1) | (fixed_address << 2)) + STOP

        def send_control_command(active: bool = True, brightness: int = 2):
            return START + send_byte(0x80 | (active << 3) | (brightness & 0x07)) + STOP

        def send_display(data: list[int], address: int = 0):
            result = START + send_byte(0xC0 | (address & 0x0F))
            for d in data:
                result += send_byte(d)
            result += STOP
            return result

        def send_fixed(actions, *, end_action=(), end_step=None, reset=True):
            # uses non-local m, current_step
            if len(actions) >= 2 ** len(current_step):
                raise ValueError("Too many actions for step counter")
            with m.Switch(current_step):
                for i, action in enumerate(actions):
                    with m.Case(i):
                        m.d.sync += action
                        m.d.sync += current_step.eq(current_step + 1)
                with m.Default():
                    if reset:
                        m.d.sync += current_step.eq(0)
                    m.d.sync += end_action
                    if end_step:
                        # Should be used only within a FSM
                        m.next = end_step

        sequence = (
            send_data_command() + send_display([0, 0, 0, 0]) + send_control_command()
        )

        duration = len(sequence)
        current_step = Signal(range(duration + 1))  # sequential execution counter
        data_out = Signal.like(
            self.display_data
        )  # shift register for data transmission
        count = Signal(range(len(data_out) + 1))  # counter of data left
        with m.If(~initialized):
            send_fixed(sequence, end_action=initialized.eq(1))
        with m.Else():
            # Active mode. Just loop sending the display data.
            prefix = START + send_byte(0xC0)
            with m.FSM(name="update_display_fsm") as update_display_fsm:
                with m.State("SEND_PREFIX"):
                    send_fixed(prefix, end_step="SEND_DATA")
                    m.d.sync += [
                        data_out.eq(self.display_data),
                        count.eq(len(data_out)),
                    ]
                with m.State("SEND_DATA"):
                    # This is done to stop the data sending FSM
                    done = Signal()
                    with m.If(done):
                        m.next = "STOP"

                    # This IS the data sending FSM
                    with m.FSM(name="send_data_fsm"):
                        with m.State("bit out"):
                            send_fixed(
                                [self.dio.eq(data_out[0])] + PULSE,
                                end_action=(
                                    data_out.eq(data_out >> 1),
                                    count.eq(count - 1),
                                ),
                                end_step="bit end",
                            )
                        with m.State("bit end"):
                            with m.If(count == 0):
                                # Send ACK + stop. stop send data FSM
                                send_fixed(
                                    PULSE + STOP,
                                    end_action=done.eq(1),
                                    end_step="bit out",
                                )
                            with m.Elif(count[:3] == 0):  # Byte finished. Send ack
                                send_fixed(PULSE, end_step="bit out")
                            with m.Else():
                                m.next = "bit out"
                with m.State("STOP"):
                    m.d.sync += done.eq(0)  # reset done signal

                    send_fixed(STOP, end_step="SEND_PREFIX")

        return m


if __name__ == "__main__":
    from tang_nano_20k import TangNano20kPlatform
    from amaranth.build import Resource, Pins, Attrs

    class TM1637_Nano(TangNano20kPlatform):
        resources = TangNano20kPlatform.resources + [
            Resource(
                "tmclk",
                0,
                Pins("55", dir="o"),
                Attrs(
                    IO_TYPE="LVCMOS33",
                ),
            ),
            Resource("tmdio", 0, Pins("49", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        ]

    platform = TM1637_Nano()

    from amaranth.cli import main

    DELAY = 27  # 1 microsecond; assuming the nano 27MHz clock.

    m = Module()
    m.submodules.speed = slow = SlowEnable(DELAY)
    m.submodules.display = display = EnableInserter(slow.pulse)(TM1637())

    m.d.comb += platform.request("tmclk").o.eq(m.submodules.display.scl)
    m.d.comb += platform.request("tmdio").o.eq(m.submodules.display.dio)

    m.submodules.data_speed = ds = SlowEnable(27_000_000 // 4)
    counter = Signal(16)
    with m.If(ds.pulse):
        m.d.sync += counter.eq(counter + 1)

    m.submodules.decimal = decimal = DecimalDecoder()
    m.d.comb += [
        decimal.value.eq(counter),
        display.display_data.eq(decimal.segments),
    ]

    if "synth" in sys.argv:
        platform.build(m, do_program=True)
    else:
        main(m, ports=[display.dio, display.scl])
