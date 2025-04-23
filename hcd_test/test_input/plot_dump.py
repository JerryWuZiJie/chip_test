import numpy as np
from PIL import Image

IMG_HEIGHT = 40
IMG_WIDTH = 40


def dump_to_image(file_path):
    hex_data = []
    with open(file_path, "r") as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("@"):
                continue
            else:
                hex_data.extend(line.split())

    data_lst = []
    data_per_word = 32 // 8
    data = 0
    for i in range(len(hex_data)):
        data = data | int(hex_data[i], 16) << (8 * (i % data_per_word))
        if (i + 1) % data_per_word == 0:
            data_lst.append(data)
            data = 0
    # left over
    if len(hex_data) % data_per_word != 0:
        data_lst.append(data)

    # change to np array and plot
    np_array = np.array(data_lst, dtype=np.uint8).reshape(IMG_HEIGHT, IMG_WIDTH)
    image = Image.fromarray(np_array)
    image.save("restore_image.png")


if __name__ == "__main__":
    dump_to_image("image_dump.v")
