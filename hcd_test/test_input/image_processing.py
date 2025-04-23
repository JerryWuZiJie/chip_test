"""
generate hex dump from ndarrays
"""

import argparse

import numpy as np
from PIL import Image

import generate_dump

DATA_WIDTH = 32
IMG_HEIGHT = 40
IMG_WIDTH = 40
PIXEL_WIDTH = 8
ROW_BUFFER_SIZE = 5  # 5 rows of pixels
INPUT_WIDTH = ROW_BUFFER_SIZE * PIXEL_WIDTH

DEFUALT_IMAGE_FILE = "image.png"

parser = argparse.ArgumentParser(description="Generate hex dump from image")
parser.add_argument(
    "--image_file", "-i", help="image file name to generate hex dump from"
)
args = parser.parse_args()

IMAGE_FILE = args.image_file


if __name__ == "__main__":
    if not IMAGE_FILE:
        print("No image file specified, using generated data...")

        # generate image
        img = np.zeros((IMG_HEIGHT, IMG_WIDTH), dtype=np.uint8)

        img[:] = 100
        img[10:30, 10:20] = 255
        img[20:25, 20:30] = 255
        img[23:30, 23:27] = 255
        img[23:27, 0:40] = 255

        Image.fromarray(img).save(DEFUALT_IMAGE_FILE)
        print(f"Generated image saved to {DEFUALT_IMAGE_FILE}")
        IMAGE_FILE = DEFUALT_IMAGE_FILE
    else:
        # parse image to numpy array
        image = Image.open(IMAGE_FILE)
        image = image.convert("L")
        image = image.resize((IMG_WIDTH, IMG_HEIGHT))
        img = np.array(image, dtype=np.uint8)
        Image.fromarray(img).save(DEFUALT_IMAGE_FILE)
        print(f"Resized image saved to {DEFUALT_IMAGE_FILE}")

    generate_dump.generate_hex_dump(
        img.flatten(), hex_file_name="image_dump.v", bits_per_data=DATA_WIDTH
    )
