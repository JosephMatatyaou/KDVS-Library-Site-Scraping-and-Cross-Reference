#!/usr/bin/env python3
from PIL import Image
import os

# Create assets directory
os.makedirs('assets', exist_ok=True)

# Load the image
img = Image.open('icon.png')

# Ensure it's RGB (not RGBA) for some formats
if img.mode == 'RGBA':
    background = Image.new('RGB', img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])
    img = background

# Resize to common icon size
img_resized = img.resize((512, 512), Image.Resampling.LANCZOS)

# Save as .ico for Windows
img_resized.save('assets/icon.ico')

# Save main icon for pyinstaller
img_resized.save('assets/icon.png')

print("✅ Icons generated:")
print("  - assets/icon.ico (Windows)")
print("  - assets/icon.png (Mac)")
