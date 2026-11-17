`timescale 1ns/1ps
// A source sends A1, A2, A3 once after each synchronous reset.
module handshake (
    input wire clk, reset, ready,
    output reg valid,
    output reg [7:0] data,
    output reg [1:0] sent
);
    always @(posedge clk) begin
        if (reset) begin
            valid <= 0;
            data <= 8'hA1;
            sent <= 0;
        end else if (!valid && sent == 0) begin
            valid <= 1;
        end else if (valid && ready) begin
            sent <= sent + 2'd1;
            if (sent == 2) valid <= 0;
            else data <= data + 8'd1;
        end
        // With valid && !ready, valid and data both retain their values.
    end
endmodule
