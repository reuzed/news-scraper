import typer
from collect_links import smart_collect_link_scheme, Paper, write_link_scrape
app = typer.Typer(help="News website scraping app using Selenium. Collect links, process these then scrape them.")

@app.command()
def scrape(
    url: str,
    depth: int = typer.Option(1, help="Crawl depth"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Scrape a URL."""
    print(f"Scraping {url} to depth {depth}")

@app.command()
def list(all: bool = typer.Option(False, "--all", "-a", help="List all items")):
    """List items."""
    print("Listing all..." if all else "Listing...")

if __name__ == "__main__":
    app()