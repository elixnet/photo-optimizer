"""
Photo Optimizer
===============

A lightweight image optimization script for web use.

Supported formats:
    JPG, JPEG, TIF, TIFF

Features:
    - Resizes images to a maximum dimension of 2048 pixels.
    - Uses adaptive JPEG quality based on the original file size.
    - Saves progressive JPEGs with 4:4:4 chroma subsampling.
    - Applies subtle sharpening when resizing.
    - Preserves selected EXIF, IPTC and XMP metadata.
    - Preserves ICC color profiles and DPI information.
    - Normalizes filenames and detects naming conflicts.

Requirements:
    Python 3
    Pillow
    ExifTool

Installation:
    py -m pip install --upgrade Pillow
    winget install -e --id OliverBetz.ExifTool

Usage:
    Place this script in the directory containing your images
    and run:

        py Optimize-Photos.py

    Only files in the current directory are processed.

IMPORTANT:
    This script modifies, renames or converts source files.
    Always create a backup before running it.

Author:
    Elix (<https://github.com/elixnet>)

Repository:
    <https://github.com/elixnet/photo-optimizer>

License:
    See the repository for licensing information.
"""
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter, ImageCms
import subprocess
import shutil
import tempfile
import os
import re
import io
from datetime import datetime

# ============================================================
# PHOTO OPTIMIZER
# ============================================================

# Maximum dimension for resizing (width or height)
MAX_DIMENSION = 2048

# Minimum file size for JPEG optimization (200 KB)
MIN_FILE_SIZE = 200 * 1024

# JPEG settings
JPEG_SAMPLING = 0       # 0 = 4:4:4
JPEG_PROGRESSIVE = True
JPEG_OPTIMIZE = True

# Sharpening - only when resizing
SHARPEN_RADIUS = 0.5
SHARPEN_PERCENT = 50
SHARPEN_THRESHOLD = 3

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".tif", ".tiff"
}

JPEG_EXTENSIONS = {
    ".jpg", ".jpeg"
}

# EXIF metadata to preserve
EXIF_TAGS = [
    "Make",
    "Model",
    "LensMake",
    "LensModel",
    "DateTimeOriginal",
    "CreateDate",
    "ExposureTime",
    "FNumber",
    "ISO",
    "FocalLength",
    "FocalLengthIn35mmFormat",
    "ExposureProgram",
    "MeteringMode",
    "Flash",
    "WhiteBalance",
    "ExposureCompensation",
    "Artist",
    "Copyright",
]

# Selected XMP metadata
XMP_TAGS = [
    "XMP-dc:Creator",
    "XMP-dc:Rights",
    "XMP-dc:Publisher",
    "XMP-dc:Source",
    "XMP-dc:Description",
    "XMP-xmpRights:UsageTerms",
    "XMP-xmpRights:WebStatement",
    "XMP-xmpRights:Marked",
    "XMP-photoshop:Credit",
    "XMP-photoshop:Copyright",
    "XMP-photoshop:AuthorsPosition",
]

# Pillow imports are checked at runtime
PIL = None
Image = None
ImageOps = None
ImageFilter = None
ImageCms = None


# ============================================================
# DEPENDENCY CHECK
# ============================================================

def check_dependencies():

    global PIL, Image, ImageOps, ImageFilter, ImageCms

    print("\nCHECKING DEPENDENCIES")
    print("-" * 62)

    missing = []

    # Pillow
    try:
        import PIL as pil_module
        from PIL import Image as image_module
        from PIL import ImageOps as image_ops
        from PIL import ImageFilter as image_filter
        from PIL import ImageCms as image_cms

        PIL = pil_module
        Image = image_module
        ImageOps = image_ops
        ImageFilter = image_filter
        ImageCms = image_cms

        print(f"[OK] Pillow: {PIL.__version__}")

    except ImportError:
        print("[MISSING] Pillow")
        missing.append("Pillow")

    # ExifTool
    exiftool = (
        shutil.which("exiftool")
        or shutil.which("exiftool.exe")
    )

    if exiftool:

        result = subprocess.run(
            [exiftool, "-ver"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode == 0:
            print(f"[OK] ExifTool: {result.stdout.strip()}")
        else:
            print("[ERROR] ExifTool cannot be executed.")
            missing.append("ExifTool")
            exiftool = None

    else:
        print("[MISSING] ExifTool")
        missing.append("ExifTool")

    if missing:

        print("\n" + "=" * 62)
        print("              MISSING DEPENDENCIES")
        print("=" * 62)

        if "Pillow" in missing:
            print("\nInstall Pillow:")
            print("  py -m pip install --upgrade Pillow")

        if "ExifTool" in missing:
            print("\nInstall ExifTool:")
            print("  winget install -e --id OliverBetz.ExifTool")

        print("\nInstall missing dependencies and restart the script.")

        return None

    print("\nAll dependencies are available.")

    return exiftool


# ============================================================
# HELPERS
# ============================================================

def format_size(size):

    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"

    return f"{size / 1024:.1f} KB"


def normalize_filename(filename):
    """Normalize filename for web usage."""

    name = Path(filename).stem.lower()

    # Remove unwanted characters
    name = re.sub(r"[)(\[\]]", "", name)

    # Replace spaces and whitespace with underscores
    name = re.sub(r"\s+", "_", name)

    # Remove repeated underscores
    name = re.sub(r"_+", "_", name)

    name = name.strip("_")

    if not name:
        raise ValueError("Filename would be empty.")

    return name + ".jpg"


def get_jpeg_quality(size):
    """Adaptive JPEG quality based on original file size."""

    mb = size / (1024 * 1024)

    if size < 500 * 1024:
        return 96
    elif mb < 1:
        return 95
    elif mb < 2:
        return 93
    elif mb < 3:
        return 91
    elif mb < 5:
        return 90
    else:
        return 88


def safe_rename(source, destination):
    """Rename through an intermediate filename."""

    if source.name == destination.name:
        return

    intermediate = source.with_name(
        f".{source.stem}.rename_{os.getpid()}{source.suffix}"
    )

    if intermediate.exists():
        raise FileExistsError(intermediate)

    os.replace(source, intermediate)

    try:
        os.replace(intermediate, destination)

    except Exception:
        os.replace(intermediate, source)
        raise


# ============================================================
# COLOR MANAGEMENT
# ============================================================

def convert_to_rgb(image):
    """Convert image to RGB and prepare ICC profile."""

    icc = image.info.get("icc_profile")

    srgb_profile = ImageCms.createProfile("sRGB")

    srgb_bytes = ImageCms.ImageCmsProfile(
        srgb_profile
    ).tobytes()

    # Handle transparency
    if (
        image.mode in ("RGBA", "LA")
        or "transparency" in image.info
    ):

        rgba = image.convert("RGBA")

        background = Image.new(
            "RGB",
            rgba.size,
            (255, 255, 255)
        )

        background.paste(
            rgba,
            mask=rgba.getchannel("A")
        )

        return background, srgb_bytes

    # Preserve original RGB profile
    if image.mode == "RGB":

        return image.copy(), icc or srgb_bytes

    # Convert using embedded color profile
    if icc:

        try:

            source_profile = ImageCms.ImageCmsProfile(
                io.BytesIO(icc)
            )

            converted = ImageCms.profileToProfile(
                image,
                source_profile,
                srgb_profile,
                outputMode="RGB"
            )

            return converted, srgb_bytes

        except Exception:
            pass

    return image.convert("RGB"), srgb_bytes


# ============================================================
# METADATA
# ============================================================

def copy_metadata(exiftool, source, destination):
    """Copy selected EXIF, IPTC and XMP metadata."""

    command = [
        exiftool,
        "-overwrite_original",
        "-TagsFromFile",
        str(source),
    ]

    # Selected EXIF tags
    for tag in EXIF_TAGS:
        command.append(f"-EXIF:{tag}")

    # Preserve IPTC metadata
    command.append("-IPTC:all")

    # Selected XMP tags
    for tag in XMP_TAGS:
        command.append(f"-{tag}")

    command.append(str(destination))

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stderr.strip()
            or "ExifTool metadata processing failed."
        )


# ============================================================
# SAFE FILE REPLACEMENT
# ============================================================

def commit_file(source, temporary, destination):
    """Safely replace source with processed file."""

    backup = source.with_name(
        f".{source.name}.backup_{os.getpid()}"
    )

    if backup.exists():
        raise FileExistsError(backup)

    os.replace(source, backup)

    try:

        os.replace(temporary, destination)

    except Exception:

        os.replace(backup, source)
        raise

    backup.unlink()


# ============================================================
# IMAGE PROCESSING
# ============================================================

def process_image(source, exiftool):

    original_size = source.stat().st_size

    original_extension = source.suffix.lower()

    is_jpeg = original_extension in JPEG_EXTENSIONS

    destination = source.with_name(
        normalize_filename(source.name)
    )

    # Check target filename collision
    if (
        destination.exists()
        and not os.path.samefile(source, destination)
    ):

        raise FileExistsError(
            f"Target filename already exists: {destination.name}"
        )

    # Read image dimensions
    with Image.open(source) as original:

        original_width, original_height = original.size

        image = ImageOps.exif_transpose(original)

        width, height = image.size

        resized = max(width, height) > MAX_DIMENSION

        # Small JPEG files are not reprocessed
        if is_jpeg and original_size <= MIN_FILE_SIZE:

            if source.name != destination.name:
                safe_rename(source, destination)

            return {
                "status": "SKIPPED",
                "reason": "Under 200 KB",
                "original": original_size,
                "final": destination.stat().st_size,
                "dimensions": f"{width} x {height}",
                "name": destination.name,
            }

        # Proportional resizing
        if resized:

            image.thumbnail(
                (MAX_DIMENSION, MAX_DIMENSION),
                Image.Resampling.LANCZOS
            )

        # Convert to RGB and prepare ICC profile
        image, icc_profile = convert_to_rgb(image)

        # Light sharpening only after resizing
        if resized:

            image = image.filter(
                ImageFilter.UnsharpMask(
                    radius=SHARPEN_RADIUS,
                    percent=SHARPEN_PERCENT,
                    threshold=SHARPEN_THRESHOLD
                )
            )

        final_dimensions = f"{image.width} x {image.height}"

        # Adaptive JPEG quality
        quality = (
            get_jpeg_quality(original_size)
            if original_size > MIN_FILE_SIZE
            else 95
        )

        # Preserve DPI when available
        dpi = original.info.get("dpi")

        temp_handle = tempfile.NamedTemporaryFile(
            prefix=".optimizer_",
            suffix=".jpg",
            dir=source.parent,
            delete=False
        )

        temp_path = Path(temp_handle.name)
        temp_handle.close()

        try:

            # Save optimized JPEG
            image.save(
                temp_path,
                format="JPEG",
                quality=quality,
                subsampling=JPEG_SAMPLING,
                progressive=JPEG_PROGRESSIVE,
                optimize=JPEG_OPTIMIZE,
                icc_profile=icc_profile,
                dpi=dpi
            )

        finally:

            image.close()

    try:

        # Copy selected metadata
        copy_metadata(
            exiftool,
            source,
            temp_path
        )

        optimized_size = temp_path.stat().st_size

        # Keep original JPEG if optimization increases size
        if is_jpeg and optimized_size >= original_size:

            temp_path.unlink()

            if source.name != destination.name:
                safe_rename(source, destination)

            return {
                "status": "KEPT",
                "reason": "Original is smaller",
                "original": original_size,
                "final": destination.stat().st_size,
                "dimensions": f"{width} x {height}",
                "name": destination.name,
            }

        # Replace original safely
        commit_file(
            source,
            temp_path,
            destination
        )

        return {
            "status": (
                "CONVERTED"
                if not is_jpeg
                else "OPTIMIZED"
            ),
            "original": original_size,
            "final": destination.stat().st_size,
            "quality": quality,
            "dimensions": final_dimensions,
            "resized": resized,
            "name": destination.name,
        }

    finally:

        if temp_path.exists():
            temp_path.unlink()


# ============================================================
# MAIN
# ============================================================

def main():

    folder = Path(__file__).resolve().parent

    print()
    print("=" * 62)
    print("              PHOTO OPTIMIZER")
    print("=" * 62)

    # Check dependencies before processing
    exiftool = check_dependencies()

    if not exiftool:
        return

    print(f"\nWorking directory: {folder}")
    print(f"Maximum dimension: {MAX_DIMENSION} px")
    print(f"Minimum JPEG size: {format_size(MIN_FILE_SIZE)}")

    # Find supported images in current directory only
    photos = sorted(
        [
            file for file in folder.iterdir()
            if file.is_file()
            and file.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=lambda file: file.name.lower()
    )

    if not photos:

        print("\nNo supported images found.")
        return

    # Pre-check filename collisions
    targets = {}

    for photo in photos:

        target_name = normalize_filename(photo.name).casefold()

        targets.setdefault(
            target_name,
            []
        ).append(photo)

    collisions = {
        name
        for name, files in targets.items()
        if len(files) > 1
    }

    print(f"\nFound images: {len(photos)}")
    print("-" * 62)

    stats = {
        "OPTIMIZED": 0,
        "CONVERTED": 0,
        "SKIPPED": 0,
        "KEPT": 0,
        "ERROR": 0,
    }

    total_before = 0
    total_after = 0

    for index, photo in enumerate(photos, start=1):

        original_size = photo.stat().st_size

        total_before += original_size

        print(
            f"\n[{index:02}/{len(photos):02}] {photo.name}"
        )

        try:

            target_name = normalize_filename(
                photo.name
            ).casefold()

            if target_name in collisions:

                raise FileExistsError(
                    "Multiple files would have the same target name."
                )

            result = process_image(
                photo,
                exiftool
            )

            status = result["status"]

            stats[status] += 1

            total_after += result["final"]

            print(
                f"  Dimensions: {result['dimensions']}"
            )

            if status in ("OPTIMIZED", "CONVERTED"):

                print(
                    f"  JPEG quality: {result['quality']}"
                )

                if result["resized"]:
                    print("  Resized and sharpened: YES")
                else:
                    print("  Resized: NO")

            else:

                print(f"  Reason: {result['reason']}")

            print(
                f"  Size: {format_size(result['original'])}"
                f" -> {format_size(result['final'])}"
            )

            print(f"  Output: {result['name']}")
            print(f"  Status: {status}")

        except Exception as error:

            stats["ERROR"] += 1

            total_after += original_size

            print(f"  ERROR: {error}")
            print("  Original file preserved.")

    # ========================================================
    # SUMMARY
    # ========================================================

    saved = total_before - total_after

    percentage = (
        saved / total_before * 100
        if total_before > 0
        else 0
    )

    print()
    print("=" * 62)
    print("                    SUMMARY")
    print("=" * 62)

    for status, count in stats.items():

        print(f"{status:<15}: {count}")

    print("-" * 62)

    print(f"Original size:  {format_size(total_before)}")
    print(f"Final size:     {format_size(total_after)}")

    if saved >= 0:

        print(
            f"Saved:          {format_size(saved)}"
            f" ({percentage:.1f} %)"
        )

    else:

        print(
            f"Size increase:  {format_size(abs(saved))}"
            f" ({abs(percentage):.1f} %)"
        )

    print("=" * 62)

    print(
        f"Finished: {datetime.now():%d.%m.%Y %H:%M:%S}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print("\n\nOperation interrupted by user.")

    except Exception as error:

        print(f"\nFATAL ERROR: {error}")

    input("\nPress Enter to exit...")
