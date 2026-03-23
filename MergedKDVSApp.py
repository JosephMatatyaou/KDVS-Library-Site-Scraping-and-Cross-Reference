import os
import re
import tkinter as tk
from datetime import date, datetime
from html import unescape
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urljoin

import pandas as pd
import requests
from rapidfuzz import process
from rapidfuzz.fuzz import ratio


BASE_URL = "https://library.kdvs.org"
LOGIN_URL = f"{BASE_URL}/login/?next=/"
LOGIN_POST_URL = f"{BASE_URL}/login/"
ALBUMS_URL = f"{BASE_URL}/library/albums/"

CURRENT_COLUMNS = [
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

FINAL_COLUMNS = ["Artist", "Count", "Current Album", "Genre"]

ADVANCED_SEARCH_DEFAULTS = {
    "advanced_album_search": "True",
    "title": "",
    "id": "",
    "artists": "",
    "genre": "",
    "labels": "",
    "release_date_option": "none",
    "release_date": "",
    "add_date_option": "none",
    "add_date": "",
    "tracking_end_date_option": "after",
    "promoter": "",
    "format": "",
    "adder": "",
    "action_advanced_album_search": "",
}


def normalize_text(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().strip().split())


def normalize_name(name):
    if not isinstance(name, str):
        return ""

    cleaned_name = " ".join(name.strip().split())
    if not cleaned_name:
        return ""

    if ", " in cleaned_name:
        name_parts = cleaned_name.split(", ")
        if len(name_parts) == 2 and name_parts[0] and name_parts[1]:
            cleaned_name = f"{name_parts[1]} {name_parts[0]}"

    return normalize_text(cleaned_name)


def html_to_text(value):
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(without_tags).split())


def find_column(df, candidates, required=True):
    normalized_columns = {normalize_text(column): column for column in df.columns}
    for candidate in candidates:
        match = normalized_columns.get(normalize_text(candidate))
        if match:
            return match

    if required:
        candidate_list = ", ".join(candidates)
        raise ValueError(f"CSV is missing a required column. Expected one of: {candidate_list}")

    return None


def extract_csrf_token(html):
    patterns = [
        r"name='csrfmiddlewaretoken' value='([^']+)'",
        r'name="csrfmiddlewaretoken" value="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    raise RuntimeError("Could not find the KDVS login CSRF token.")


def normalize_website_date_input(value):
    cleaned_value = value.strip()
    candidate_formats = ("%Y-%m-%d", "%Y%m%d")

    for candidate_format in candidate_formats:
        try:
            parsed_date = datetime.strptime(cleaned_value, candidate_format).date()
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError("Website search date must be in YYYY-MM-DD or YYYYMMDD format.")


def login_to_kdvs(session, username, password):
    login_page = session.get(LOGIN_URL, timeout=30)
    login_page.raise_for_status()
    csrf_token = extract_csrf_token(login_page.text)

    response = session.post(
        LOGIN_POST_URL,
        data={
            "csrfmiddlewaretoken": csrf_token,
            "username": username,
            "password": password,
            "next": "/",
        },
        headers={"Referer": LOGIN_URL},
        timeout=30,
    )
    response.raise_for_status()

    albums_page = session.get(ALBUMS_URL, timeout=30)
    albums_page.raise_for_status()

    if "Logout" not in albums_page.text and "/logout" not in albums_page.text:
        raise RuntimeError("KDVS login failed. Please check your username and password.")


def build_advanced_search_params(tracking_end_date):
    params = dict(ADVANCED_SEARCH_DEFAULTS)
    params["tracking_end_date"] = tracking_end_date
    return params


def extract_table_rows(html):
    table_match = re.search(r"<table[^>]*>(.*?)</table>", html, re.S | re.I)
    if not table_match:
        return []

    table_html = table_match.group(1)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S | re.I)
    scraped_rows = []

    for row_html in rows[1:]:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)
        if len(cells) < 11:
            continue

        scraped_rows.append([html_to_text(cell) for cell in cells[:11]])

    return scraped_rows


def extract_next_page_url(current_url, html):
    next_match = re.search(
        r"<li[^>]*class=['\"][^'\"]*next[^'\"]*['\"][^>]*>\s*<a href=['\"]([^'\"]+)['\"]>\s*(?:<span[^>]*>&raquo;</span>|&raquo;)",
        html,
        re.S | re.I,
    )
    if not next_match:
        return None

    return urljoin(current_url, unescape(next_match.group(1)))


def fetch_currents_from_site(username, password, tracking_end_date, progress_callback=None):
    """Use a logged-in requests session to submit the real website advanced search."""
    scraped_data = []
    seen_ids = set()

    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        if progress_callback:
            progress_callback("Logging into the KDVS site...")

        login_to_kdvs(session, username, password)

        search_url = ALBUMS_URL
        search_params = build_advanced_search_params(tracking_end_date)
        page_number = 1

        while search_url:
            response = session.get(
                search_url,
                params=search_params if page_number == 1 else None,
                timeout=60,
            )
            response.raise_for_status()

            if "Server Error (500)" in response.text:
                raise RuntimeError(
                    "KDVS website search failed. The advanced search request was rejected by the site."
                )

            page_rows = extract_table_rows(response.text)
            for row in page_rows:
                album_id = row[0]
                if not album_id or album_id in seen_ids:
                    continue

                seen_ids.add(album_id)
                scraped_data.append(row)

            if progress_callback:
                progress_callback(
                    f"Scraped {len(scraped_data)} KDVS albums from website search (page {page_number})..."
                )

            search_url = extract_next_page_url(response.url, response.text)
            search_params = None
            page_number += 1

    return scraped_data


def cross_reference_files(spinitron_path, currents_data, threshold):
    spinitron_df = pd.read_csv(spinitron_path)
    if spinitron_df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    artist_column = find_column(spinitron_df, ["Artist", "Artists"])
    count_column = find_column(
        spinitron_df,
        ["Count", "Plays", "Play Count", "Spin Count", "Spins"],
    )

    currents_df = pd.DataFrame(currents_data, columns=CURRENT_COLUMNS)
    if currents_df.empty:
        return pd.DataFrame(columns=FINAL_COLUMNS)

    spinitron_df["Normalized Artist"] = spinitron_df[artist_column].apply(normalize_name)
    currents_df["Normalized Artist"] = currents_df["Artist"].apply(normalize_name)

    current_artists = currents_df["Normalized Artist"].tolist()
    matched_rows = []

    for _, sp_row in spinitron_df.iterrows():
        normalized_artist = sp_row["Normalized Artist"]
        if not normalized_artist:
            continue

        result = process.extractOne(normalized_artist, current_artists, scorer=ratio)
        if not result:
            continue

        _, score, idx = result
        if score < threshold:
            continue

        current_row = currents_df.iloc[idx]
        matched_rows.append(
            {
                "Artist": sp_row[artist_column],
                "Count": sp_row[count_column],
                "Current Album": current_row["Album Title"],
                "Genre": current_row["Genre"],
            }
        )

    matched_df = pd.DataFrame(matched_rows, columns=FINAL_COLUMNS)
    if matched_df.empty:
        return matched_df

    matched_df["Count"] = pd.to_numeric(matched_df["Count"], errors="coerce").fillna(0)
    matched_df = (
        matched_df.groupby(["Artist", "Current Album", "Genre"], as_index=False)["Count"]
        .sum()
        .sort_values(["Count", "Artist", "Current Album"], ascending=[False, True, True], kind="stable")
        .reset_index(drop=True)
    )
    matched_df["Count"] = matched_df["Count"].astype(int)

    return matched_df[FINAL_COLUMNS]


class MergedKDVSApp:
    """Run the KDVS website advanced search via requests and cross-reference with Spinitron."""

    def __init__(self, root):
        self.root = root
        self.root.title("The Charter 3000")
        self.build_ui()
        self.root.update_idletasks()
        self.root.geometry(f"{self.root.winfo_reqwidth()}x{self.root.winfo_reqheight()}")
        self.root.resizable(False, False)

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Spinitron CSV File:", font=("Arial", 12, "bold")).grid(
            row=0, column=0, padx=8, pady=10, sticky="e"
        )
        self.spinitron_entry = ttk.Entry(frame, width=64)
        self.spinitron_entry.grid(row=0, column=1, padx=8, pady=10, sticky="w")
        ttk.Button(
            frame,
            text="Browse",
            command=lambda: self.browse_file(self.spinitron_entry),
        ).grid(row=0, column=2, padx=8, pady=10)

        ttk.Label(frame, text="KDVS Username:", font=("Arial", 12, "bold")).grid(
            row=1, column=0, padx=8, pady=10, sticky="e"
        )
        self.username_entry = ttk.Entry(frame, width=32)
        self.username_entry.grid(row=1, column=1, padx=8, pady=10, sticky="w")

        ttk.Label(frame, text="KDVS Password:", font=("Arial", 12, "bold")).grid(
            row=2, column=0, padx=8, pady=10, sticky="e"
        )
        self.password_entry = ttk.Entry(frame, width=32, show="*")
        self.password_entry.grid(row=2, column=1, padx=8, pady=10, sticky="w")

        today = date.today()
        website_date = today.strftime("%Y-%m-%d")
        ttk.Label(frame, text="Website Search Date:", font=("Arial", 12, "bold")).grid(
            row=3, column=0, padx=8, pady=10, sticky="e"
        )
        self.website_date_entry = ttk.Entry(frame, width=18)
        self.website_date_entry.insert(0, website_date)
        self.website_date_entry.grid(row=3, column=1, padx=8, pady=10, sticky="w")
        ttk.Label(
            frame,
            text="(YYYY-MM-DD or YYYYMMDD)",
            font=("Arial", 12, "italic"),
        ).grid(row=3, column=1, columnspan=2, padx=8, pady=10, sticky="e")

        ttk.Label(frame, text="Match Threshold (0-100):", font=("Arial", 12, "bold")).grid(
            row=4, column=0, padx=8, pady=10, sticky="e"
        )
        self.threshold_entry = ttk.Entry(frame, width=10)
        self.threshold_entry.insert(0, "75")
        self.threshold_entry.grid(row=4, column=1, padx=8, pady=10, sticky="w")
        ttk.Label(frame, text="(Artist similarity score)", font=("Arial", 12, "italic")).grid(
            row=4, column=1, columnspan=2, padx=8, pady=10, sticky="e"
        )

        ttk.Button(frame, text="Start Complete Analysis", command=self.run_complete_workflow).grid(
            row=6, column=0, columnspan=3, pady=10
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
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        website_date_input = self.website_date_entry.get().strip()
        threshold_text = self.threshold_entry.get().strip()

        if not spinitron_path:
            messagebox.showerror("Error", "Please select a Spinitron CSV file.")
            return

        if not os.path.exists(spinitron_path):
            messagebox.showerror("Error", "Spinitron file does not exist.")
            return

        if not username or not password:
            messagebox.showerror("Error", "Please enter your KDVS username and password.")
            return

        try:
            website_date = normalize_website_date_input(website_date_input)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
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
            initialfile=f"KDVS_Final_{date.today().strftime('%Y%m%d')}.csv",
            title="Save Results CSV",
        )
        if not output_path:
            return

        self.execute_workflow(spinitron_path, username, password, website_date, threshold, output_path)

    def execute_workflow(self, spinitron_path, username, password, website_date, threshold, output_path):
        progress_window = None

        try:
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Processing...")
            progress_window.geometry("200x150")
            progress_frame = ttk.Frame(progress_window, padding=16)
            progress_frame.pack(fill="both", expand=True)

            status_label = ttk.Label(
                progress_frame,
                text=f"Submitting KDVS website advanced search with tracking end date after {website_date}...",
                font=("Arial", 10),
                wraplength=420,
            )
            status_label.pack(pady=10)

            progress_bar = ttk.Progressbar(progress_frame, mode="indeterminate", length=340)
            progress_bar.pack(pady=10)
            progress_bar.start()

            progress_window.update()

            def update_progress(message):
                status_label.config(text=message)
                progress_window.update()

            currents_data = fetch_currents_from_site(
                username,
                password,
                website_date,
                progress_callback=update_progress,
            )

            if not currents_data:
                progress_window.destroy()
                progress_window = None
                messagebox.showwarning(
                    "No Data",
                    f"No KDVS albums were found with tracking end date after {website_date}.",
                )
                return

            status_label.config(text=f"Scraped {len(currents_data)} KDVS albums. Cross-referencing...")
            progress_window.update()

            matched_df = cross_reference_files(spinitron_path, currents_data, threshold)
            matched_df.to_csv(output_path, index=False)

            progress_window.destroy()
            progress_window = None

            messagebox.showinfo(
                "Success",
                "Analysis complete.\n\n"
                f"KDVS albums scraped: {len(currents_data)}\n"
                f"Final CSV rows: {len(matched_df)}\n"
                f"Saved to: {output_path}",
            )

        except Exception as exc:
            if progress_window is not None:
                progress_window.destroy()
            messagebox.showerror("Error", f"Workflow failed:\n{exc}")


def main():
    root = tk.Tk()
    MergedKDVSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
