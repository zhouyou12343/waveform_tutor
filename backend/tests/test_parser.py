from pathlib import Path

import pytest

from backend.app import parser
from backend.app.parser import ParseError, parse_vcd

HEADER = b"$timescale 1 ns $end\n$scope module tb $end\n$var wire 1 ! clk $end\n$var reg 4 # data [3:0] $end\n$upscope $end\n$enddefinitions $end\n"


def test_digital_values_and_same_timestamp():
    trace = parse_vcd(
        HEADER + b"$dumpvars\n0!\nbx #\n$end\n#10\n1!\nb10xz #\nbz #\n#20\n0!\nb10 #\n", "test.vcd"
    )
    assert trace.timescale == "1 ns"
    assert trace.tick_fs == 10**6
    assert trace.end == 20
    assert trace.signals[1].name == "tb.data[3:0]"
    assert [(event.time, event.value) for event in trace.signals[1].events] == [
        (0, "xxxx"),
        (10, "10xz"),
        (10, "zzzz"),
        (20, "0010"),
    ]


@pytest.mark.parametrize(
    ("unit", "scale"),
    [("s", 10**15), ("ms", 10**12), ("us", 10**9), ("ns", 10**6), ("ps", 1000), ("fs", 1)],
)
def test_timescales(unit, scale):
    trace = parse_vcd(HEADER.replace(b"1 ns", f"10 {unit}".encode()) + b"#0\n0!", "test.vcd")
    assert trace.tick_fs == 10 * scale


def test_aliases_nested_scope():
    data = HEADER.replace(
        b"$upscope $end",
        b"$scope module dut $end\n$var wire 1 ! clock_alias $end\n$upscope $end\n$upscope $end",
    )
    trace = parse_vcd(data + b"0!\n#5\n1!", "test.vcd")
    assert trace.signals[2].name == "tb.dut.clock_alias"
    assert trace.signals[0].events == trace.signals[2].events


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"hello",
        HEADER.replace(b"1 ns", b"0 ns"),
        HEADER.replace(b"1 ns", b"2 ns"),
        b"$timescale 1 ns $end\n$enddefinitions $end",
        HEADER + b"#10\n#9",
        HEADER + b"1?",
        HEADER + b"b10101 #",
        HEADER + b"$dumpvars\n0!",
        HEADER + b"$comment unfinished",
        HEADER + b"r1.2 !",
        HEADER.replace(b"wire", b"mystery"),
        HEADER.replace(b"wire", b"real"),
        HEADER.replace(b"$enddefinitions $end", b""),
        HEADER + b"#9007199254740992",
        HEADER + b"$attrbegin blah $end",
        HEADER + b"b10",
        HEADER + b"#",
        HEADER + b"1#",
    ],
)
def test_invalid_and_unsupported(data):
    with pytest.raises(ParseError):
        parse_vcd(data, "invalid.vcd")


def named_vcd(scopes, refs, id_code="!"):
    return (
        "$timescale 1 ns $end\n"
        + "".join(f"$scope module {scope} $end\n" for scope in scopes)
        + "".join(f"$var wire 1 {id_code} {ref} $end\n" for ref in refs)
        + "$upscope $end\n" * len(scopes)
        + "$enddefinitions $end\n"
    ).encode()


@pytest.mark.parametrize("part", ["scope", "ref", "id_code"])
@pytest.mark.parametrize("length", [256, 257])
def test_identifier_limits(part, length):
    data = named_vcd(
        ["s" * length if part == "scope" else "tb"],
        ["r" * length if part == "ref" else "q"],
        "!" * length if part == "id_code" else "!",
    )
    if length == 256:
        assert parse_vcd(data, "boundary.vcd").signals
    else:
        with pytest.raises(ParseError, match="256"):
            parse_vcd(data, "boundary.vcd")


@pytest.mark.parametrize("length", [253, 254])
def test_full_name_limit(length):
    data = named_vcd(["s" * 256] * 3, ["r" * length])
    if length == 253:
        assert len(parse_vcd(data, "boundary.vcd").signals[0].name) == 1024
    else:
        with pytest.raises(ParseError, match="1024"):
            parse_vcd(data, "boundary.vcd")


def test_aggregate_name_scope_budget():
    # Each signal contributes 258 + 254 = 512 characters, including aliases.
    refs = [f"{i:03}" for i in range(257)]
    data = named_vcd(["s" * 254], refs[:256])
    trace = parse_vcd(data, "boundary.vcd")
    assert sum(len(s.name) + len(s.scope) for s in trace.signals) == 128 * 1024
    with pytest.raises(ParseError, match="128 Ki"):
        parse_vcd(named_vcd(["s" * 254], refs), "over.vcd")


def test_long_scope_amplification_rejected():
    with pytest.raises(ParseError, match="256"):
        parse_vcd(named_vcd(["s" * 4096], [f"q{i}" for i in range(16)]), "large.vcd")


@pytest.mark.parametrize("snapshot", [b"", b"x!\n"])
def test_dumpoff_rejected_even_without_snapshot(snapshot):
    with pytest.raises(ParseError, match=r"\$dumpoff.*停录区间"):
        parse_vcd(
            HEADER + b"#0\n1!\n#10\n$dumpoff\n" + snapshot + b"$end\n#15\n#20\n$dumpon\n1!\n$end",
            "off.vcd",
        )


@pytest.mark.parametrize("directive", [b"dumpvars", b"dumpall", b"dumpon"])
def test_other_dump_directives_preserved(directive):
    trace = parse_vcd(HEADER + b"$" + directive + b"\n1!\n$end\n#15", "on.vcd")
    assert trace.signals[0].events[0].value == "1"
    assert trace.end == 15


def test_resource_limits(monkeypatch):
    monkeypatch.setattr(parser, "MAX_FILE_BYTES", 8)
    with pytest.raises(ParseError, match="8 MiB"):
        parse_vcd(HEADER, "large.vcd")
    monkeypatch.setattr(parser, "MAX_FILE_BYTES", 10000)
    monkeypatch.setattr(parser, "MAX_EVENTS", 1)
    with pytest.raises(ParseError, match="事件数"):
        parse_vcd(HEADER + b"0!\n1!", "events.vcd")
    monkeypatch.setattr(parser, "MAX_SIGNALS", 1)
    with pytest.raises(ParseError, match="信号数"):
        parse_vcd(HEADER, "signals.vcd")


@pytest.mark.parametrize("name", ["counter", "fifo", "handshake"])
def test_real_examples(name):
    root = Path(__file__).resolve().parents[2]
    trace = parse_vcd((root / "examples" / name / "trace.vcd").read_bytes(), name)
    assert trace.timescale == "1 ps"
    assert trace.end > 100000
    assert all(
        len(event.value) == signal.width for signal in trace.signals for event in signal.events
    )
