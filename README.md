# Python Tools for KDVS Data Management

## Overview
A cross-platform GUI application that fetches KDVS library albums and cross-references them with Spinitron play reports to separate true library plays from outside sources.

## Installation

### Prerequisites
- Python 3.7+ (macOS, Windows, or Linux)

### Quick Setup

**Mac/Linux:**
```bash
pip install -r requirements.txt
python3 MergedKDVSApp.py
```

**Windows:**
```bash
pip install -r requirements.txt
python MergedKDVSApp.py
```

## Usage

Run `MergedKDVSApp.py`:

1. **Select Spinitron CSV** - Choose your Spinitron play report
2. **Enter Date Filter** (YYYY-MM-DD) - Albums added after this date
3. **Set Match Threshold** - Artist similarity score (0-100, default 75)
4. **Click "Start Complete Analysis"** - The app will:
   - Fetch albums from the KDVS library API (~1,000 albums)
   - Cross-reference against your Spinitron data
   - Save results sorted by play count (highest first)

## Output
A CSV file with:
- **Artist** - From Spinitron
- **Count** - Play count (aggregated for duplicates)
- **Current Album** - Matched KDVS album title
- **Genre** - Album genre

## Files
- `MergedKDVSApp.py` - Main app (all-in-one workflow)
- `requirements.txt` - Python dependencies
- `CurrentScrape.py` - Legacy standalone scraper
- `ChartCrossReference.py` - Legacy standalone cross-reference tool

## Requirements
```
pandas>=1.3.0
requests>=2.28.0
rapidfuzz>=2.0.0
```

(All cross-platform - installs via `pip install -r requirements.txt`)

Update that path in the app or use the browse button if your ChromeDriver lives elsewhere.

## Run
Launch the combined app with:

```bash
python MergedKDVSApp.py
```
