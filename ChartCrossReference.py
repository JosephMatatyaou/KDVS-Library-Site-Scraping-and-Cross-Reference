#Joseph Matatyaou
#1/1/25
#Code takes in two CSV files, one with spinitron weekly plays and one with KDVS current albums. Code outputs a new CSV file with rows in order:
#Spinitron Artist, Spinitron Release, Play Count, Matched Artist, Current Album, Genre, Highlight (TRUE if spinitron release does not match current album)



import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from rapidfuzz.fuzz import ratio
from rapidfuzz import process

def normalize_name(name):
    if isinstance(name, str):
        name_parts = name.split(", ")
        if len(name_parts) == 2:
            return f"{name_parts[1]} {name_parts[0]}"
        return name.strip()
    return ""

def process_files(spinitron_path, currents_path, threshold):
    try:
        # Load the CSV files
        spinitron_df = pd.read_csv(spinitron_path)
        currents_df = pd.read_csv(currents_path)

        # Normalize artist names
        spinitron_df['Normalized Artist'] = spinitron_df['Artist'].apply(normalize_name)
        currents_df['Normalized Artist'] = currents_df['Artist'].apply(normalize_name)

        # Perform matching
        def find_similar_artists_with_details(spinitron_df, currents_df, threshold):
            matched_rows = []
            for sp_index, sp_row in spinitron_df.iterrows():
                sp_artist = sp_row['Normalized Artist']
                sp_release = sp_row.get('Release', '')
                sp_count = sp_row.get('Count', '')

                result = process.extractOne(sp_artist, currents_df['Normalized Artist'], scorer=ratio)
                if result:
                    match, score, idx = result[0], result[1], result[2]
                    if score >= threshold:
                        current_row = currents_df.iloc[idx]
                        current_album = current_row.get('Album Title', '')
                        current_genre = current_row.get('Genre', '')

                        highlight = sp_release != current_album
                        matched_rows.append({
                            'Spinitron Artist': sp_row['Artist'],
                            'Spinitron Release': sp_release,
                            'Count': sp_count,
                            'Matched Artist': match,
                            'Current Album': current_album,
                            'Genre': current_genre,
                            'Highlight': highlight
                        })
            return matched_rows

        fuzzy_matches = find_similar_artists_with_details(spinitron_df, currents_df, threshold)

        # Save output
        matched_df = pd.DataFrame(fuzzy_matches)
        output_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Referenced CSV"
        )
        if output_path:
            matched_df.to_csv(output_path, index=False)
            messagebox.showinfo("Success", f"Results saved to: {output_path}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

def browse_file(entry_field):
    file_path = filedialog.askopenfilename(
        filetypes=[("CSV files", "*.csv")],
        title="Select a CSV file"
    )
    entry_field.delete(0, tk.END)
    entry_field.insert(0, file_path)

# GUI Setup
root = tk.Tk()
root.title("CSV Referencing App")

# File inputs
tk.Label(root, text="Spinitron CSV File:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
spinitron_entry = tk.Entry(root, width=50)
spinitron_entry.grid(row=0, column=1, padx=10, pady=5)
tk.Button(root, text="Browse", command=lambda: browse_file(spinitron_entry)).grid(row=0, column=2, padx=10, pady=5)

tk.Label(root, text="Currents CSV File:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
currents_entry = tk.Entry(root, width=50)
currents_entry.grid(row=1, column=1, padx=10, pady=5)
tk.Button(root, text="Browse", command=lambda: browse_file(currents_entry)).grid(row=1, column=2, padx=10, pady=5)

# Threshold input
tk.Label(root, text="Threshold (Represents percent similarity between spinitron artist and artist in \n KDVS current library to account for typos and misorders (Input 0-100))").grid(row=2, column=0, padx=10, pady=5, sticky="e")
threshold_entry = tk.Entry(root, width=10)
threshold_entry.insert(0, "75")  # Default threshold value
threshold_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")

# Process Button
tk.Button(
    root,
    text="Process Files",
    command=lambda: process_files(
        spinitron_entry.get(),
        currents_entry.get(),
        int(threshold_entry.get())
    )
).grid(row=3, column=0, columnspan=3, pady=20)

root.mainloop()
