from pathlib import Path

import pytest

from backend.app.analyzer import analyze, edges, value_at
from backend.app.models import AnalysisRequest, Event, Signal, Source
from backend.app.parser import parse_vcd
from backend.tests.test_parser import HEADER


@pytest.fixture
def trace():
    return parse_vcd(
        HEADER + b"#5\n0!\nbx #\n#10\n1!\nb1 #\nb10 #\n#15\n0!\n#20\n1!\n#25", "test.vcd"
    )


def test_value_boundary_and_same_timestamp(trace):
    assert value_at(trace.signals[0], 0) is None
    assert value_at(trace.signals[0], 5) == "0"
    assert value_at(trace.signals[1], 10) == "0010"
    assert value_at(trace.signals[1], 25) == "0010"


def test_edges(trace):
    assert edges(trace.signals[0], "rising") == [10, 20]
    assert edges(trace.signals[0], "falling") == [15]
    signal = Signal(
        id="x",
        name="x",
        scope="",
        width=1,
        kind="wire",
        events=[Event(time=i, value=v) for i, v in enumerate("x1z01")],
    )
    assert edges(signal, "rising") == [4]


def test_window_and_nearest(trace):
    result = analyze(trace, AnalysisRequest(time=10, signals=["s0", "s1"], window=0, clock="s0"))
    signal = result["signals"][0]
    assert signal["previous"].time == 5
    assert signal["next"].time == 15
    assert [event.time for event in signal["events"]] == [10]
    assert len(result["signals"][1]["events"]) == 2
    assert result["clock"] == {
        "name": "tb.clk",
        "edge": "rising",
        "previous": None,
        "next": 20,
        "at_time": True,
    }


def test_reset_configuration_and_no_data(trace):
    result = analyze(trace, AnalysisRequest(time=0, signals=["s0"], reset="s0", reset_active="0"))
    assert result["reset"]["active"] is None
    assert result["reset"]["mode"] == "unknown"
    assert result["signals"][0]["value"] is None
    assert result["signals"][0]["previous"] is None
    result = analyze(
        trace,
        AnalysisRequest(
            time=5, signals=["s0"], reset="s0", reset_active="0", reset_mode="synchronous"
        ),
    )
    assert result["reset"]["active"] is True
    assert result["reset"]["mode"] == "synchronous"


@pytest.mark.parametrize(
    "kwargs",
    [{"time": 26}, {"signals": ["bad"]}, {"clock": "s1"}, {"reset": "s1"}, {"clock": "bad"}],
)
def test_invalid_analysis(trace, kwargs):
    with pytest.raises(ValueError):
        analyze(trace, AnalysisRequest(**({"time": 0, "signals": ["s0"]} | kwargs)))


def test_rtl_heuristic(trace):
    trace.sources = [
        Source(
            name="design.sv",
            content="module demo;\nreg [3:0] data;\n// data is not causal proof\nendmodule",
        )
    ]
    result = analyze(trace, AnalysisRequest(time=10, signals=["s1"]))
    assert [match["line"] for match in result["related_code"]] == [2, 3]
    assert all(match["match"] == "name-only" for match in result["related_code"])


@pytest.mark.parametrize(
    "newline", ["\r", "\n", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", " ", " "]
)
def test_rtl_line_endings(trace, newline):
    trace.sources = [
        Source(
            name="design.sv",
            content=newline.join(
                [
                    "module demo;",
                    "",
                    "wire data;",
                    "// data",
                    "",
                ]
            ),
        )
    ]
    matches = analyze(trace, AnalysisRequest(time=10, signals=["s1"]))["related_code"]
    assert [(match["line"], match["text"]) for match in matches] == [
        (3, "wire data;"),
        (4, "// data"),
    ]


def test_rtl_ascii_name_boundaries(trace):
    trace.sources = [
        Source(
            name="design.sv",
            content="\n".join(
                [
                    "data",
                    "metadata data_next data$next",
                    "édata中",
                    "$data _data 1data",
                    "dataé",
                ]
            ),
        )
    ]
    matches = analyze(trace, AnalysisRequest(time=10, signals=["s1"]))["related_code"]
    assert [match["line"] for match in matches] == [1, 3, 5]


def test_rtl_escaped_identifier(trace):
    trace.signals[1].name = r"tb.\data+$[3:0]"
    trace.sources = [
        Source(
            name="design.sv",
            content="\r\n".join(
                [
                    r"wire \data+$ ;",
                    r"assign \data+$ = 0;",
                    "wire data;",
                    r"wire \data+$extra ;",
                    r"wire prefix\data+$ ;",
                ]
            ),
        )
    ]
    matches = analyze(trace, AnalysisRequest(time=10, signals=["s1"]))["related_code"]
    assert [match["line"] for match in matches] == [1, 2]
    assert all(match["signal"] == r"tb.\data+$[3:0]" for match in matches)


def test_rtl_match_order_and_limit(trace):
    trace.sources = [
        Source(name="first.sv", content="clk data\n" * 12),
        Source(name="second.sv", content="clk data\r" * 12),
    ]
    matches = analyze(trace, AnalysisRequest(time=10, signals=["s1", "s0"]))["related_code"]
    assert [(match["signal"], match["file"], match["line"]) for match in matches] == [
        *[(trace.signals[1].name, "first.sv", i) for i in range(1, 13)],
        *[(trace.signals[1].name, "second.sv", i) for i in range(1, 13)],
        *[(trace.signals[0].name, "first.sv", i) for i in range(1, 9)],
    ]


def test_window_truncation(trace):
    trace.end = 500
    trace.signals[0].events = [Event(time=i, value=str(i % 2)) for i in range(500)]
    result = analyze(trace, AnalysisRequest(time=250, signals=["s0"], window=500))
    assert result["signals"][0]["truncated"]
    assert len(result["signals"][0]["events"]) == 128
    assert result["window"] == {"start": 0, "end": 500}


def test_counter_real_hold():
    root = Path(__file__).resolve().parents[2]
    trace = parse_vcd((root / "examples/counter/trace.vcd").read_bytes(), "counter")
    signals = {signal.name: signal for signal in trace.signals}
    assert value_at(signals["tb.count[3:0]"], 120000) == "1010"
    assert value_at(signals["tb.enable"], 120000) == "0"
    assert value_at(signals["tb.count[3:0]"], 145000) == "1010"
    assert 125000 in edges(signals["tb.clk"], "rising")
