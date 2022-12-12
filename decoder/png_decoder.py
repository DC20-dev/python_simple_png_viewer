import struct
import zlib


class PngDecoder:
    """PNG decoder based off Pyokagan's implementation: https://pyokagan.name/blog/2019-10-14-png/
    
    It only supports 8 bit truecolor with alpha"""

    def decode(self, filepath):
        """Decodes a PNG file"""
        file = open(filepath, 'rb')
        png_signature = b'\x89PNG\r\n\x1a\n'  # 89 50 4E 47 0D 0A 1A 0A
        if (file.read(len(png_signature)) != png_signature):
            raise PngDecoder.InvalidSignatureException(png_signature)

        chunks = []
        while True:
            chunk_type, chunk_data = self.__read_chunk(file)
            chunks.append((chunk_type, chunk_data))
            if chunk_type == b'IEND':   # end of file
                break
        self.__process_chunks(chunks)
        return (self.reconstructed_data, self.width, self.height)

    def __read_chunk(self, file):
        """returns (chunk_type, chunk_data)"""
        # first 4 bytes = length of the data section (>=0), second 4 bytes = type (ex. IHDR)
        chunk_length, chunk_type = struct.unpack('>I4s', file.read(8))
        # reads the data contained in the chunk
        chunk_data = file.read(chunk_length)
        # crc is the last 4 bytes; first compute the checksum with the info already owned
        # then check if it corresponds to the crc to spot possible corruption
        checksum = zlib.crc32(chunk_data, zlib.crc32(
            struct.pack('>4s', chunk_type)))
        chunk_crc, = struct.unpack('>I', file.read(4))
        if chunk_crc != checksum:
            raise PngDecoder.ChecksumFailedException(chunk_crc, checksum)
        return (chunk_type, chunk_data)

    def __process_chunks(self, chunks: list):
        """processes the supported chunk types (IHDR and IDAT) and reconstructs the image"""
        # IHDR is first as a convention
        _, IHDR_data = chunks[0]
        self.width, self.height, bit_depth, color_type, compression_m, filter_m, interlace_m = struct.unpack(
            '>IIBBBBB', IHDR_data)
        # only accepted value for filter and compression method is 0 as a standard
        if compression_m != 0:
            raise PngDecoder.InvalidCompressionException
        if filter_m != 0:
            raise PngDecoder.InvalidFilterException
        # restricting to RGBA8
        if color_type != 6:
            raise PngDecoder.InvalidColorTypeException(color_type)
        if bit_depth != 8:
            raise PngDecoder.InvalidBitDepthException
        if interlace_m != 0:
            raise PngDecoder.InvalidInterlaceMethodException
        # IDAT next
        # first concatenate all the data, even if the IDAT chunks are consecutive
        IDAT_data = b''.join(chunk_data for chunk_type,
                             chunk_data in chunks if chunk_type == b'IDAT')
        IDAT_data = zlib.decompress(IDAT_data)
        self.__reconstruct_data(IDAT_data)
    
    def __reconstruct_data(self, IDAT_data):
        self.reconstructed_data = []
        self.bytes_per_pixel = 4
        self.stride = self.width * self.bytes_per_pixel
        i = 0
        for r in range(self.height):  # for each scanline
            filter_type = IDAT_data[i]  # first byte in scanline is filter type
            i += 1
            for c in range(self.stride):  # for each byte in scanline
                filter_x = IDAT_data[i]
                i += 1
                if filter_type == 0:    # None
                    reconstructed_x = filter_x
                elif filter_type == 1:  # Sub
                    reconstructed_x = filter_x + self.__reconstruct_a(r, c)
                elif filter_type == 2:  # Up
                    reconstructed_x = filter_x + self.__reconstruct_b(r, c)
                elif filter_type == 3:  # Average
                    reconstructed_x = filter_x + \
                        (self.__reconstruct_a(r, c) +
                         self.__reconstruct_b(r, c)) // 2
                elif filter_type == 4:  # Paeth
                    reconstructed_x = filter_x + self.__paeth_predictor(self.__reconstruct_a(r, c),
                                                                        self.__reconstruct_b(r, c), self.__reconstruct_c(r, c))
                else:
                    raise PngDecoder.InvalidFilterException(
                        'unknown filter type: ' + str(filter_type))
                self.reconstructed_data.append(
                    reconstructed_x & 0xff)   # truncation to byte

    def __paeth_predictor(self, a, b, c):
        """Picks the best filtering for the scanline"""
        p = a + b - c
        pa = abs(p-a)
        pb = abs(p-b)
        pc = abs(p-c)
        if pa <= pb and pa <= pc:
            pres = a
        elif pb <= pc:
            pres = b
        else:
            pres = c
        return pres

    def __reconstruct_a(self, r, c):
        """a is the byte corresponding to x in the pixel immediately before
         the pixel containing x (or 0 if out of bounds)"""
        return self.reconstructed_data[r * self.stride + c - self.bytes_per_pixel
                                  ] if c >= self.bytes_per_pixel else 0

    def __reconstruct_b(self, r, c):
        """b is the byte corresponding to x in the previous scanline (or 0 if out of bounds)"""
        return self.reconstructed_data[(r-1) * self.stride + c] if r > 0 else 0

    def __reconstruct_c(self, r, c):
        """c is the byte corresponding to b in the pixel 
        immediately before the pixel containing b (or 0 if out of bounds)"""
        return self.reconstructed_data[(r-1)*self.stride + c - self.bytes_per_pixel
                                  ] if r > 0 and c >= self.bytes_per_pixel else 0

    class PngDecoderException(Exception):
        def __init__(self, message):
            self.message = message

    class InvalidSignatureException(PngDecoderException):
        def __init__(self, signature, message='Invalid PNG Signature'):
            self.message = message
            print(f'file signature is: {signature}')

    class ChecksumFailedException(PngDecoderException):
        def __init__(self, crc, checksum):
            self.message = f"chunk checksum failed {crc} != {checksum}"

    class InvalidCompressionException(PngDecoderException):
        def __init__(self):
            self.message = 'Invalid compression method!'

    class InvalidFilterException(PngDecoderException):
        def __init__(self, message='Invalid filter method!'):
            self.message = message

    class InvalidColorTypeException(PngDecoderException):
        def __init__(self, color_type):
            self.message = f'Color type {color_type} is not supported!'

    class InvalidBitDepthException(PngDecoderException):
        def __init__(self):
            self.message = 'Only a bit depth of 8 is supported!'

    class InvalidInterlaceMethodException(PngDecoderException):
        def __init__(self):
            self.message = 'There is no interlacing support!'
