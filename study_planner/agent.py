from . import prompts
from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents import SequentialAgent
from pypdf import PdfReader
from datetime import datetime
import json

path_dict = {
    "Quantum": "study_planner/textbooks/quantum.pdf",
    "Business": "study_planner/textbooks/business.pdf",
    "Biostatistics": "study_planner/textbooks/biostats.pdf",
}

def get_current_date():
    """
    returns the current date in YYYY-MM-DD format. This can be used by the Scheduler agent to create a calendar starting from today.
    """
    return datetime.now().strftime("%Y-%m-%d")


def scan_textbook(
    topic_keywords: list[str],
    textbook_name: str,
    patience_limit: int = 20
) -> str:
    """
    Scans a PDF to count pages per topic. 
    Assumes topics are roughly ordered. 
    Stops scanning for a keyword if it hasn't been seen for `patience_limit` pages 
    after the last match.
    """
    
    textbook_path = path_dict[textbook_name.split()[0]]  # Simple mapping for example purposes

    reader = PdfReader(textbook_path)
    total_pages = len(reader.pages)

    topic_stats = {}
    
    # Optimization: Start the next search near where the previous one was found.
    # (Initialize at 0 for the first topic)
    current_scan_index = 0

    for keyword in topic_keywords:
        match_count = 0
        last_match_index = -1
        found_start = False
        
        # Start loop from our current position in the book
        for i in range(current_scan_index, total_pages):
            page = reader.pages[i]
            text = page.extract_text()
            
            # Simple check if keyword is in text (case-insensitive)
            if text and keyword.lower() in text.lower():
                if not found_start:
                    found_start = True
                    # Update global index so the NEXT topic doesn't start from page 0
                    current_scan_index = i 
                
                match_count += 1
                last_match_index = i
            
            # LOGIC: If we started finding the topic, but haven't seen it 
            # for 'patience_limit' pages, assume the section is over.
            elif found_start:
                if (i - last_match_index) >= patience_limit:
                    break 

        topic_stats[keyword] = match_count

    return json.dumps(topic_stats)
       

# --- Agent 1: Scope Analyst (Alpha) ---
# Responsibility: Extract dates and topics from syllabi related to each course's midterm exam, and determine the importance of each course based on the midterm weight.
ScopeAnalyst = Agent(
    name="ScopeAnalyst",
    model='gemini-2.5-flash',
    instruction=prompts.SCOPE_ANALYST_PROMPT,
    tools=[scan_textbook],  # Provide the tool to scan textbooks
    output_key="midterm_scope"  # Writes result to this key in session state
)


# --- Agent 2: Resource Estimator (Beta) ---
# Responsibility: Estimate study hours using textbooks
ResourceEstimator = Agent(
    name="ResourceEstimator",
    model="gemini-2.5-flash",
    instruction=prompts.RESOURCE_ESTIMATOR_PROMPT,
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
# SequentialAgent runs ScopeAnalyst -> ResourceEstimator -> Scheduler automatically
root_agent = SequentialAgent(
    name="StudyPlannerTeam",
    sub_agents=[ScopeAnalyst, ResourceEstimator, Scheduler],
    description="Full pipeline to generate study plans from syllabi and textbooks."
)


# root_agent = Agent(
#     name="root_agent",
#     model="gemini-2.5-flash",
#     instruction="""
#     You are a helpful Study Assistant.
#     When the user uploads syllabi, textbooks and midterm details files, you will:
#     1- Run the ScopeAnalyst agent to extract the midterm scope,
#     2- Run the ResourceEstimator to estimate study hours per topic,
#     3- Run the Scheduler to create a study plan calendar.

#     DO NOT try to do any of these tasks yourself. Your job is to run the agents in the correct order and pass the outputs from one to another.

#     """,
#     sub_agents=[ResourceEstimator],
#     tools=[AgentTool(ScopeAnalyst), AgentTool(Scheduler)]
# )