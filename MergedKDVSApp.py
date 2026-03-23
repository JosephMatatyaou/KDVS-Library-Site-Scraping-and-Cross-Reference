import csv
import os
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import pandas as pd
import requests
from rapidfuzz import process
from rapidfuzz.fuzz import ratio


API_BASE_URL = "https://library.kdvs.org/api/library/albums/"


def normalize_name(name):
    if isinstance(name, str):
        name_parts = name.split(", ")
        if len(name_parts) == 2:
            return f"{name_parts[1]} {name_parts[0]}"
        return name.strip()
    return ""


def save_csv(data, file_path):
    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "ID",
                "Album Title",
                "Artist",
                "Date Added",
                "Release Year",
                "Tracked Until",
                "Label",
                "Promoter",
                "Genre",
                "Format",
                "Adder",
            ]
        )
        writer.writerows(data)


def fetch_currents_from_api(tracking_end_date, max_pages=None, progress_callback=None):
    """Fetch albums from KDVS API with tracking end date filter.
    
    Args:
        tracking_end_date: Date filter (YYYY-MM-DD)
        max_pages: Optional limit on number of pages to fetch (None = all)
        progress_callback: Optional function to call with progress updates
    """
    all_data = []
    page = 1
    
    while True:
        try:
            # Filter albums by tracking_end_date__gte (greater than or equal to)
            params = {
                "tracking_end_date__gte": tracking_end_date,
                "ordering": "-created",
                "limit": 100,
                "page": page,
            }
            
            response = requests.get(API_BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for album in data.get("results", []):
                # Format the data to match the original CSV structure
                album_data = [
                    str(album.get("pk", "")),  # ID
                    album.get("title", ""),  # Album Title
                    ", ".join(album.get("artists", [])),  # Artist
                    album.get("created", "").split("T")[0],  # Date Added
                    str(album.get("release_date", "")),  # Release Year
                    album.get("tracking_end_date", ""),  # Tracked Until
                    ", ".join(album.get("labels", [])),  # Label
                    album.get("promoter", ""),  # Promoter
                    album.get("genre", "").strip(),  # Genre
                    album.get("format", ""),  # Format
                    album.get("adder", ""),  # Adder
                ]
                all_data.append(album_data)
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(f"Fetched {len(all_data)} albums (page {page})...")
            
            # Check if there are more pages
            if not data.get("next"):
                break
            
            # Stop if max_pages limit reached
            if max_pages and page >= max_pages:
                break
            
            page += 1
            
        except requests.RequestException as e:
            raise Exception(f"API request failed: {e}")
    
    return all_data


def cross_reference_files_parallel(spinitron_path, currents_data, threshold):
    """Cross reference with parallel processing for efficiency."""
    spinitron_df = pd.read_csv(spinitron_path)
    currents_df = pd.DataFrame(
        currents_data,
        columns=[
            "ID",
            "Album Title",
            "Artist",
            "Date Added",
            "Release Year",
            "Tracked Until",
            "Label",
            "Promoter",
            "Genre",
            "Format",
            "Adder",
        ],
    )

    spinitron_df["Normalized Artist"] = spinitron_df["Artist"].apply(normalize_name)
    currents_df["Normalized Artist"] = currents_df["Artist"].apply(normalize_name)

    matched_rows = []
    
    def process_spinitron_row(sp_row):
        sp_artist = sp_row["Normalized Artist"]
        sp_release = sp_row.get("Release", "")
        sp_count = sp_row.get("Count", "")

        result = process.extractOne(sp_artist, currents_df["Normalized Artist"], scorer=ratio)
        if not result:
            return None

        match, score, idx = result[0], result[1], result[2]
        if score < threshold:
            return None

        current_row = currents_df.iloc[idx]
        current_album = current_row.get("Album Title", "")
        current_genre = current_row.get("Genre", "")

        return {
            "Artist": sp_row["Artist"],
            "Count": sp_count,
            "Current Album": current_album,
            "Genre": current_genre,
        }
    
    # Use parallel processing for faster matching
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_spinitron_row, row) for _, row in spinitron_df.iterrows()]
        for future in as_completed(futures):
            result = future.result()
            if result:
                matched_rows.append(result)

    result_df = pd.DataFrame(matched_rows)
    
    # Aggregate by Artist and Current Album, summing counts
    if len(result_df) > 0:
        result_df["Count"] = pd.to_numeric(result_df["Count"], errors="coerce").fillna(0).astype(int)
        result_df = result_df.groupby(["Artist", "Current Album", "Genre"], as_index=False)["Count"].sum()
        # Sort by Count descending
        result_df = result_df.sort_values("Count", ascending=False).reset_index(drop=True)
    
    return result_df


class MergedKDVSApp:
    """Unified app that scrapes KDVS library and cross-references with Spinitron data in one step."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("The Charter 3000")
        self.root.geometry("950x350")
        self.build_ui()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        # Spinitron File
        ttk.Label(frame, text="Spinitron CSV File:", font=("Arial", 12, "bold")).grid(
            row=0, column=0, padx=8, pady=12, sticky="e"
        )
        self.spinitron_entry = ttk.Entry(frame, width=60)
        self.spinitron_entry.grid(row=0, column=1, padx=8, pady=12, sticky="w")
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file(self.spinitron_entry)).grid(
            row=0, column=2, padx=8, pady=12
        )

        # Tracking End Date
        ttk.Label(frame, text="Tracking End Date (YYYY-MM-DD):", font=("Arial", 12, "bold")).grid(
            row=1, column=0, padx=8, pady=12, sticky="e"
        )
        self.date_entry = ttk.Entry(frame, width=20)
        self.date_entry.grid(row=1, column=1, padx=8, pady=12, sticky="w")
        ttk.Label(frame, text="(Get albums added after this date)", font=("Arial", 12, "italic")).grid(
            row=1, column=1, columnspan=2, padx=8, pady=12, sticky="e"
        )

        # Matching Threshold
        ttk.Label(frame, text="Match Threshold (0-100):", font=("Arial", 12, "bold")).grid(
            row=2, column=0, padx=8, pady=12, sticky="e"
        )
        self.threshold_entry = ttk.Entry(frame, width=10)
        self.threshold_entry.insert(0, "75")
        self.threshold_entry.grid(row=2, column=1, padx=8, pady=12, sticky="w")
        ttk.Label(frame, text="(Artist similarity score)", font=("Arial", 12, "italic")).grid(
            row=2, column=1, columnspan=2, padx=8, pady=12, sticky="e"
        )

        # Info box
        info_text = "This will: \n1. Fetch albums from KDVS library API\n2. Cross-reference with Spinitron data\n3. Save results to CSV"
        ttk.Label(frame, text=info_text, font=("Arial", 14), foreground="black").grid(
            row=3, column=0, columnspan=3, padx=8, pady=16, sticky="w"
        )

        # Start Button
        ttk.Button(frame, text="Start Complete Analysis", command=self.run_complete_workflow).grid(
            row=4, column=0, columnspan=3, pady=24
        )

    def browse_file(self, entry_field):
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")],
            title="Select a CSV file",
        )
        if file_path:
            entry_field.delete(0, tk.END)
            entry_field.insert(0, file_path)

    def run_complete_workflow(self):
        spinitron_path = self.spinitron_entry.get().strip()
        tracking_date = self.date_entry.get().strip()
        threshold_text = self.threshold_entry.get().strip()

        # Validation
        if not spinitron_path:
            messagebox.showerror("Error", "Please select a Spinitron CSV file.")
            return

        if not os.path.exists(spinitron_path):
            messagebox.showerror("Error", "Spinitron file does not exist.")
            return

        if not tracking_date:
            messagebox.showerror("Error", "Please enter a tracking end date (YYYY-MM-DD).")
            return

        try:
            datetime.strptime(tracking_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date must be in YYYY-MM-DD format.")
            return

        try:
            threshold = int(threshold_text)
        except ValueError:
            messagebox.showerror("Error", "Threshold must be a number between 0 and 100.")
            return

        if threshold < 0 or threshold > 100:
            messagebox.showerror("Error", "Threshold must be between 0 and 100.")
            return

        output_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Results CSV",
        )
        if not output_path:
            return

        # Run the workflow
        self.execute_workflow(spinitron_path, tracking_date, threshold, output_path)

    def execute_workflow(self, spinitron_path, tracking_date, threshold, output_path):
        """Execute the complete workflow: fetch from API, cross-reference, and save."""
        try:
            # Show progress
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Processing...")
            progress_window.geometry("400x150")
            progress_frame = ttk.Frame(progress_window, padding=16)
            progress_frame.pack(fill="both", expand=True)

            status_label = ttk.Label(progress_frame, text="Fetching albums from KDVS API...", font=("Arial", 10))
            status_label.pack(pady=10)

            progress_bar = ttk.Progressbar(
                progress_frame, mode="indeterminate", length=300
            )
            progress_bar.pack(pady=10)
            progress_bar.start()

            progress_window.update()

            # Define progress callback to update label
            def update_progress(message):
                status_label.config(text=message)
                progress_window.update()

            # Step 1: Fetch from API (limit to first 10 pages = ~1000 albums for speed)
            currents_data = fetch_currents_from_api(
                tracking_date, 
                max_pages=10,  # Limit to first 1000 albums for reasonable performance
                progress_callback=update_progress
            )
            
            if not currents_data:
                messagebox.showwarning("No Data", f"No albums found with tracking end date on or after {tracking_date}.")
                progress_window.destroy()
                return

            status_label.config(text=f"Fetched {len(currents_data)} albums. Cross-referencing...")
            progress_window.update()

            # Step 2: Cross-reference
            matched_df = cross_reference_files_parallel(spinitron_path, currents_data, threshold)

            # Step 3: Save results
            matched_df.to_csv(output_path, index=False)
            
            progress_window.destroy()

            messagebox.showinfo(
                "Success",
                f"Analysis complete!\n\n"
                f"Fetched: {len(currents_data)} albums\n"
                f"Matched: {len(matched_df)} entries\n"
                f"Saved to: {output_path}",
            )

        except Exception as exc:
            messagebox.showerror("Error", f"Workflow failed:\n{exc}")
            if 'progress_window' in locals():
                progress_window.destroy()


def main():
    root = tk.Tk()
    MergedKDVSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
