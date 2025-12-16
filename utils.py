from urllib.parse import urlparse, urlunparse
import re
from pathlib import Path
from typing import Callable, Literal, get_args
from pydantic import BaseModel
from pydantic import TypeAdapter
from datetime import datetime

LINK_SCRAPE_DIR = Path("scrapes/links/raw")
CLEAN_LINK_SCRAPE_DIR = Path("scrapes/links/clean")
ARTICLE_SCRAPE_DIR = Path("scrapes/articles/raw")
CLEAN_ARTICLE_SCRAPE_DIR = Path("scrapes/articles/clean")

Paper = Literal[
    "thetimes",
    "thesun",
    "express",
    "mirror",
    "telegraph",
    "theguardian",
    "dailymail",
    "ft",
    "metro",
    "independent",
    "observer",
    "dailystar",
]

PAPERS:list[Paper] = list(get_args(Paper))

LinkScheme = Callable[[int], str]

ai_topic_page_maps: dict[Paper, LinkScheme] = {
    "thetimes": lambda n : f"https://www.thetimes.com/topic/artificial-intelligence?page={n}",
    "thesun": lambda n : f"https://www.thesun.co.uk/topic/artificial-intelligence/page/{n}/",
    "express": lambda n : f"https://www.express.co.uk/latest/artificial-intelligence?pageNumber={n}",
    "mirror": lambda n : f"https://www.mirror.co.uk/all-about/artificial-intelligence?pageNumber={n}",
    "telegraph": lambda n : f"https://www.telegraph.co.uk/artificial-intelligence/page-{n}/",
    "theguardian": lambda n : f"https://www.theguardian.com/technology/artificialintelligenceai?page={n}",
    "dailymail": lambda n : f"https://www.dailymail.co.uk/sciencetech/ai/index.html?page={n}",
    "ft": lambda n : f"https://www.ft.com/artificial-intelligence?page={n}",
    "metro": lambda n : f"https://metro.co.uk/tag/artificial-intelligence/page/{n}/",
    "independent": lambda n : f"https://www.independent.co.uk/topic/ai",
    "observer": lambda n : f"https://observer.co.uk/tags/artificial-intelligence/{20*n}",
    "dailystar": lambda n : f"https://www.dailystar.co.uk/latest/artificial-intelligence?pageNumber={n}",
}

class LinkData(BaseModel):
    text: str
    href: str

class SmartLinkScrapeResult(BaseModel):
    once_links: list[LinkData]
    schema_links: list[LinkData]
    multiple_links: list[LinkData]
    all_links: list[LinkData]

class ScrapeData(BaseModel):
    url: str
    content: str
    
class Scrape(ScrapeData):
    success: bool

def glob_articles():
    articles_dir = Path("scrapes/articles")
    article_paths = list(articles_dir.rglob("*.json"))
    return article_paths

def glob_links(paper:Paper|None=None):
    links_dir = Path("scrapes/links")
    links_paths = list(links_dir.rglob("*.json"))
    if paper is not None:
        links_paths = list(filter(lambda lp : f"-{paper}-" in str(lp), links_paths))
    return links_paths

def write_link_scrape(slsr: SmartLinkScrapeResult, filename: str):
    path = LINK_SCRAPE_DIR / filename
    with open(path, "w") as outfile:
        outfile.write(
            slsr.model_dump_json(indent=4)
        )

def read_link_scrape(filename: str) -> SmartLinkScrapeResult:
    path = LINK_SCRAPE_DIR / filename
    with open(path, "r") as outfile:
        contents = outfile.read()
    slsr = SmartLinkScrapeResult.model_validate_json(contents)
    return slsr

LinkDataList = TypeAdapter(list[LinkData])

def canonicalize_url(url: str) -> str:
    """Canonicalize a URL by removing fragments and normalizing.
    This removes #comments, #section, etc. to prevent duplicates."""
    parsed = urlparse(url)
    # Remove fragment (everything after #)
    canonical = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ''  # Remove fragment
    ))
    return canonical

def write_clean_link_scrape(links: list[LinkData], filename: str):
    """Write clean link scrape, deduplicating by canonical URL"""
    # Canonicalize URLs and deduplicate
    seen_canonical_urls = set()
    deduplicated_links = []
    
    for link in links:
        canonical_url = canonicalize_url(link.href)
        if canonical_url not in seen_canonical_urls:
            seen_canonical_urls.add(canonical_url)
            # Update the link's href to the canonical version
            deduplicated_link = LinkData(text=link.text, href=canonical_url)
            deduplicated_links.append(deduplicated_link)
    
    path = CLEAN_LINK_SCRAPE_DIR / filename
    with open(path, "w") as outfile:
        outfile.write(LinkDataList.dump_json(deduplicated_links, indent=4).decode())

def read_clean_link_scrape(filename: str) -> list[LinkData]:
    path = CLEAN_LINK_SCRAPE_DIR / filename
    with open(path, "r") as outfile:
        contents = outfile.read()
    return LinkDataList.validate_json(contents)

def link_scrape_filename(paper: Paper, page_limit: int, batch_id: str|None = None) -> str:
    if batch_id is None:
        batch_id = datetime.now().date().isoformat()
    return f"scrape-{paper}-{page_limit}-pages-{batch_id}.json"

def write_article_scrape(scrape: Scrape, filename: str):
    path = ARTICLE_SCRAPE_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(scrape.model_dump_json(indent=2))

def read_article_scrape(filename: str) -> Scrape:
    path = ARTICLE_SCRAPE_DIR / filename
    with open(path, "r") as f:
        return Scrape.model_validate_json(f.read())

def write_clean_article_scrape(scrape: ScrapeData, filename: str):
    path = CLEAN_ARTICLE_SCRAPE_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(scrape.model_dump_json(indent=2))

def read_clean_article_scrape(filename: str) -> ScrapeData:
    path = CLEAN_ARTICLE_SCRAPE_DIR / filename
    with open(path, "r") as f:
        return ScrapeData.model_validate_json(f.read())

def article_scrape_filename(paper: Paper, href: str, batch_id: str | None = None) -> str:
    if batch_id is None:
        batch_id = datetime.now().date().isoformat()
    
    # Extract path from href and sanitize
    parsed = urlparse(href)
    slug = parsed.path.strip("/").replace("/", "-")
    slug = re.sub(r"[^\w\-]", "", slug)  # Remove non-alphanumeric chars
    slug = slug[:80]  # Truncate if too long
    
    return f"{paper}-{slug}-{batch_id}.json"

def get_batch_id(batch_id: str | None = None) -> str:
    """Get batch_id, defaulting to today's date if None"""
    if batch_id is None:
        return datetime.now().date().isoformat()
    return batch_id

def parse_link_scrape_filename(filename: str) -> tuple[Paper | None, int | None, str | None]:
    """Parse link scrape filename to extract paper, page_limit, and batch_id.
    Format: scrape-{paper}-{page_limit}-pages-{batch_id}.json
    Returns (paper, page_limit, batch_id) or (None, None, None) if parsing fails"""
    match = re.match(r"scrape-([^-]+)-(\d+)-pages-(.+)\.json", filename)
    if match:
        paper_str, page_limit_str, batch_id_str = match.groups()
        paper = paper_str if paper_str in PAPERS else None
        page_limit = int(page_limit_str) if page_limit_str.isdigit() else None
        return (paper, page_limit, batch_id_str)
    return (None, None, None)

def parse_article_scrape_filename(filename: str) -> tuple[Paper | None, str | None]:
    """Parse article scrape filename to extract paper and batch_id.
    Format: {paper}-{slug}-{batch_id}.json where batch_id is YYYY-MM-DD
    Returns (paper, batch_id) or (None, None) if parsing fails"""
    # Remove .json extension
    name_without_ext = filename.replace(".json", "")
    
    # Batch_id is always in format YYYY-MM-DD at the end
    # Use regex to find date pattern at the end
    date_pattern = r'(\d{4}-\d{2}-\d{2})$'
    match = re.search(date_pattern, name_without_ext)
    if not match:
        return (None, None)
    
    batch_id = match.group(1)
    # Remove batch_id from the name to get paper-slug
    remaining = name_without_ext[:match.start()]
    
    # Paper is the first part before the first dash after removing batch_id
    # But we need to be careful - the slug can contain dashes
    # So we check if the first part (before first dash) is a valid paper
    parts = remaining.split("-", 1)
    if len(parts) >= 1:
        paper = parts[0] if parts[0] in PAPERS else None
        return (paper, batch_id)
    
    return (None, None)

def clean_link_scrape_exists(filename: str) -> bool:
    """Check if a clean link scrape file already exists"""
    path = CLEAN_LINK_SCRAPE_DIR / filename
    return path.exists()

def article_scrape_exists(filename: str) -> bool:
    """Check if an article scrape file already exists"""
    path = ARTICLE_SCRAPE_DIR / filename
    return path.exists()

def clean_article_scrape_exists(filename: str) -> bool:
    """Check if a clean article scrape file already exists"""
    path = CLEAN_ARTICLE_SCRAPE_DIR / filename
    return path.exists()

def get_link_scrapes_for_batch(batch_id: str) -> list[Path]:
    """Get all link scrape files for a given batch_id"""
    all_links = glob_links()
    matching = []
    for link_path in all_links:
        filename = link_path.name
        _, _, file_batch_id = parse_link_scrape_filename(filename)
        if file_batch_id == batch_id:
            matching.append(link_path)
    return matching

def get_clean_link_scrapes_for_batch(batch_id: str) -> list[Path]:
    """Get all clean link scrape files for a given batch_id"""
    all_links = glob_links()
    matching = []
    for link_path in all_links:
        filename = link_path.name
        _, _, file_batch_id = parse_link_scrape_filename(filename)
        if file_batch_id == batch_id:
            clean_path = CLEAN_LINK_SCRAPE_DIR / filename
            if clean_path.exists():
                matching.append(clean_path)
    return matching

def get_article_scrapes_for_batch(batch_id: str) -> list[Path]:
    """Get all article scrape files for a given batch_id"""
    all_articles = glob_articles()
    matching = []
    for article_path in all_articles:
        filename = article_path.name
        _, file_batch_id = parse_article_scrape_filename(filename)
        if file_batch_id == batch_id and "raw" in str(article_path):
            matching.append(article_path)
    return matching

def get_clean_article_scrapes_for_batch(batch_id: str) -> list[Path]:
    """Get all clean article scrape files for a given batch_id"""
    all_articles = glob_articles()
    matching = []
    for article_path in all_articles:
        filename = article_path.name
        _, file_batch_id = parse_article_scrape_filename(filename)
        if file_batch_id == batch_id and "clean" in str(article_path):
            matching.append(article_path)
    return matching