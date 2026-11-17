#!/usr/bin/env python3
"""Simulate only the three trusted repository examples; never accept uploads."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ("counter", "fifo", "handshake")


def main() -> None:
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        raise SystemExit("需要安装 Icarus Verilog（iverilog 和 vvp）")

    for name in EXAMPLES:
        source = ROOT / "examples" / name
        lesson = json.loads((source / "lesson.json").read_text(encoding="utf-8"))
        if (
            set(lesson) != {"title", "description", "questions", "expected"}
            or not all(isinstance(lesson[k], str) for k in ("title", "description"))
            or not all(
                isinstance(lesson[k], list)
                and lesson[k]
                and all(isinstance(item, str) for item in lesson[k])
                for k in ("questions", "expected")
            )
            or len(lesson["questions"]) != len(lesson["expected"])
        ):
            raise ValueError(f"Invalid lesson schema: {source / 'lesson.json'}")

        # The temporary cwd isolates build products, not arbitrary hostile code.
        # No user paths, uploads, shell execution, or source discovery are allowed.
        with tempfile.TemporaryDirectory(prefix=f"waveform-{name}-") as directory:
            work = Path(directory)
            for filename in ("design.sv", "tb.sv"):
                shutil.copyfile(source / filename, work / filename)
            commands = (
                [iverilog, "-g2012", "-Wall", "-s", "tb", "-o", "sim.vvp", "design.sv", "tb.sv"],
                [vvp, "sim.vvp"],
            )
            for command in commands:
                print(f"[{name}] cwd={work} $ {' '.join(command)}", flush=True)
                subprocess.run(command, cwd=work, check=True, timeout=30)
            trace = work / "trace.vcd"
            if not trace.is_file() or trace.stat().st_size == 0:
                raise RuntimeError(f"Simulation produced no trace: {name}")
            shutil.copyfile(trace, source / "trace.vcd")
            print(f"[{name}] generated {source / 'trace.vcd'}", flush=True)
    print("全部三个示例的断言及 lesson.json 格式检查通过。")


if __name__ == "__main__":
    main()
