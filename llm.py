from openai import OpenAI
from dotenv import load_dotenv
import os
import json

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def filter_links(links: list[str]) -> list[str]:
    response = client.responses.create(
        model="gpt-5",
        reasoning={"effort": "low"},
        instructions=(
            "You will be given a list of links taken from a webpage on a news site."
            "Your task is to extract the links which refer to articles."
            "You should remove links to things like settings, homepages, advertisements"
            ),
        input=json.dumps(links),
    )
    list_text = response.output_text
    return json.loads(list_text)

def extract_article_text(article_body_text: str) -> str:
    response = client.responses.create(
        model="gpt-5",
        reasoning={"effort": "low"},
        instructions=(
            "You will be given the text taken from a webpage which contains a newspaper article."
            "You must extract the article text verbatim, not changing any content."
            "You must remove the header and footer text, that came from hyperlinks, and other parts of the webpage, which is not related to the article."
            "Also remove non-article content such as 'Last modified on Tue 9 Dec 2025 02.02 EST' or 'Composite: Guardian Design; MR.Cole_Photographer; J Studios/Getty Images'" 
        ),
        input=article_body_text,
    )
    return response.output_text

if __name__ == "__main__":
    with open("example_article_llm_test.txt", "r") as file:
        article_body = file.read()
    
    processed_article = extract_article_text(article_body)
    
    print("article/processed", len(article_body), len(processed_article))
    
    with open("example_article_llm_test_out.txt", "w") as file:
        file.write(processed_article)