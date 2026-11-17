`timescale 1ns/1ps
module tb;
reg clk=0, reset=1;
reg [3:0] sync_count, async_count;
reg [3:0] bus=4'bxxxx;
reg marker=0;
always #5 clk=~clk;
always @(posedge clk) if(reset) sync_count<=0; else sync_count<=sync_count+4'd1;
always @(posedge clk or posedge reset) if(reset) async_count<=0; else async_count<=async_count+4'd1;
initial begin
  $dumpfile("trace.vcd"); $dumpvars(0,tb);
  #12 reset=0;
  #160; // 172 ns, 16 increments -> 0
  #10; // 182 ns, both counters = 1
  reset=1; // async clears off-edge, sync stays 1 until 185
  #1 bus=4'bzzzz;
  #1 bus=4'bx1z0;
  #2 reset=0;
  #1 marker=1; $dumpall; #0 marker=0; $dumpall; // same tick dump records
  #1 bus=4'b0011;
  #12 $finish;
end
endmodule
