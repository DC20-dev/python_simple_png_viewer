import sys
import decoder.png_decoder as pngdec
from PIL import Image, ImageDraw

def run():
    decoder = pngdec.PngDecoder()
    for index, arg in enumerate(sys.argv[1:]):
        try:
            data, width, height = decoder.decode(arg)
            draw_image(data, width, height)
        except pngdec.PngDecoder.InvalidSignatureException as e:
            print(e.message)
        except FileNotFoundError as e:
            print(f"No such file: {arg}")

def draw_image(raw_data, width, height):
    image = Image.frombytes("RGBA", (width, height),raw_data)
    drawer = ImageDraw.Draw(image)
    image.show()

if __name__ == "__main__":
    run()