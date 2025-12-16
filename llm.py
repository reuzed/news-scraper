from openai import OpenAI
from dotenv import load_dotenv
import os
import json
from utils import SmartLinkScrapeResult, LinkData
from pydantic import BaseModel

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class FilteredLinks(BaseModel):
    links: list[LinkData]

class ArticleExtractionResult(BaseModel):
    content: str
    is_article: bool
    
def filter_links(scrape_result: SmartLinkScrapeResult) -> list[LinkData]:
    # Combine once_links and multiple_links for filtering
    candidates = (
        scrape_result.once_links 
        + scrape_result.multiple_links # can comment out these links, less likely to be good
    )
    # Just pass the hrefs and text for the LLM to evaluate
    link_summaries = [{"href": l.href, "text": l.text} for l in candidates]
    
    response = client.responses.parse(
        model="gpt-5",
        reasoning={"effort": "low"},
        instructions=(
            "You will be given a list of links taken from a webpage on a news site. "
            "Your task is to extract the links which refer to articles. "
            "You should remove links to things like settings, homepages, advertisements. "
            "Return only the hrefs of article links."
            "Article links will usually have some kind of id or some article title/keywords in their link text."
        ),
        input=json.dumps(link_summaries),
        text_format=FilteredLinks,
    )
    
    if not response.output_parsed:
        print("Issue in LLM link filtering, didn't get JSON back from API.")
        return scrape_result.once_links
    filtered_hrefs = {l.href for l in response.output_parsed.links}
    
    return [l for l in candidates if l.href in filtered_hrefs]

def extract_article_text(article_body_text: str) -> tuple[str, bool]:
    """Extract article text and determine if it's a valid article.
    
    Returns:
        tuple[str, bool]: (cleaned_content, is_article)
        - cleaned_content: The extracted article text
        - is_article: True if this is a valid article, False if it's a listing page, navigation, or non-article content
    """
    response = client.responses.parse(
        model="gpt-5",
        reasoning={"effort": "low"},
        instructions=(
            "You will be given the text taken from a webpage which may contain a newspaper article."
            "\n\n"
            "First, determine if this is actually an article page or if it's something else like:"
            "- A listing/index page (showing multiple article headlines and teasers)"
            "- A navigation page"
            "- A category page"
            "- A search results page"
            "- Any other non-article content"
            "\n\n"
            "If it IS a valid article:"
            "- Extract the article text verbatim, not changing any content."
            "- Remove the header and footer text, that came from hyperlinks, and other parts of the webpage, which is not related to the article."
            "- Remove non-article content such as 'Last modified on Tue 9 Dec 2025 02.02 EST' or 'Composite: Guardian Design; MR.Cole_Photographer; J Studios/Getty Images'"
            "- Set is_article to true"
            "\n\n"
            "If it is NOT a valid article (e.g., a listing page):"
            "- Set is_article to false"
            "- In the content field, provide a brief explanation of why it's not an article (e.g., 'This is a listing page showing multiple article headlines')"
        ),
        input=article_body_text,
        text_format=ArticleExtractionResult,
    )
    
    if not response.output_parsed:
        # Fallback: return original text and assume it's an article
        return article_body_text, True
    
    return response.output_parsed.content, response.output_parsed.is_article

if __name__ == "__main__":
    with open("example_article_llm_test.txt", "r") as file:
        article_body = file.read()
    
    processed_article, is_article = extract_article_text(article_body)
    
    print("article/processed", len(article_body), len(processed_article))
    print("is_article:", is_article)
    
    with open("example_article_llm_test_out.txt", "w") as file:
        file.write(processed_article)