`timescale 1ns/1ps
module tb;
    reg clk = 0;
    reg reset = 1;
    reg enable = 0;
    wire [3:0] count;
    reg [3:0] expected = 0;
    integer checks = 0;
    counter dut (.clk(clk), .reset(reset), .enable(enable), .count(count));
    always #5 clk = ~clk;

    // Check after nonblocking assignments on every rising edge.
    always @(posedge clk) begin
        if (reset) expected = 0;
        else if (enable) expected = expected + 4'd1;
        #1;
        assert (count === expected) else $fatal(1, "counter mismatch at %0t", $time);
        checks = checks + 1;
    end

    initial begin
        $dumpfile("trace.vcd");
        $dumpvars(0, tb);
        #20; reset = 0; enable = 1;
        #100; enable = 0; // 120 ns: ten increments, then hold.
        assert (count === 4'd10) else $fatal(1, "120ns count must be 10");
        #30;
        assert (count === 4'd10) else $fatal(1, "disabled count changed");
        enable = 1;
        #56; // 206 ns: overflow occurred at 205 ns.
        assert (count === 4'd0) else $fatal(1, "4-bit wrap failed");
        #6; reset = 1; // 212 ns, not a clock edge.
        #1;
        assert (count === 4'd0) else $fatal(1, "unexpected pre-edge count");
        #7; reset = 0;
        #6;
        assert (count === 4'd1) else $fatal(1, "count after reset failed");
        #6; reset = 1; // 232 ns: count=1 must not reset asynchronously.
        #1;
        assert (count === 4'd1) else $fatal(1, "reset must be synchronous");
        #4;
        assert (count === 4'd0) else $fatal(1, "reset priority failed");
        assert (checks == 24) else $fatal(1, "missing clock checks");
        $display("PASS counter: 24 edges, hold at 120-150ns, wrap at 205ns, sync reset at 235ns");
        $finish;
    end
    initial begin #1000; $fatal(1, "counter timeout"); end
endmodule
