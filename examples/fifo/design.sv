`timescale 1ns/1ps
module fifo (
    input wire clk, reset,
    input wire wr_en, rd_en,
    input wire [7:0] wr_data,
    output reg [7:0] rd_data,
    output wire full, empty,
    output reg [2:0] count
);
    reg [7:0] mem [0:3];
    reg [1:0] wr_ptr, rd_ptr;
    // Admission uses pre-edge flags: full rejects writes even with a read;
    // empty rejects reads even with a write (no fall-through).
    wire push = wr_en && !full;
    wire pop = rd_en && !empty;
    assign full = (count == 3'd4);
    assign empty = (count == 3'd0);
    always @(posedge clk) begin
        if (reset) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            count <= 0;
            rd_data <= 0;
        end else begin
            if (push) begin
                mem[wr_ptr] <= wr_data;
                wr_ptr <= wr_ptr + 2'd1;
            end
            if (pop) begin
                rd_data <= mem[rd_ptr];
                rd_ptr <= rd_ptr + 2'd1;
            end
            case ({push, pop})
                2'b10: count <= count + 3'd1;
                2'b01: count <= count - 3'd1;
                default: count <= count;
            endcase
        end
    end
endmodule
