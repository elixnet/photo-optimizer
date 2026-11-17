# Photo Optimizer

A lightweight Python script for optimizing photographs for web use while preserving visual quality and selected image metadata.

The script processes JPEG and TIFF images in the current directory, resizes oversized images and saves the results as optimized JPEG files.

## Features

- Supports **JPG, JPEG, TIF and TIFF** input formats.
- Converts all supported images to JPEG.
- Resizes images so the longest edge does not exceed 2048 pixels.
- Preserves the original aspect ratio and never enlarges images.
- Uses adaptive JPEG quality based on the original file size.
- Saves progressive JPEGs with 4:4:4 chroma subsampling.
- Applies subtle sharpening only when an image is resized.
- Preserves ICC color profiles and DPI information.
- Preserves selected EXIF, IPTC and XMP metadata.
- Excludes GPS coordinates and camera serial numbers.
- Normalizes filenames to lowercase and replaces whitespace with underscores.
- Detects filename conflicts to prevent accidental overwriting.
- Displays processing progress and a final optimization summary.

## Requirements

- Windows with Python 3 installed.
- [Pillow](https://pypi.org/project/Pillow/) (image processing).
- [ExifTool](https://exiftool.org/) (metadata preservation)

### Installation

Install Pillow using pip:

```powershell
py -m pip install --upgrade Pillow
```

Install ExifTool using Windows Package Manager:

```powershell
winget install -e --id OliverBetz.ExifTool
```

Make sure ExifTool is available in your system PATH. You may need to restart your terminal after installation.

## Usage

1. Copy `photos-optimizer.py` into the directory containing your photographs.
2. Run the script:

```powershell
py photos-optimizer.py
```

3. Wait for the processing to finish.
4. Press Enter to close the window.

The script processes files in the current directory only. Subdirectories are not scanned.

**Important:** The script modifies, renames or converts the original files in the working directory. Always make a backup before running it.

## Optimization behavior

| Original file | Behavior |
|---|---|
| JPEG smaller than 200 KB | Skipped |
| JPEG 200 KB or larger | Optimized |
| TIFF of any size | Converted to JPEG |

JPEG quality is selected automatically according to the original file size. Smaller photographs receive higher quality settings, while larger files use progressively lower settings to achieve better compression.

The maximum image dimension is 2048 pixels. Images already within this limit are not resized.

## Output

All processed images are saved in JPEG format using:

- Progressive encoding
- 4:4:4 chroma subsampling
- Optimized Huffman tables
- Adaptive JPEG quality
- Preserved color profile and selected metadata

The script prints a summary containing the number of optimized, converted, skipped and unchanged files, along with the total storage savings.

## Limitations

- Only the current directory is processed.
- Multi-page TIFF files are processed using their first frame.
- Transparency is flattened against a white background.
- GPS coordinates and camera serial numbers are intentionally excluded from preserved metadata.

## License

This project is open-source and available under the [MIT License](LICENSE).

## Support the Project

This script is **free and open source**. Use it, modify it, share it - no strings attached.
If it saves you time and makes your photography workflow a little easier, consider buying me a coffee.

Every contribution is completely voluntary and greatly appreciated. It helps support the time and effort behind this project.

**Bitcoin (BTC):**

`bc1qznjr2949n6297307ct7exprr5n77l9dlnzd698`

Thank you for supporting open-source software!