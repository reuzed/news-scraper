from rich import print
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from pydantic import BaseModel

class Scrape(BaseModel):
    url: str
    content: str
    success: bool

ARCHIVE_PREFIX = "https://archive.md/"

def setup_driver():
    """Initialize and configure the Chrome WebDriver"""
    options = webdriver.ChromeOptions()
    # Uncomment the next line to run in headless mode (no browser window)
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver

def scrape_body_text(driver: webdriver.Chrome) -> str:
    # Scrape visible text from the body element of the current page
    body = driver.find_element(by=By.CLASS_NAME, value="body")
    return body.text

def find_archive_page_link(driver: webdriver.Chrome) -> str:
    # When we are on archive.md page, we want to click the archive link to get to our article
    links = driver.find_elements(By.XPATH, "//a[contains(@href, 'archive.md')]")
        
    if len(links) == 0:
        time.sleep(10)
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'archive.md')]")
    
    # All the bad archive links have a webpage after https://archive.md, we can find this by looking for a . after md
    link_texts = list(map(lambda l: l.get_attribute('href'), links))
    # print("found", len(links), "links", link_texts)

    good_link_texts = list(filter(lambda lt: '.' not in lt.split("md")[1], link_texts)) # type: ignore
    good_link_text = good_link_texts[0]
    # print("good links", len(good_link_texts), good_link_text)
    if good_link_text is None:
        print()
        raise ValueError("No link found")
    return good_link_text

def scrape_website(driver: webdriver.Chrome, url: str, captcha_wait_time=60) -> str:
    """
    Navigate to a website, click a link, wait for CAPTCHA, and scrape body text
    
    Args:
        url: The initial URL to visit
        captcha_wait_time: Maximum time to wait for CAPTCHA completion (seconds)
    
    Returns:
        The scraped body text as a string
    """    
    time.sleep(1)
    
    # Navigate to the initial URL
    print(f"Navigating to {url}...")
    driver.get(url)
    
    WebDriverWait(driver, captcha_wait_time).until(
        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'archive.md')]"))
    )
    
    time.sleep(2)  # Brief wait for page load
    
    good_link_text = find_archive_page_link(driver)
    
    # Go to archived page
    print(f"Navigating to {good_link_text}...")
    driver.get(good_link_text)
    
    time.sleep(2) # Wait for page load again
    
    # Scrape the body text
    print("Scraping body text...")
    body_text = scrape_body_text(driver)
    
    print(f"Scraped {len(body_text)} characters.")
    return body_text
        
def scrape_from_archive(urls: str | list[str]) -> list[Scrape]:
    # Run the scraper
    if isinstance(urls, str):
        urls = [urls]
        
    driver = setup_driver()
    
    scrapes: list[Scrape] = []
    
    for url in urls:
        archive_url = ARCHIVE_PREFIX + url
        
        try: 
            scraped_content = scrape_website(
                driver=driver,
                url=archive_url,
                captcha_wait_time=60,  # Wait up to 60 seconds for CAPTCHA
            )
            success = True
        except:
            scraped_content = ""
            success = False
        scrapes.append(Scrape(
            url=url,
            content=scraped_content,
            success=success,
        ))
    return scrapes


if __name__ == "__main__":
    articles = [
        "https://www.ft.com/content/8112d77f-2531-400f-b947-b506fe3c6b3f", 
        "https://www.theguardian.com/media/2025/dec/09/youth-movement-digital-justice-spreading-across-europe",
        "https://www.dailymail.co.uk/sciencetech/article-12068585/What-10-American-cities-look-like-2050-predicted-AI.html",
    ]
    
    scrape = scrape_from_archive(articles)
    
    print(scrape[0].url, scrape[0].content[:500])
    
    with open("scraped_content.txt", "w", encoding="utf-8") as f:
        f.write(scrape[0].content)
    print("\n[Content saved to scraped_content.txt]")
