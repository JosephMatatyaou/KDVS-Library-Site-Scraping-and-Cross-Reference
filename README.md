# Python Tools for KDVS Data Management

## Background
This repository supports two KDVS workflows:

- scraping the KDVS library site into a CSV backup of current albums
- cross-referencing Spinitron play reports against KDVS currents for charting

Charting became slower after moving to Spinitron because not every logged play comes from a physical KDVS library item. These tools help separate true library plays from outside sources and reduce manual cross-checking.

## Files
- `CurrentScrape.py`: the original standalone scraper GUI
- `ChartCrossReference.py`: the original standalone cross-reference GUI
- `MergedKDVSApp.py`: the newer combined app that includes both workflows in one Tkinter interface

## Recommended Workflow
Run `MergedKDVSApp.py` if you want the current all-in-one experience.

1. Open the scraper tab and log in to the KDVS library site.
2. Scrape currents for a given tracking end date and save the CSV.
3. Move to the cross-reference tab.
4. Pick a Spinitron CSV and either reuse the last scraped currents CSV or choose one manually.
5. Export the matched chart-reference CSV.

## Legacy Standalone Scripts
The original scripts are still included if you want to keep using the split workflow:

### `CurrentScrape.py`
- GUI scraper for KDVS currents
- saves a CSV of album metadata from the library site

### `ChartCrossReference.py`
- matches Spinitron artists against KDVS currents using fuzzy matching
- exports a CSV with matched artist, album, genre, and a highlight flag when releases differ

## Requirements
Install the Python dependencies before running any of the apps:

```bash
pip install pandas rapidfuzz selenium
```

`tkinter` is included with the standard Python installation on most macOS Python builds.

## ChromeDriver
`MergedKDVSApp.py` lets you choose a ChromeDriver binary from the GUI and defaults to:

```text
/Users/josephmatatyaou/Desktop/chromedriver-mac-arm64/chromedriver
```

Update that path in the app or use the browse button if your ChromeDriver lives elsewhere.

## Run
Launch the combined app with:

```bash
python MergedKDVSApp.py
```
