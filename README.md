# Python Tools for KDVS Data Management

This repository contains two Python scripts designed to streamline data management and analysis for KDVS. 
These tools help cross-reference plays on air with what we physically have and scrape data efficiently.

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
