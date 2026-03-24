# The Charter 3000

## Overview
This is a cross-platform Tkinter app that fetches KDVS library albums and cross-references them with Spinitron play reports so you can separate true library plays from outside sources.

## Run From Python

### Prerequisites
- Python 3.11+ recommended

### Setup
```bash
python3 -m pip install -r requirements.txt
python3 MergedKDVSApp.py
```

### Full Library Export
```bash
python3 KDVSFullLibraryExport.py
```

The exporter prompts for your KDVS username and password, then saves the full library catalog as `csv` by default.

Optional example with an explicit output path:
```bash
python3 KDVSFullLibraryExport.py --output kdvs_library.csv
```

## Build Shareable Apps

### Build Requirements
```bash
python3 -m pip install -r requirements-build.txt
```

### macOS
```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

This creates the shareable package `dist/TheCharter3000-macOS-arm64.zip`.

### macOS Intel
```bash
chmod +x scripts/build_macos_intel.sh
./scripts/build_macos_intel.sh
```

This creates the shareable package `dist/TheCharter3000-macOS-intel.zip`.

### Windows
```powershell
python -m pip install -r requirements-build.txt
./scripts/build_windows.ps1
```

This creates `dist/TheCharter3000.exe` and `dist/TheCharter3000-Windows.zip`.

## GitHub Releases

Pushing a tag that starts with `v` triggers GitHub Actions to build the Windows, macOS arm64, and macOS Intel artifacts and attach them to a GitHub release.

```bash
git add .
git commit -m "Set up cross-platform app releases"
git push origin <your-branch>
git tag v1.0.0
git push origin v1.0.0
```

The release workflow uploads:
- `TheCharter3000-macOS-arm64.zip`
- `TheCharter3000-macOS-intel.zip`
- `TheCharter3000-Windows.zip`

## Important Signing Note

These builds are unsigned by default.

- macOS users may need to right-click the app and choose `Open` the first time.
- Windows users may see a SmartScreen warning before launch.

If you want to remove those warnings completely, the next step would be Apple code signing/notarization and a Windows code-signing certificate.

## Usage

1. Select the Spinitron CSV export.
2. Enter your KDVS library site username and password.
3. Enter the website search date in `YYYY-MM-DD` or `YYYYMMDD` format.
4. The app logs in and submits the website's advanced album search without Selenium.
5. Choose a match threshold from `0` to `100`.
6. Save the output CSV when prompted.

## Output

The exported CSV includes:
- `Artist`
- `Count`
- `Current Album`
- `Genre`

The full-library exporter includes fields such as:
- `pk`
- `title`
- `artists_joined`
- `artists_count`
- `labels`
- `labels_count`
- `genre`
- `release_date`
- `tracking_end_date`
- `format_name`
- `adder`
