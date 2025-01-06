# Python Tools for KDVS Data Management

## Background/Context
To address two key challenges at KDVS Davis 90.3 FM — creating a backup database of our library website as we transition to a new platform and streamlining our chart reporting process to the NACC charts — I developed code to automate these tasks.

The script scrapes data from our library site, converts it into a CSV, and cross-references it for charting purposes. Charting has been slow since we began using Spinitron as our tracking source, primarily because charting at KDVS involves reporting only tracks that are both physically in our library and played on-air. However, Spinitron also picks up plays from external sources like Spotify and other music platforms, which we don’t include in our reporting.

Previously, this process required manually cross-referencing Spinitron’s tracked plays with our physical library records, a tedious and time-consuming task. Now, with this new automated solution, cross-referencing is entirely streamlined, saving significant time and effort while ensuring accuracy in our chart reporting.
---

## Contents

1. **`CrossReferenceApp.py`**  
   A tool to cross-reference Spinitron weekly plays with KDVS current albums.
2. **`CurrentScrape.py`**  
   A GUI-based scraper for retrieving and organizing KDVS "currents".

---

## 1. CrossReferenceApp.py

### Description
This script takes in two CSV files:
- **Spinitron weekly plays**: A list of tracks and artists played during the week.
- **KDVS current albums**: A catalog of current albums at KDVS.

It outputs a new CSV with the following columns:
- Spinitron Artist
- Spinitron Release
- Play Count
- Matched Artist
- Current Album
- Genre
- Highlight (TRUE if Spinitron release does not match the current album)

### Features
- Uses fuzzy matching to compare artist names for better accuracy.
- Highlights unmatched releases for easier identification.

### Usage
1. Run the script using Python.
2. Upload the Spinitron weekly plays CSV and KDVS current albums CSV when prompted.
3. The script will generate a new CSV with cross-referenced data.

---

## 2. CurrentScrapeFINAL.py

### Description
A scraping tool with a GUI interface that collects data and generates a CSV file of KDVS currents.

### Features
- Allows the user to input a date via a simple GUI.
- Scrapes relevant data from a specified website.
- Outputs the data as a CSV file.

### Usage
1. Run the script using Python.
2. Enter the desired date in the GUI.
3. The script will scrape data and save it as a CSV.

---

## Requirements

### Python Libraries
Both scripts require the following Python libraries:
- `pandas`
- `tkinter`
- `rapidfuzz`
- `selenium`
- `webdriver_manager`

### Additional Requirements
- **ChromeDriver**: Automatically managed by `webdriver_manager`.
- **Google Chrome**: Ensure the latest version is installed.

---

## Running the Scripts

1. **Install Dependencies**:
   ```bash
   pip install pandas tkinter rapidfuzz selenium webdriver-manager
