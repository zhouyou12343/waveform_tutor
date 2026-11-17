`timescale 1ns/1ps
module tb;
    reg clk = 0, reset = 1, ready = 0;
    wire valid;
    wire [7:0] data;
    wire [1:0] sent;
    integer received = 0;
    integer stalls = 0;
    reg stalled = 0;
    reg [7:0] held_data = 0;
    handshake dut (.*);
    always #5 clk = ~clk;
    // Sample pre-edge values: those are the values actually transferred.
    always @(posedge clk) begin
        if (reset) begin
            received = 0; stalled = 0;
        end else begin
            if (stalled)
                assert (valid === 1 && data === held_data)
                    else $fatal(1, "source changed while waiting at %0t", $time);
            if (valid && ready) begin
                assert (received < 3 && data === (8'hA1 + received))
                    else $fatal(1, "transfer data/order at %0t", $time);
                case (received)
                    0: assert ($time == 55) else $fatal(1, "first transfer time");
                    1: assert ($time == 95) else $fatal(1, "second transfer time");
                    2: assert ($time == 105) else $fatal(1, "third transfer time");
                endcase
                received = received + 1;
            end
            stalled = valid && !ready;
            held_data = data;
            if (stalled) stalls = stalls + 1;
        end
        #1;
        assert (sent === received[1:0]) else $fatal(1, "sent advanced without handshake");
        if (stalled)
            assert (valid === 1 && data === held_data) else $fatal(1, "post-edge stall violation");
    end
    initial begin
        $dumpfile("trace.vcd"); $dumpvars(0, tb);
        #20; reset = 0;
        #30; ready = 1; // transfer A1 at 55 ns
        #10; ready = 0; // A2 must wait through 65,75,85 ns
        #30; ready = 1; // transfer A2 at 95 ns, A3 at 105 ns
        #37;
        assert (received == 3 && sent === 3 && valid === 0)
            else $fatal(1, "handshake completion failed");
        assert (stalls == 5) else $fatal(1, "missing backpressure checks");
        $display("PASS handshake: A1@55ns A2@95ns A3@105ns; 5 stalled edges checked");
        $finish;
    end
    initial begin #1000; $fatal(1, "handshake timeout"); end
endmodule
