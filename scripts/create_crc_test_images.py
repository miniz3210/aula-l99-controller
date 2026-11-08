from pathlib import Path

from PIL import Image, ImageDraw


WIDTH = 320
HEIGHT = 480

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "crc_test_images"


def save_solid(name, color):
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        color,
    )

    output_file = OUTPUT_DIR / f"{name}.png"
    image.save(output_file)

    print(f"Saved: {output_file}")


def save_pattern():
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (0, 0, 0),
    )

    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (0, 0, 159, 239),
        fill=(255, 0, 0),
    )

    draw.rectangle(
        (160, 0, 319, 239),
        fill=(0, 255, 0),
    )

    draw.rectangle(
        (0, 240, 159, 479),
        fill=(0, 0, 255),
    )

    draw.rectangle(
        (160, 240, 319, 479),
        fill=(255, 255, 255),
    )

    draw.rectangle(
        (135, 215, 185, 265),
        fill=(255, 255, 0),
    )

    output_file = OUTPUT_DIR / "quadrants.png"
    image.save(output_file)

    print(f"Saved: {output_file}")


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_solid(
        "solid_black",
        (0, 0, 0),
    )

    save_solid(
        "solid_white",
        (255, 255, 255),
    )

    save_solid(
        "solid_red",
        (255, 0, 0),
    )

    save_solid(
        "solid_green",
        (0, 255, 0),
    )

    save_solid(
        "solid_blue",
        (0, 0, 255),
    )

    save_pattern()

    print()
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()