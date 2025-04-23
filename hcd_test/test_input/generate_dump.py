SRAM_ROW_WIDTH = 32


def generate_hex_dump(
    data_lst, hex_file_name, bits_per_data=SRAM_ROW_WIDTH
):
    """
    generate hexdump from number list (1d)
    """
    # turn number list into hex list of the form ['00', '01', ...]
    hex_list = []
    hex_width = bits_per_data // 4
    for i in range(len(data_lst)):
        hex_val = ("{:0" + str(hex_width) + "x}").format(data_lst[i])
        for j in reversed(range(bits_per_data // 8)):
            hex_list.append(hex_val[j * 2 : j * 2 + 2])

    # save to a hex file
    with open(hex_file_name, "w") as hex_file:
        for i, hex_val in enumerate(hex_list, start=1):
            hex_file.write(f"{hex_val} ")
            if i % 16 == 0:
                hex_file.write("\n")
    print(f"Hex dump saved to {hex_file_name}")
