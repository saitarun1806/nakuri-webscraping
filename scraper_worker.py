"""
Naukri.com Job Scraper — All India (state-by-state, parallel)
Scrapes full job details including description, company info, ratings, etc.
"""

import multiprocessing
import csv
import time
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------- CONFIG ----------------

# ---------------- CONFIG ----------------

STATES = [
    "andhra-pradesh", "arunachal-pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal-pradesh", "jharkhand",
    "karnataka", "kerala", "madhya-pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "punjab",
    "rajasthan", "sikkim", "tamil-nadu", "telangana", "tripura",
    "uttar-pradesh", "uttarakhand", "west-bengal",
    "delhi-ncr", "jammu-kashmir", "ladakh", "chandigarh",
    "puducherry",
]

MAX_PAGES_PER_STATE = 10        # capped as requested
TEMP_DIR = "state_csvs"
MAX_PARALLEL_WORKERS = 10        # safe for GitHub's 2-core/7GB runners
FINAL_OUTPUT = "naukri_jobs_all_india.csv"


# ---------------- HELPERS ----------------

def log(state, message):
    """Prefixed, immediately-flushed print so logs appear live, not in batches."""
    print(f"[{state}] {message}", flush=True)


def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def get_search_page_url(location, page):
    if page == 1:
        return f"https://www.naukri.com/jobs-in-{location}"
    return f"https://www.naukri.com/jobs-in-{location}-{page}"


def safe_text(el, by, value, default="N/A"):
    try:
        return el.find_element(by, value).text.strip()
    except Exception:
        return default


def safe_attr(el, by, value, attr, default="N/A"):
    try:
        return el.find_element(by, value).get_attribute(attr)
    except Exception:
        return default


def extract_labeled_field(full_text, label):
    pattern = rf"{re.escape(label)}\s*[:\-]\s*(.+)"
    match = re.search(pattern, full_text)
    return match.group(1).split("\n")[0].strip() if match else "N/A"


# ---------------- JOB DETAIL SCRAPER ----------------

def scrape_job_detail(driver, job_url, state):
    driver.get(job_url)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.2)
    except Exception:
        pass

    body_text = driver.find_element(By.TAG_NAME, "body").text
    title = safe_text(driver, By.TAG_NAME, "h1")

    company = "N/A"
    lines = body_text.split("\n")
    if title in lines:
        idx = lines.index(title)
        if idx + 1 < len(lines):
            company = lines[idx + 1].strip()

    exp_match = re.search(r"(\d+(\.\d+)?\s*-\s*\d+(\.\d+)?\s*years|\d+\s*years)", body_text, re.IGNORECASE)
    experience = exp_match.group(0) if exp_match else "N/A"

    salary_match = re.search(r"([\d,.]+\s*(Lacs|Lakh|Cr)?\s*P\.?A\.?|Not disclosed)", body_text, re.IGNORECASE)
    salary = salary_match.group(0) if salary_match else "N/A"

    rating_match = re.search(r"\n(\d\.\d)\n", body_text)
    rating = rating_match.group(1) if rating_match else "N/A"

    reviews_match = re.search(r"(\d[\d,]*)\s*Reviews", body_text)
    reviews_count = reviews_match.group(1) if reviews_match else "N/A"

    openings_match = re.search(r"Openings:\s*(\d+)", body_text)
    openings = openings_match.group(1) if openings_match else "N/A"

    applicants_match = re.search(r"Applicants:\s*(.+)", body_text)
    applicants = applicants_match.group(1).split("\n")[0].strip() if applicants_match else "N/A"

    posted_match = re.search(r"Posted:\s*(.+)", body_text)
    posted = posted_match.group(1).split("\n")[0].strip() if posted_match else "N/A"

    role = extract_labeled_field(body_text, "Role")
    industry = extract_labeled_field(body_text, "Industry Type")
    department = extract_labeled_field(body_text, "Department")
    employment_type = extract_labeled_field(body_text, "Employment Type")
    role_category = extract_labeled_field(body_text, "Role Category")
    education = extract_labeled_field(body_text, "UG")

    desc = "N/A"
    desc_match = re.search(r"Job description\s*\n(.+?)(?:\nRole:|\Z)", body_text, re.DOTALL)
    if desc_match:
        desc = desc_match.group(1).strip()

    skills = "N/A"
    skills_match = re.search(r"Key Skills\s*\n(.+?)(?:\n\n|\Z)", body_text, re.DOTALL)
    if skills_match:
        skills = skills_match.group(1).replace("\n", ", ").strip()

    about_company = "N/A"
    about_match = re.search(r"About company\s*\n(.+?)(?:\nCompany Info|\nAddress:|\Z)", body_text, re.DOTALL)
    if about_match:
        about_company = about_match.group(1).strip()

    address = "N/A"
    address_match = re.search(r"Address:\s*(.+)", body_text)
    if address_match:
        address = address_match.group(1).split("\n")[0].strip()

    log(state, f"    -> parsed: '{title[:60]}' @ {company} (rating: {rating})")

    return {
        "JobLink": job_url,
        "Title": title,
        "Company": company,
        "CompanyRating": rating,
        "CompanyReviewsCount": reviews_count,
        "Experience": experience,
        "Salary": salary,
        "PostedDate": posted,
        "Openings": openings,
        "Applicants": applicants,
        "Role": role,
        "IndustryType": industry,
        "Department": department,
        "EmploymentType": employment_type,
        "RoleCategory": role_category,
        "Education": education,
        "Skills": skills,
        "Description": desc,
        "AboutCompany": about_company,
        "CompanyAddress": address,
    }


# ---------------- STATE-LEVEL SCRAPER ----------------

def scrape_state(state):
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_file = os.path.join(TEMP_DIR, f"{state}.csv")

    log(state, "Launching browser...")
    driver = make_driver()
    csv_file = None
    writer = None
    total_saved = 0

    try:
        for page in range(1, MAX_PAGES_PER_STATE + 1):
            url = get_search_page_url(state, page)
            log(state, f"Loading page {page}: {url}")
            driver.get(url)

            wait = WebDriverWait(driver, 15)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cust-job-tuple")))
            except Exception:
                log(state, f"No job cards at page {page} — stopping this state.")
                break

            if page > 1 and driver.current_url.rstrip("/").endswith(f"jobs-in-{state}"):
                log(state, f"Redirected to page 1 — pagination cap hit at page {page}.")
                break

            cards = driver.find_elements(By.CSS_SELECTOR, "div.cust-job-tuple")
            links = [safe_attr(c, By.CLASS_NAME, "title", "href") for c in cards]
            links = [l for l in links if l != "N/A"]
            log(state, f"  Found {len(links)} job links on page {page}")

            for i, link in enumerate(links, 1):
                log(state, f"  [{i}/{len(links)}] Fetching: {link}")
                try:
                    job_data = scrape_job_detail(driver, link, state)
                    job_data["State"] = state

                    if writer is None:
                        csv_file = open(output_file, "w", newline="", encoding="utf-8")
                        writer = csv.DictWriter(csv_file, fieldnames=list(job_data.keys()))
                        writer.writeheader()
                    writer.writerow(job_data)
                    csv_file.flush()
                    total_saved += 1
                    log(state, f"    Saved. Running total: {total_saved}")

                except Exception as e:
                    log(state, f"    FAILED on {link}: {e}")
                time.sleep(1)

            time.sleep(1.5)
    finally:
        if csv_file:
            csv_file.close()
        driver.quit()
        log(state, f"DONE. Total jobs saved: {total_saved}")


# ---------------- MERGE + DEDUP ----------------

def merge_and_dedup(final_output=FINAL_OUTPUT):
    seen_links = set()
    all_rows = []
    fieldnames = None

    if not os.path.isdir(TEMP_DIR):
        print("No state CSVs found — nothing to merge.", flush=True)
        return

    for fname in os.listdir(TEMP_DIR):
        if fname.endswith(".csv"):
            with open(os.path.join(TEMP_DIR, fname), "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if fieldnames is None:
                    fieldnames = reader.fieldnames
                for row in reader:
                    link = row.get("JobLink", "")
                    if link and link not in seen_links:
                        seen_links.add(link)
                        all_rows.append(row)

    if not all_rows:
        print("No jobs found across any state CSVs.", flush=True)
        return

    final_fields = [f for f in fieldnames if f != "JobLink"]
    for row in all_rows:
        row.pop("JobLink", None)

    with open(final_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=final_fields)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nMerged and deduplicated: {len(all_rows)} unique jobs saved to {final_output}", flush=True)


# ---------------- MAIN ----------------

if __name__ == "__main__":
    print(f"Starting scrape across {len(STATES)} states with {MAX_PARALLEL_WORKERS} parallel workers...\n", flush=True)

    with multiprocessing.Pool(processes=MAX_PARALLEL_WORKERS) as pool:
        pool.map(scrape_state, STATES)

    merge_and_dedup()
