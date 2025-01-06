#Joseph Matatyaou
#Script pops up gui and asks for current date and outputs csv of all currents

import sys
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

#Package/Import ChromeDriver
if hasattr(sys, "_MEIPASS"):
    driver_path = os.path.join(sys._MEIPASS, "chromedriver")
else:
    driver_path = os.path.join(os.getcwd(), "chromedriver")

# Function to run the scraping process
def start_scraping():
    desired_date = date_entry.get()
    username = username_entry.get()
    password = password_entry.get()

    if not desired_date or not username or not password:
        messagebox.showerror("Error", "Please fill in all the fields!")
        return

    try: #login to KDVS library site and input advanced search
        driver_path = "/Users/josephmatatyaou/Desktop/chromedriver-mac-arm64/chromedriver"  # Update with your path
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)

        driver.get("https://library.kdvs.org/login/?next=/")
        time.sleep(2)

        username_field = driver.find_element(By.ID, "id_username")
        password_field = driver.find_element(By.ID, "id_password")
        username_field.send_keys(username)
        password_field.send_keys(password)

        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        time.sleep(3)

        view_albums_button = driver.find_element(By.XPATH, "//a[@class='btn btn-default' and @href='/library/albums/']")
        view_albums_button.click()
        time.sleep(3)

        advanced_search_button = driver.find_element(By.XPATH, "//a[@href='#' and @data-toggle='modal' and @data-target='#advanced-search-modal']")
        advanced_search_button.click()
        time.sleep(2)

        dropdown = Select(driver.find_element(By.ID, "id_tracking_end_date_option"))
        dropdown.select_by_value("after")

        tracking_end_date_field = driver.find_element(By.ID, "id_tracking_end_date")
        tracking_end_date_field.clear()
        tracking_end_date_field.send_keys(desired_date)

        search_button = driver.find_element(By.NAME, "action_advanced_album_search")
        search_button.click()
        time.sleep(3)

        # Scraping logic
        scraped_data = []
        page_number = 1

        while True:
            table = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div/table"))
            )
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header

            for row in rows:
                columns = row.find_elements(By.TAG_NAME, "td")
                if len(columns) > 0:
                    ID = columns[0].text
                    album_title = columns[1].text
                    artist = columns[2].text 
                    date_added = columns[3].text
                    release_date = columns[4].text
                    tracked_until = columns[5].text  
                    label = columns[6].text
                    promoter = columns[7].text
                    genre = columns[8].text
                    Format = columns[9].text
                    adder = columns[10].text
                    scraped_data.append([ID, album_title, artist, date_added, release_date, tracked_until, label, promoter, genre, Format, adder])

            try:
                next_page_xpath = (
                    "/html/body/div/ul/li[3]/a" if page_number == 1 else "/html/body/div/ul/li[5]/a"
                )
                next_page_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, next_page_xpath))
                )
                next_page_button.click()
                page_number += 1
            except Exception:
                break

        driver.quit()

        # After scraping, ask where to save the CSV file
        save_file(scraped_data)

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

# Function to save the file
def save_file(data):
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        title="Save CSV File"
    )
    if not file_path:
        messagebox.showinfo("Cancelled", "File saving was cancelled.")
        return

    try:
        with open(file_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Album Title", "Artist", "Date Added", "Release Year", "Tracked Until", "Label", "Promoter", "Genre", "Format", "Adder"])
            writer.writerows(data)
        messagebox.showinfo("Success", f"Data has been saved to {file_path}!")
    except Exception as e:
        messagebox.showerror("Error", f"Could not save file: {e}")

# GUI setup
root = tk.Tk()
root.title("Scraping Tool")

tk.Label(root, text="Enter Date (MMDDYYYY):").grid(row=0, column=0, padx=10, pady=10)
date_entry = tk.Entry(root)
date_entry.grid(row=0, column=1, padx=10, pady=10)

tk.Label(root, text="KDVS Library Site Username:").grid(row=1, column=0, padx=10, pady=10)
username_entry = tk.Entry(root)
username_entry.grid(row=1, column=1, padx=10, pady=10)

tk.Label(root, text="KDVS Library Site Password:").grid(row=2, column=0, padx=10, pady=10)
password_entry = tk.Entry(root, show="*")
password_entry.grid(row=2, column=1, padx=10, pady=10)

start_button = tk.Button(root, text="Start Scraping", command=start_scraping)
start_button.grid(row=3, column=0, columnspan=2, pady=20)

root.mainloop()
