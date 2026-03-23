import csv
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from rapidfuzz import process
from rapidfuzz.fuzz import ratio
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


DEFAULT_CHROMEDRIVER_PATH = "/Users/josephmatatyaou/Desktop/chromedriver-mac-arm64/chromedriver"
LOGIN_URL = "https://library.kdvs.org/login/?next=/"
ALBUMS_URL = "/library/albums/"


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


def build_driver(driver_path):
    if driver_path:
        service = Service(driver_path)
        return webdriver.Chrome(service=service)
    return webdriver.Chrome()


def scrape_currents(desired_date, username, password, driver_path):
    driver = build_driver(driver_path)
    scraped_data = []
    page_number = 1

    try:
        driver.get(LOGIN_URL)
        time.sleep(2)

        driver.find_element(By.ID, "id_username").send_keys(username)
        driver.find_element(By.ID, "id_password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        driver.find_element(
            By.XPATH,
            f"//a[@class='btn btn-default' and @href='{ALBUMS_URL}']",
        ).click()
        time.sleep(3)

        driver.find_element(
            By.XPATH,
            "//a[@href='#' and @data-toggle='modal' and @data-target='#advanced-search-modal']",
        ).click()
        time.sleep(2)

        Select(driver.find_element(By.ID, "id_tracking_end_date_option")).select_by_value("after")
        tracking_end_date_field = driver.find_element(By.ID, "id_tracking_end_date")
        tracking_end_date_field.clear()
        tracking_end_date_field.send_keys(desired_date)

        driver.find_element(By.NAME, "action_advanced_album_search").click()
        time.sleep(3)

        while True:
            table = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div/table"))
            )
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]

            for row in rows:
                columns = row.find_elements(By.TAG_NAME, "td")
                if len(columns) >= 11:
                    scraped_data.append(
                        [
                            columns[0].text,
                            columns[1].text,
                            columns[2].text,
                            columns[3].text,
                            columns[4].text,
                            columns[5].text,
                            columns[6].text,
                            columns[7].text,
                            columns[8].text,
                            columns[9].text,
                            columns[10].text,
                        ]
                    )

            next_page_xpath = "/html/body/div/ul/li[3]/a" if page_number == 1 else "/html/body/div/ul/li[5]/a"
            try:
                next_page_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, next_page_xpath))
                )
                next_page_button.click()
                page_number += 1
                time.sleep(2)
            except TimeoutException:
                break

        return scraped_data
    finally:
        driver.quit()


def cross_reference_files(spinitron_path, currents_path, threshold):
    spinitron_df = pd.read_csv(spinitron_path)
    currents_df = pd.read_csv(currents_path)

    spinitron_df["Normalized Artist"] = spinitron_df["Artist"].apply(normalize_name)
    currents_df["Normalized Artist"] = currents_df["Artist"].apply(normalize_name)

    matched_rows = []
    for _, sp_row in spinitron_df.iterrows():
        sp_artist = sp_row["Normalized Artist"]
        sp_release = sp_row.get("Release", "")
        sp_count = sp_row.get("Count", "")

        result = process.extractOne(sp_artist, currents_df["Normalized Artist"], scorer=ratio)
        if not result:
            continue

        match, score, idx = result[0], result[1], result[2]
        if score < threshold:
            continue

        current_row = currents_df.iloc[idx]
        current_album = current_row.get("Album Title", "")
        current_genre = current_row.get("Genre", "")

        matched_rows.append(
            {
                "Spinitron Artist": sp_row["Artist"],
                "Spinitron Release": sp_release,
                "Count": sp_count,
                "Matched Artist": match,
                "Current Album": current_album,
                "Genre": current_genre,
                "Highlight": sp_release != current_album,
            }
        )

    return pd.DataFrame(matched_rows)


class MergedKDVSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KDVS Currents + Cross Reference")
        self.last_currents_csv_path = ""

        self.build_ui()

    def build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        scrape_frame = ttk.Frame(notebook, padding=12)
        reference_frame = ttk.Frame(notebook, padding=12)

        notebook.add(scrape_frame, text="Scrape Currents")
        notebook.add(reference_frame, text="Cross Reference")

        self.build_scrape_tab(scrape_frame)
        self.build_reference_tab(reference_frame)

    def build_scrape_tab(self, parent):
        ttk.Label(parent, text="Enter Date (MMDDYYYY):").grid(row=0, column=0, padx=8, pady=8, sticky="e")
        self.date_entry = ttk.Entry(parent, width=24)
        self.date_entry.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        ttk.Label(parent, text="KDVS Library Username:").grid(row=1, column=0, padx=8, pady=8, sticky="e")
        self.username_entry = ttk.Entry(parent, width=40)
        self.username_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")

        ttk.Label(parent, text="KDVS Library Password:").grid(row=2, column=0, padx=8, pady=8, sticky="e")
        self.password_entry = ttk.Entry(parent, width=40, show="*")
        self.password_entry.grid(row=2, column=1, padx=8, pady=8, sticky="w")

        ttk.Label(parent, text="ChromeDriver Path:").grid(row=3, column=0, padx=8, pady=8, sticky="e")
        self.driver_entry = ttk.Entry(parent, width=60)
        self.driver_entry.insert(0, DEFAULT_CHROMEDRIVER_PATH)
        self.driver_entry.grid(row=3, column=1, padx=8, pady=8, sticky="w")
        ttk.Button(parent, text="Browse", command=self.browse_driver).grid(row=3, column=2, padx=8, pady=8)

        ttk.Button(parent, text="Scrape Currents CSV", command=self.run_scrape).grid(
            row=4, column=0, columnspan=3, pady=16
        )

    def build_reference_tab(self, parent):
        ttk.Label(parent, text="Spinitron CSV File:").grid(row=0, column=0, padx=8, pady=8, sticky="e")
        self.spinitron_entry = ttk.Entry(parent, width=60)
        self.spinitron_entry.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        ttk.Button(parent, text="Browse", command=lambda: self.browse_file(self.spinitron_entry)).grid(
            row=0, column=2, padx=8, pady=8
        )

        ttk.Label(parent, text="Currents CSV File:").grid(row=1, column=0, padx=8, pady=8, sticky="e")
        self.currents_entry = ttk.Entry(parent, width=60)
        self.currents_entry.grid(row=1, column=1, padx=8, pady=8, sticky="w")
        ttk.Button(parent, text="Browse", command=lambda: self.browse_file(self.currents_entry)).grid(
            row=1, column=2, padx=8, pady=8
        )

        ttk.Button(parent, text="Use Last Scraped CSV", command=self.use_last_scraped_csv).grid(
            row=2, column=1, padx=8, pady=4, sticky="w"
        )

        ttk.Label(
            parent,
            text="Threshold (0-100 similarity for artist matching):",
        ).grid(row=3, column=0, padx=8, pady=8, sticky="e")
        self.threshold_entry = ttk.Entry(parent, width=10)
        self.threshold_entry.insert(0, "75")
        self.threshold_entry.grid(row=3, column=1, padx=8, pady=8, sticky="w")

        ttk.Button(parent, text="Cross Reference CSVs", command=self.run_cross_reference).grid(
            row=4, column=0, columnspan=3, pady=16
        )

    def browse_file(self, entry_field):
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")],
            title="Select a CSV file",
        )
        if file_path:
            entry_field.delete(0, tk.END)
            entry_field.insert(0, file_path)

    def browse_driver(self):
        file_path = filedialog.askopenfilename(title="Select ChromeDriver")
        if file_path:
            self.driver_entry.delete(0, tk.END)
            self.driver_entry.insert(0, file_path)

    def use_last_scraped_csv(self):
        if not self.last_currents_csv_path:
            messagebox.showinfo("No File Yet", "Scrape and save a currents CSV first.")
            return

        self.currents_entry.delete(0, tk.END)
        self.currents_entry.insert(0, self.last_currents_csv_path)

    def run_scrape(self):
        desired_date = self.date_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        driver_path = self.driver_entry.get().strip()

        if not desired_date or not username or not password:
            messagebox.showerror("Error", "Please fill in the date, username, and password.")
            return

        if driver_path and not os.path.exists(driver_path):
            messagebox.showerror("Error", "The ChromeDriver path does not exist.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Currents CSV",
        )
        if not save_path:
            return

        try:
            data = scrape_currents(desired_date, username, password, driver_path)
            save_csv(data, save_path)
            self.last_currents_csv_path = save_path
            self.currents_entry.delete(0, tk.END)
            self.currents_entry.insert(0, save_path)
            messagebox.showinfo("Success", f"Scraped {len(data)} rows and saved to:\n{save_path}")
        except Exception as exc:
            messagebox.showerror("Error", f"Scraping failed:\n{exc}")

    def run_cross_reference(self):
        spinitron_path = self.spinitron_entry.get().strip()
        currents_path = self.currents_entry.get().strip()
        threshold_text = self.threshold_entry.get().strip()

        if not spinitron_path or not currents_path:
            messagebox.showerror("Error", "Please choose both the Spinitron and currents CSV files.")
            return

        try:
            threshold = int(threshold_text)
        except ValueError:
            messagebox.showerror("Error", "Threshold must be a whole number between 0 and 100.")
            return

        if threshold < 0 or threshold > 100:
            messagebox.showerror("Error", "Threshold must be between 0 and 100.")
            return

        output_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Cross Referenced CSV",
        )
        if not output_path:
            return

        try:
            matched_df = cross_reference_files(spinitron_path, currents_path, threshold)
            matched_df.to_csv(output_path, index=False)
            messagebox.showinfo("Success", f"Saved {len(matched_df)} matched rows to:\n{output_path}")
        except Exception as exc:
            messagebox.showerror("Error", f"Cross reference failed:\n{exc}")


def main():
    root = tk.Tk()
    MergedKDVSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
