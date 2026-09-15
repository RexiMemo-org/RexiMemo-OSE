from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

PROPRIETARY_FORMATS = {"ntft", "npf", "nbf"}
STANDARD_OUTPUT_FORMATS = {"png", "jpeg", "webp", "bmp", "gif"}
OUTPUT_FORMATS = PROPRIETARY_FORMATS | STANDARD_OUTPUT_FORMATS
MAX_DIMENSION = 2048
MAX_PIXELS = 4_194_304

FORMAT_LABELS = {
    "ntft": "NTFT",
    "npf": "NPF",
    "nbf": "NBF",
    "png": "PNG",
    "jpeg": "JPEG",
    "webp": "WebP",
    "bmp": "BMP",
    "gif": "GIF",
}

FORMAT_NOTES = {
    "ntft": "16-bit ABGR1555 pixels with 1-bit alpha. Dimensions are not stored in the file.",
    "npf": "4-bit indexed image: transparent index plus up to 15 opaque colors. Dimensions are not stored in the file.",
    "nbf": "8-bit indexed image with up to 256 opaque colors. Dimensions are not stored in the file.",
    "png": "Lossless standard image with full alpha support.",
    "jpeg": "Lossy standard image. Transparency is flattened onto white.",
    "webp": "Modern standard image with alpha support when available in Pillow.",
    "bmp": "Uncompressed standard bitmap. Transparency is flattened onto white.",
    "gif": "Palette-based standard image. The converter writes one still frame.",
}

MIME_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "ntft": "application/octet-stream",
    "npf": "application/octet-stream",
    "nbf": "application/octet-stream",
}

EXTENSIONS = {
    "png": "png",
    "jpeg": "jpg",
    "webp": "webp",
    "bmp": "bmp",
    "gif": "gif",
    "ntft": "ntft",
    "npf": "npf",
    "nbf": "nbf",
}

PIL_FORMAT_MAP = {
    "PNG": "png",
    "JPEG": "jpeg",
    "JPG": "jpeg",
    "WEBP": "webp",
    "BMP": "bmp",
    "GIF": "gif",
    "TIFF": "tiff",
}


class ConversionError(ValueError):
    pass


@dataclass
class DecodedImage:
    image: Image.Image
    format_key: str
    format_label: str
    width: int
    height: int
    frames: int = 1
    note: str = ""


@dataclass
class EncodedImage:
    data: bytes
    format_key: str
    format_label: str
    extension: str
    mime_type: str
    preview: Image.Image
    note: str = ""


def _round_power_of_two(value: int) -> int:
    value = int(value)
    if value <= 0:
        raise ConversionError("Image dimensions must be positive numbers.")
    power = 1
    while power < value:
        power <<= 1
    return power


def _validate_size(width: int, height: int) -> tuple[int, int]:
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise ConversionError("Image width and height must both be greater than zero.")
    if width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
        raise ConversionError("Images are limited to 2048 px per side and about 4.2 million pixels.")
    return width, height


def _parse_dimensions(width, height) -> tuple[int, int]:
    try:
        width = int(str(width or "").strip())
        height = int(str(height or "").strip())
    except (TypeError, ValueError):
        raise ConversionError("Enter the original width and height for this Flipnote image file.")
    return _validate_size(width, height)


def _unpack_abgr1555(value: int, use_alpha: bool = True) -> tuple[int, int, int, int]:
    r5 = value & 0x1F
    g5 = (value >> 5) & 0x1F
    b5 = (value >> 10) & 0x1F
    alpha_bit = (value >> 15) & 0x01
    r = (r5 << 3) | (r5 >> 2)
    g = (g5 << 3) | (g5 >> 2)
    b = (b5 << 3) | (b5 >> 2)
    a = 0 if use_alpha and alpha_bit == 0 else 255
    return r, g, b, a


def _pack_abgr1555(color, use_alpha: bool = True) -> int:
    r, g, b = int(color[0]), int(color[1]), int(color[2])
    a = int(color[3]) if len(color) > 3 else 255
    r5 = r * 0x1F // 0xFF
    g5 = g * 0x1F // 0xFF
    b5 = b * 0x1F // 0xFF
    alpha_bit = 0 if use_alpha and a < 0x80 else 1
    return (alpha_bit << 15) | (b5 << 10) | (g5 << 5) | r5


def _read_ugar_sections(data: bytes) -> list[bytes]:
    if len(data) < 12 or data[:4] != b"UGAR":
        raise ConversionError("This file does not have a valid UGAR header.")
    section_count = struct.unpack_from("<I", data, 4)[0]
    if section_count < 2 or section_count > 16:
        raise ConversionError("The UGAR section table is not valid.")
    table_end = 8 + section_count * 4
    if table_end > len(data):
        raise ConversionError("The UGAR section table is truncated.")
    lengths = struct.unpack_from("<" + "I" * section_count, data, 8)
    offset = table_end
    sections = []
    for length in lengths:
        if length > len(data) - offset:
            raise ConversionError("The UGAR image data is truncated.")
        sections.append(data[offset:offset + length])
        offset += length
    return sections


def _write_ugar_sections(*sections: bytes) -> bytes:
    out = io.BytesIO()
    out.write(b"UGAR")
    out.write(struct.pack("<I", len(sections)))
    out.write(struct.pack("<" + "I" * len(sections), *(len(section) for section in sections)))
    for section in sections:
        out.write(section)
    return out.getvalue()


def _decode_ntft(data: bytes, width: int, height: int) -> Image.Image:
    width, height = _validate_size(width, height)
    if len(data) % 2:
        raise ConversionError("NTFT data must contain complete 16-bit pixels.")
    padded_width = _round_power_of_two(width)
    pixel_count = len(data) // 2
    if pixel_count % padded_width:
        raise ConversionError("The NTFT byte length does not match the supplied width.")
    stored_height = pixel_count // padded_width
    if height > stored_height:
        raise ConversionError("The supplied height is larger than the NTFT pixel data.")
    values = struct.unpack("<" + "H" * pixel_count, data)
    rgba = [_unpack_abgr1555(value, use_alpha=True) for value in values]
    image = Image.new("RGBA", (padded_width, stored_height))
    image.putdata(rgba)
    return image.crop((0, 0, width, height))


def _decode_npf(data: bytes, width: int, height: int) -> Image.Image:
    width, height = _validate_size(width, height)
    sections = _read_ugar_sections(data)
    palette_data, image_data = sections[0], sections[1]
    if len(palette_data) < 2 or len(palette_data) % 2:
        raise ConversionError("The NPF palette section is invalid.")
    palette_values = struct.unpack("<" + "H" * (len(palette_data) // 2), palette_data)
    palette = [_unpack_abgr1555(value, use_alpha=False) for value in palette_values]
    if len(palette) > 16:
        raise ConversionError("NPF files can use at most 16 palette entries.")
    indices = []
    for value in image_data:
        indices.append(value & 0x0F)
        indices.append((value >> 4) & 0x0F)
    padded_width = _round_power_of_two(width)
    if len(indices) % padded_width:
        raise ConversionError("The NPF byte length does not match the supplied width.")
    stored_height = len(indices) // padded_width
    if height > stored_height:
        raise ConversionError("The supplied height is larger than the NPF pixel data.")
    pixels = []
    for index in indices:
        if index == 0:
            pixels.append((0, 0, 0, 0))
        elif index < len(palette):
            r, g, b, _ = palette[index]
            pixels.append((r, g, b, 255))
        else:
            pixels.append((0, 0, 0, 0))
    image = Image.new("RGBA", (padded_width, stored_height))
    image.putdata(pixels)
    return image.crop((0, 0, width, height))


def _decode_nbf(data: bytes, width: int, height: int) -> Image.Image:
    width, height = _validate_size(width, height)
    sections = _read_ugar_sections(data)
    palette_data, image_data = sections[0], sections[1]
    if len(palette_data) < 2 or len(palette_data) % 2:
        raise ConversionError("The NBF palette section is invalid.")
    if len(palette_data) > 512:
        raise ConversionError("The NBF palette contains more than 256 colors.")
    palette_values = struct.unpack("<" + "H" * (len(palette_data) // 2), palette_data)
    palette = [_unpack_abgr1555(value, use_alpha=False) for value in palette_values]
    padded_width = _round_power_of_two(width)
    if len(image_data) % padded_width:
        raise ConversionError("The NBF byte length does not match the supplied width.")
    stored_height = len(image_data) // padded_width
    if height > stored_height:
        raise ConversionError("The supplied height is larger than the NBF pixel data.")
    pixels = []
    for index in image_data:
        if index >= len(palette):
            raise ConversionError("The NBF image references a palette entry that is not present.")
        r, g, b, _ = palette[index]
        pixels.append((r, g, b, 255))
    image = Image.new("RGBA", (padded_width, stored_height))
    image.putdata(pixels)
    return image.crop((0, 0, width, height))


def _pad_rows(values: list, width: int, height: int) -> tuple[list, int]:
    padded_width = _round_power_of_two(width)
    if padded_width == width:
        return list(values), padded_width
    padded = []
    for y in range(height):
        row = list(values[y * width:(y + 1) * width])
        edge = row[-1]
        padded.extend(row)
        padded.extend([edge] * (padded_width - width))
    return padded, padded_width


def _quantize_5bit(image: Image.Image, colors: int) -> Image.Image:
    rgb = ImageOps.posterize(image.convert("RGB"), 5)
    quantize_namespace = getattr(Image, "Quantize", None)
    method = getattr(quantize_namespace, "MEDIANCUT", 0) if quantize_namespace is not None else 0
    return rgb.quantize(colors=colors, method=method)


def _palette_colors(image: Image.Image, count: int) -> list[tuple[int, int, int, int]]:
    raw = image.getpalette() or []
    colors = []
    for index in range(count):
        base = index * 3
        if base + 2 < len(raw):
            colors.append((raw[base], raw[base + 1], raw[base + 2], 255))
        else:
            colors.append((0, 0, 0, 255))
    return colors


def _encode_ntft(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    width, height = _validate_size(*rgba.size)
    pixels, _ = _pad_rows(list(rgba.getdata()), width, height)
    out = bytearray(len(pixels) * 2)
    for i, color in enumerate(pixels):
        struct.pack_into("<H", out, i * 2, _pack_abgr1555(color, use_alpha=True))
    return bytes(out)


def _encode_npf(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    width, height = _validate_size(*rgba.size)
    if _round_power_of_two(width) < 2:
        raise ConversionError("NPF images must be at least 2 pixels wide.")
    quantized = _quantize_5bit(rgba, 15)
    palette = _palette_colors(quantized, 15)
    palette_values = [0] + [_pack_abgr1555(color, use_alpha=False) for color in palette]
    palette_data = struct.pack("<" + "H" * len(palette_values), *palette_values)
    indices = list(quantized.getdata())
    alpha = list(rgba.getchannel("A").getdata())
    combined = [int(index) + 1 if int(a) > 128 else 0 for index, a in zip(indices, alpha)]
    combined, _ = _pad_rows(combined, width, height)
    if len(combined) % 2:
        combined.append(combined[-1])
    image_data = bytes((combined[i] & 0x0F) | ((combined[i + 1] & 0x0F) << 4) for i in range(0, len(combined), 2))
    return _write_ugar_sections(palette_data, image_data)


def _encode_nbf(image: Image.Image) -> bytes:
    rgb = image.convert("RGB")
    width, height = _validate_size(*rgb.size)
    quantized = _quantize_5bit(rgb, 256)
    palette = _palette_colors(quantized, 256)
    palette_values = [_pack_abgr1555(color, use_alpha=False) for color in palette]
    palette_data = struct.pack("<" + "H" * len(palette_values), *palette_values)
    indices = list(quantized.getdata())
    indices, _ = _pad_rows(indices, width, height)
    image_data = bytes(int(index) & 0xFF for index in indices)
    return _write_ugar_sections(palette_data, image_data)


def _flatten_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, "white")
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _save_standard(image: Image.Image, format_key: str) -> bytes:
    out = io.BytesIO()
    if format_key == "png":
        image.convert("RGBA").save(out, "PNG", optimize=True)
    elif format_key == "jpeg":
        _flatten_white(image).save(out, "JPEG", quality=92, optimize=True)
    elif format_key == "webp":
        image.convert("RGBA").save(out, "WEBP", quality=90, method=4)
    elif format_key == "bmp":
        _flatten_white(image).save(out, "BMP")
    elif format_key == "gif":
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        quantized = _quantize_5bit(rgba, 255)
        mask = alpha.point(lambda value: 255 if value <= 128 else 0)
        quantized.paste(255, mask=mask)
        palette = quantized.getpalette() or [0] * 768
        if len(palette) < 768:
            palette += [0] * (768 - len(palette))
        palette[255 * 3:255 * 3 + 3] = [0, 0, 0]
        quantized.putpalette(palette)
        quantized.save(out, "GIF", transparency=255, optimize=False)
    else:
        raise ConversionError("That output format is not supported.")
    return out.getvalue()


def _decode_standard(data: bytes) -> tuple[Image.Image, str, int]:
    try:
        with Image.open(io.BytesIO(data)) as source:
            format_key = PIL_FORMAT_MAP.get((source.format or "").upper())
            if not format_key:
                raise ConversionError("That standard image type is not supported.")
            width, height = _validate_size(*source.size)
            frames = int(getattr(source, "n_frames", 1) or 1)
            source.seek(0)
            image = source.convert("RGBA")
            image.load()
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError("The uploaded image could not be decoded.") from exc
    return image, format_key, frames


def _normalize_input_format(filename: str, requested: str, data: bytes) -> str:
    requested = (requested or "auto").strip().lower()
    aliases = {"jpg": "jpeg", "standard": "standard", "auto": "auto"}
    requested = aliases.get(requested, requested)
    if requested in PROPRIETARY_FORMATS or requested == "standard":
        return requested
    if requested != "auto":
        raise ConversionError("Choose a supported input format.")
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext in PROPRIETARY_FORMATS:
        return ext
    if ext in {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"}:
        return "standard"
    if data.startswith(b"UGAR"):
        try:
            sections = _read_ugar_sections(data)
        except ConversionError:
            sections = []
        if sections and len(sections[0]) == 32:
            return "npf"
        raise ConversionError("This looks like an UGAR image. Choose NPF or NBF as the input format so RexiMemo can decode it correctly.")
    raise ConversionError("RexiMemo could not identify the input type. Choose the input format manually.")


def decode_uploaded_image(data: bytes, filename: str, input_format: str = "auto", width=None, height=None) -> DecodedImage:
    if not data:
        raise ConversionError("Choose an image file to convert.")
    format_key = _normalize_input_format(filename, input_format, data)
    if format_key == "standard":
        image, detected, frames = _decode_standard(data)
        note = "Only the first frame is converted." if frames > 1 else FORMAT_NOTES.get(detected, "Standard raster image.")
        return DecodedImage(image=image, format_key=detected, format_label=FORMAT_LABELS.get(detected, detected.upper()), width=image.width, height=image.height, frames=frames, note=note)
    width, height = _parse_dimensions(width, height)
    if format_key == "ntft":
        image = _decode_ntft(data, width, height)
    elif format_key == "npf":
        image = _decode_npf(data, width, height)
    elif format_key == "nbf":
        image = _decode_nbf(data, width, height)
    else:
        raise ConversionError("That Flipnote image format is not supported.")
    return DecodedImage(image=image, format_key=format_key, format_label=FORMAT_LABELS[format_key], width=width, height=height, frames=1, note=FORMAT_NOTES[format_key])


def encode_image(image: Image.Image, output_format: str) -> EncodedImage:
    output_format = (output_format or "").strip().lower()
    output_format = "jpeg" if output_format in {"jpg", "jpeg"} else output_format
    if output_format not in OUTPUT_FORMATS:
        raise ConversionError("Choose a supported output format.")
    rgba = image.convert("RGBA")
    _validate_size(*rgba.size)
    try:
        if output_format == "ntft":
            data = _encode_ntft(rgba)
            preview = _decode_ntft(data, rgba.width, rgba.height)
        elif output_format == "npf":
            data = _encode_npf(rgba)
            preview = _decode_npf(data, rgba.width, rgba.height)
        elif output_format == "nbf":
            data = _encode_nbf(rgba)
            preview = _decode_nbf(data, rgba.width, rgba.height)
        else:
            data = _save_standard(rgba, output_format)
            preview, _, _ = _decode_standard(data)
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError("The image could not be encoded in that format.") from exc
    return EncodedImage(
        data=data,
        format_key=output_format,
        format_label=FORMAT_LABELS[output_format],
        extension=EXTENSIONS[output_format],
        mime_type=MIME_TYPES[output_format],
        preview=preview,
        note=FORMAT_NOTES[output_format],
    )


def image_characteristics(image: Image.Image) -> dict:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    extrema = alpha.getextrema()
    has_transparency = bool(extrema and extrema[0] < 255)
    colors = rgba.getcolors(maxcolors=4097)
    color_count = len(colors) if colors is not None else None
    return {
        "mode": rgba.mode,
        "has_transparency": has_transparency,
        "color_count": color_count,
    }
