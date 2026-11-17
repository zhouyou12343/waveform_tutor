`timescale 1ns/1ps
module tb;
    reg clk = 0, reset = 1, wr_en = 0, rd_en = 0;
    reg [7:0] wr_data = 0;
    wire [7:0] rd_data;
    wire full, empty;
    wire [2:0] count;
    integer checks = 0;
    fifo dut (.*);
    always #5 clk = ~clk;
    task step(input reg w, input reg r, input reg [7:0] data,
              input reg [2:0] want_count, input reg [7:0] want_data);
        begin
            @(negedge clk);
            wr_en = w; rd_en = r; wr_data = data;
            @(posedge clk); #1;
            assert (count === want_count) else $fatal(1, "FIFO count at %0t", $time);
            assert (rd_data === want_data) else $fatal(1, "FIFO order/hold at %0t", $time);
            assert (full === (want_count == 4)) else $fatal(1, "FIFO full at %0t", $time);
            assert (empty === (want_count == 0)) else $fatal(1, "FIFO empty at %0t", $time);
            checks = checks + 1;
        end
    endtask
    initial begin
        $dumpfile("trace.vcd"); $dumpvars(0, tb);
        @(posedge clk); #1;
        assert (count === 0 && empty === 1 && full === 0 && rd_data === 0)
            else $fatal(1, "FIFO reset failed");
        @(negedge clk); reset = 0;
        step(1, 0, 8'h11, 1, 0); // 25 ns
        step(1, 0, 8'h22, 2, 0);
        step(1, 0, 8'h33, 3, 0);
        step(1, 0, 8'h44, 4, 0); // 55 ns full
        step(1, 0, 8'hEE, 4, 0); // 65 ns rejected
        step(0, 1, 0, 3, 8'h11); // 75 ns
        step(1, 1, 8'h55, 3, 8'h22); // 85 ns simultaneous, pointer wrap
        step(0, 1, 0, 2, 8'h33);
        step(0, 1, 0, 1, 8'h44);
        step(0, 1, 0, 0, 8'h55); // 115 ns empty
        step(0, 1, 0, 0, 8'h55); // 125 ns underflow rejected
        step(1, 1, 8'h66, 1, 8'h55); // 135 ns empty: write only
        step(0, 1, 0, 0, 8'h66);
        step(1, 0, 8'h77, 1, 8'h66);
        step(1, 0, 8'h88, 2, 8'h66);
        step(1, 0, 8'h99, 3, 8'h66);
        step(1, 0, 8'hAA, 4, 8'h66);
        step(1, 1, 8'hFF, 3, 8'h77); // 195 ns full: read only
        step(0, 1, 0, 2, 8'h88);
        step(0, 1, 0, 1, 8'h99);
        step(0, 1, 0, 0, 8'hAA);
        assert (checks == 21) else $fatal(1, "missing FIFO checks");
        $display("PASS fifo: 21 transactions, full/empty guards, simultaneous access and ordering");
        $finish;
    end
    initial begin #1000; $fatal(1, "FIFO timeout"); end
endmodule
