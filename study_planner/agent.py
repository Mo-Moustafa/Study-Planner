from . import prompts
from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from pypdf import PdfReader
from datetime import datetime


def get_current_date():
    """
    returns the current date in YYYY-MM-DD format. This can be used by the Scheduler agent to create a calendar starting from today.
    """
    return datetime.now().strftime("%Y-%m-%d")

def read_text_book(
    text_book_path: str,
    topic_keywords: list[str],
    max_pages_per_keyword: int = 1000,
    max_chars_per_page: int = 10000
) -> str:
    """
    Searches a PDF textbook for pages relevant to given topic keywords.

    Args:
        text_book_path: Path to the PDF file.
        topic_keywords: List of topic keywords to search for.
        max_pages_per_keyword: Maximum number of pages to return per keyword.
        max_chars_per_page: Maximum characters extracted per page.

    Returns:
        A string containing relevant text snippets with page numbers.
    """

    reader = PdfReader(text_book_path)
    results = []
    seen_pages = set()

    for keyword in topic_keywords:
        matches = 0

        for page_index, page in enumerate(reader.pages):
            if matches >= max_pages_per_keyword:
                break

            text = page.extract_text()
            if not text:
                continue

            if keyword.lower() in text.lower():
                if page_index in seen_pages:
                    continue  # avoid duplicate pages across keywords

                snippet = text[:max_chars_per_page]
                results.append(
                    f"--- Keyword: {keyword} | Page {page_index + 1} ---\n{snippet}"
                )
                seen_pages.add(page_index)
                matches += 1

    # Fallback: return first 2 pages if nothing matched
    if not results:
        for i, page in enumerate(reader.pages[:2]):
            text = page.extract_text() or ""
            results.append(
                f"--- Fallback Page {i + 1} ---\n{text[:max_chars_per_page]}"
            )

    return "\n\n".join(results)

# --- Agent 1: Scope Analyst (Alpha) ---
# Responsibility: Extract dates and topics from syllabi related to each course's midterm exam, and determine the importance of each course based on the midterm weight.
ScopeAnalyst = Agent(
    name="ScopeAnalyst",
    model='gemini-2.5-flash',
    instruction=prompts.SCOPE_ANALYST_PROMPT,
    output_key="midterm_scope"  # Writes result to this key in session state
)


# --- Agent 2: Resource Estimator (Beta) ---
# Responsibility: Estimate study hours using textbooks
ResourceEstimator = Agent(
    name="ResourceEstimator",
    model="gemini-2.5-flash",
    instruction=prompts.RESOURCE_ESTIMATOR_PROMPT,
    tools=[read_text_book],
    output_key="weighted_topics"
)


# --- Agent 3: Scheduler (Gamma) ---
# Responsibility: Create the calendar
Scheduler = Agent(
    name="Scheduler",
    model="gemini-2.5-flash",
    instruction=prompts.SCHEDULER_PROMPT,
    tools=[get_current_date],
    output_key="final_plan"
)


# --- Orchestration: The Assembly Line ---
# SequentialAgent runs Alpha -> Beta -> Gamma automatically
root_agent = SequentialAgent(
    name="StudyPlannerTeam",
    sub_agents=[ScopeAnalyst, ResourceEstimator, Scheduler],
    description="Full pipeline to generate study plans from syllabi and textbooks."
)