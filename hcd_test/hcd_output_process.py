import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt


def hcd_output_process(
    original_img_path, hcd_output_lst, output_img_path="test_outputs"
):
    """
    parse the output data and store the corner detection as an image overlay on the original image

    Args:
        original_img_path: path to the original image
        hcd_output_lst: list of hcd output data from the utils.load_out_data function call
        output_img_path: path to save the processed image
    """

    image_width = 40
    image_height = 40
    image = Image.open(original_img_path)
    image = image.convert("L")
    img = np.array(image, dtype=np.uint8)

    assert (
        len(hcd_output_lst) == image_width * image_height
    ), f"hcd_output_lst should have length {image_width * image_height}, but got {len(hcd_output_lst)}"

    # parse in hcd_output.txt
    res = np.zeros((image_height, image_width), dtype=np.uint8)
    for i, output_point in enumerate(hcd_output_lst):
        val = int(output_point)
        assert val >= 0 and val <= 1, f"output value {val} is not in range [0, 1]"
        res[i // image_width][i % image_width] = val

    # remove the peripheral invalid pixels
    invalid_width = 3
    res_truncated = np.zeros((image_height, image_width), dtype=np.uint8)
    res_truncated[
        invalid_width : image_height - invalid_width,
        invalid_width : image_width - invalid_width,
    ] = res[
        invalid_width : image_height - invalid_width,
        invalid_width : image_width - invalid_width,
    ]

    # plot the image
    pr, pc = np.where(res_truncated == 1)
    plt.figure(figsize=(10, 10))
    plt.imshow(img, cmap="gray", vmin=0, vmax=255)  # plot the original image
    plt.plot(pc, pr, "r*", markersize=10)  # plot the corner points
    image_loc = os.path.join(output_img_path, "result.png")
    plt.savefig(image_loc)
    print(f"\033[92mHCD processed image saved to {image_loc}\033[0m")
