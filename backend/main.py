import asyncio
import io
import os
import certifi
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import json
import operator
import trafilatura
import requests
from pypdf import PdfReader

from langchain_text_splitters import RecursiveCharacterTextSplitter


from langgraph.graph import StateGraph, START, END
#paralle agent calling 
from langgraph.constants import Send


from typing import TypedDict, Annotated, Any

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

# Hugging Face integration is kept for future fallback/use. Groq is the
# active provider below.
# from langchain_huggingface import (
#     ChatHuggingFace,
#     HuggingFaceEndpoint,
# )

from langchain_groq import ChatGroq

from langchain_mcp_adapters.client import MultiServerMCPClient

from langchain_core.prompts import ChatPromptTemplate


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


# =========================================================
# LLM
# =========================================================

# -------------------------------------------------------------------------
# Hugging Face configuration (kept, but currently disabled)
# -------------------------------------------------------------------------
# HUGGINGFACE_TOKEN = os.getenv(
#     "HUGGINGFACEHUB_ACCESS_TOKEN"
# )
#
# if not HUGGINGFACE_TOKEN:
#     raise ValueError(
#         "HUGGINGFACEHUB_ACCESS_TOKEN is missing from .env"
#     )
#
# llm = HuggingFaceEndpoint(
#     # This is configurable because not every Hugging Face model is
#     # available through the hosted inference provider.  The NVIDIA
#     # NVFP4 model is primarily intended for local/deployed inference.
#     repo_id=os.getenv(
#         "HF_MODEL_ID",
#         "meta-llama/Llama-3.1-8B-Instruct"
#     ),
#     task="text-generation",
#     huggingfacehub_api_token=HUGGINGFACE_TOKEN,
#     max_new_tokens=1024,
#     temperature=0.7,
# )
#
# model = ChatHuggingFace(
#     llm=llm
# )


# =========================================================
# ACTIVE LLM: GROQ
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing from .env"
    )


# ChatGroq preserves the existing model.invoke(...) interface used by all
# guardrail, supervisor, research, and report agents.
model = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=1,
    max_tokens=2048,
    reasoning_effort="medium",
    streaming=False,
)


# =========================================================
# DATABASE
# =========================================================

# =========================================================
# MCP CLIENT
# =========================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()


if not TAVILY_API_KEY:
    raise ValueError(
        "TAVILY_API_KEY is missing from .env"
    )

if not NEWS_API_KEY:
    raise ValueError(
        "NEWS_API_KEY is missing from .env"
    )

 
client = MultiServerMCPClient(
    {
        "research": {
            # Run the MCP server as a local subprocess over stdio.
            "transport": "stdio",
            "command": os.sys.executable,
            "args": [
                os.path.join(
                    os.path.dirname(__file__),
                    "MCP_servers.py"
                )
            ],
            "env": {
                "TAVILY_API_KEY": TAVILY_API_KEY,
                "NEWS_API_KEY": NEWS_API_KEY,
                "YOUTUBE_API_KEY": YOUTUBE_API_KEY,
            },
        }
    }
)


# =========================================================
# MCP TOOL INITIALIZATION
# =========================================================

web_search_tool = None
paper_search_tool = None
news_search_tool = None
youtube_search_tool = None


async def initialize_research_tools():

    global web_search_tool
    global paper_search_tool
    global news_search_tool
    global youtube_search_tool

    if (
        web_search_tool is not None
        and paper_search_tool is not None
        and news_search_tool is not None
        and youtube_search_tool is not None
    ):
        return

    tools = await client.get_tools(
        server_name="research"
    )

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    web_search_tool = tools_by_name.get(
        "web_search"
    )

    paper_search_tool = tools_by_name.get(
        "paper_search"
    )

    news_search_tool = tools_by_name.get(
        "news_search"
    )
    youtube_search_tool = tools_by_name.get("youtube_search")

    missing = [
        name
        for name, tool in {
            "web_search": web_search_tool,
            "paper_search": paper_search_tool,
            "news_search": news_search_tool,
            "youtube_search": youtube_search_tool
        }.items()
        if tool is None
    ]

    if missing:
        raise RuntimeError(
            "Research MCP tools not found: "
            + ", ".join(missing)
        )


# =========================================================
# MCP SEARCH FUNCTIONS   -- function calling tools 
# =========================================================

async def web_mcp_search(
    query: str,
    limit: int = 3
):

    await initialize_research_tools()

    return await web_search_tool.ainvoke(
        {
            "query": query,
            "max_results": limit
        }
    )


async def paper_mcp_search(
    query: str,
    limit: int = 3
):

    await initialize_research_tools()

    return await paper_search_tool.ainvoke(
        {
            "query": query,
            "limit": limit
        }
    )


async def news_mcp_search(
    query: str,
    limit: int = 3
):

    await initialize_research_tools()

    return await news_search_tool.ainvoke(
        {
            "query": query,
            "limit": limit
        }
    )

async def youtube_mcp_search(query:str , limit:int=3):
    await initialize_research_tools()
    return await youtube_search_tool.ainvoke(
        {
            "query":query,
            "limit": limit
        }
    )


# =========================================================
# ASYNC HELPER   -- ??
# =========================================================

def run_async(coro):

    try:
        asyncio.get_running_loop()

    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(
        max_workers=1
    ) as executor:

        return executor.submit(
            asyncio.run,
            coro
        ).result()


# =========================================================
# STATE
# =========================================================

class ResearchState(TypedDict):

    messages: Annotated[
        list[AnyMessage],
        operator.add
    ]

    user_query: str

    # Supervisor
    guardrail_allowed: bool
    guardrail_reason: str

    selected_agents: list[str]

    research_constraints: dict[str, Any]

    supervisor_reasoning: str
    supervisor_failed: bool
    supervisor_error: str

    # Research results
    web_results: str
    paper_results: str
    news_results: str
    youtube_results: str

    # Report
    draft_report: str
    combined_research_context: str
    analysis_context: str
    analysis_route: str
    context_token_estimate: int

    # Revision
    revision_requires_research: bool
    revision_query: str
    revision_reason: str


    # Final
    final_response: str

    llm_calls: Annotated[int, operator.add]


# =========================================================
# AGENTS
# =========================================================

KNOWN_AGENTS = {
    "web_research_agent",
    "paper_research_agent",
    "news_research_agent",
    "youtube_research_agent"
}


AGENT_ORDER = [
    "web_research_agent",
    "paper_research_agent",
    "news_research_agent",
    "youtube_research_agent"
   
    
]

####agr urani reseacrrh papers pr research krni hui toh islie 
def empty_constraints():

    return {
        "topic": "",
        "time_range": "",
        "source_preference": "",
        "special_requirements": [],
    }


def _prompt_text(value, max_chars: int = 8000):
    """Serialize and cap tool output before sending it to the LLM."""

    if isinstance(value, (dict, list)):
        text = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    else:
        text = str(value or "")

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        + "\n\n[Additional source content truncated.]"
    )


def _decode_tool_result(value):
    """Unwrap MCP text-content responses into Python data."""
    current = value

    for _ in range(3):
        if isinstance(current, dict):
            if (
                current.get("type") == "text"
                and isinstance(current.get("text"), str)
            ):
                current = current["text"]
                continue
            return current

        if isinstance(current, list):
            if (
                len(current) == 1
                and isinstance(current[0], dict)
                and current[0].get("type") == "text"
            ):
                current = current[0].get("text", "")
                continue
            return current

        if isinstance(current, str):
            try:
                current = json.loads(current)
                continue
            except json.JSONDecodeError:
                return current

        return current

    return current


# =========================================================
# LLM HELPERS
# =========================================================

def _llm_text(
    system_prompt: str,
    user_prompt: str
):

    response = model.invoke(
        [
            SystemMessage(
                content=system_prompt
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]
    )

    return str(response.content)



#llm se aae str response ko json mai convert krega 
def _json_from_llm(text: str):

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "Model did not return JSON."
        )

    return json.loads(
        text[start:end + 1]
    )


# =========================================================
# SUPERVISOR
# =========================================================
def guardrail_agent(state: ResearchState):
    """Validate the user request before sending it to the supervisor."""

    query = state["user_query"]

    llm_calls = state.get("llm_calls", 0)

    # -----------------------------------------------------
    # GUARDRAIL
    # -----------------------------------------------------

    guardrail_prompt = f"""
    Determine whether the following request is suitable
    for an AI research assistant.
    
    Allow requests asking for:
    - research
    - factual information
    - academic information
    - technology
    - science
    - business
    - current events
    - literature
    - comparisons
    - reports
    - general knowledge
    
    Block harmful or clearly inappropriate requests.
    Do not block a normal research topic merely because it could be
    more specific. If the request names a subject or asks for research,
    allow it.
    
    Return strict JSON:
    
    {{
        "allowed": true,
        "reason": ""
    }}
    
    User request:
    {query}
    """
    
    try:
        raw = _llm_text(
            "You are a research input guardrail. Return strict JSON only.",
            guardrail_prompt,
        )
        result = _json_from_llm(raw)

        if not isinstance(result, dict):
            raise ValueError("Guardrail response must be a JSON object.")

        allowed_value = result.get("allowed", True)
        if isinstance(allowed_value, str):
            allowed = allowed_value.strip().lower() in {
                "true",
                "yes",
                "allow",
                "allowed",
            }
        else:
            allowed = bool(allowed_value)

        reason = str(result.get("reason", "")).strip()
        llm_calls += 1
    except Exception as exc:
        print(
            f"Guardrail fallback used: {type(exc).__name__}: {exc}"
        )
        allowed = True
        reason = "Guardrail fallback allowed the request."

    if not reason:
        reason = "Request allowed." if allowed else "Request blocked."

    # Always return a state update. Returning None for allowed requests makes
    # LangGraph fail before the supervisor can run.
    return {
        "guardrail_allowed": allowed,
        "guardrail_reason": reason,
        "selected_agents": [] if not allowed else state.get("selected_agents", []),
        "research_constraints": empty_constraints(),
        "supervisor_reasoning": reason if not allowed else state.get("supervisor_reasoning", ""),
        "final_response": reason if not allowed else state.get("final_response", ""),
        "messages": [AIMessage(content=reason)],
        "llm_calls": llm_calls,
    }

def supervisor_agent(
    state: ResearchState
):


    query = state["user_query"]
    reason = state["guardrail_reason"]
    llm_calls = state.get("llm_calls", 0)
    # -----------------------------------------------------
    # SUPERVISOR
    # -----------------------------------------------------

    supervisor_prompt = f"""
You are the supervisor of a multi-agent
AI research system.

Choose the specialist agents required
for the user's research request.

Available agents:

- web_research_agent:
  searches websites and online sources

- paper_research_agent:
  searches academic and research papers

- news_research_agent:
  searches recent news and reports

- youtube_research_agent:
  searches relevant YouTube videos and transcripts

Return strict JSON:

{{
    "selected_agents": [
        "web_research_agent",
        "paper_research_agent",
        "news_research_agent"
        
    ],
    "research_constraints": {{
        "topic": "",
        "time_range": "",
        "source_preference": "",
        "special_requirements": []
    }},
    "reasoning": ""
}}

User request:

{query}
"""

    try:
        print("supervisor agent called : ")
        raw = _llm_text(
            "You route research work to specialist agents. "
            "Return strict JSON only.",
            supervisor_prompt
        )

        parsed = _json_from_llm(raw)

        requested = parsed.get(
            "selected_agents",
            []
        )

        selected_agents = [
            agent
            for agent in AGENT_ORDER
            if agent in requested
        ]

        # if "report_agent" not in selected_agents:
        #     selected_agents.append(
        #         "report_agent"
        #     )

        constraints = empty_constraints()

        parsed_constraints = parsed.get(
            "research_constraints",
            {}
        )

        if isinstance(
            parsed_constraints,
            dict
        ):
            constraints.update(
                parsed_constraints
            )

        reasoning = str(
            parsed.get(
                "reasoning",
                ""
            )
        ).strip()

        llm_calls += 1

    except Exception as exc:

        print(
            f"Supervisor failed: {type(exc).__name__}: {exc}"
        )

        error_message = (
            "Unable to process your request because the supervisor "
            "encountered a temporary error. Please try again later."
        )
        selected_agents = []
        constraints = empty_constraints()
        reasoning = error_message

        return {
            "guardrail_allowed": True,
            "guardrail_reason": reason,
            "selected_agents": [],
            "research_constraints": constraints,
            "supervisor_reasoning": reasoning,
            "supervisor_failed": True,
            "supervisor_error": error_message,
            "final_response": error_message,
            "messages": [AIMessage(content=error_message)],
            "llm_calls": llm_calls,
        }

    return {

        "guardrail_allowed": True,

        "guardrail_reason": reason,

        "selected_agents": selected_agents,

        "research_constraints": constraints,

        "supervisor_reasoning": reasoning,
        "supervisor_failed": False,
        "supervisor_error": "",

        "messages": [
            AIMessage(
                content="Research plan created."
            )
        ],

        "llm_calls": llm_calls,
    }


# =========================================================
# GUARDRAIL BLOCK
# =========================================================

def guardrail_blocked_agent(
    state: ResearchState
):

    reason = (
        state.get("final_response")
        or state.get("guardrail_reason")
        or "Request blocked."
    )

    return {
        "final_response": reason,
        "messages": [
            AIMessage(
                content=reason
            )
        ],
    }


def supervisor_error_agent(state: ResearchState):
    """Finish the graph after a supervisor routing failure."""

    error_message = state.get(
        "supervisor_error",
        "Unable to process your request because the supervisor "
        "encountered a temporary error. Please try again later.",
    )

    return {
        "selected_agents": [],
        "final_response": error_message,
        "messages": [AIMessage(content=error_message)],
    }


# =========================================================
# WEB RESEARCH AGENT
# =========================================================


def web_research_agent(state: ResearchState):
    print("web search agent called:")

    query = state["user_query"]

    try:
        result = _decode_tool_result(
            run_async(
                web_mcp_search(
                    query,
                    limit=3
                )
            )
        )

        if isinstance(result, dict):
            answers = result.get("results", [])
        elif isinstance(result, list):
            answers = result
        else:
            answers = []

       

    except Exception as exc:
        print(
            f"Web search failed: "
            f"{type(exc).__name__}: {exc}"
        )

       

    return {
        "web_results": answers,

        "messages": [
            AIMessage(
                content="Web research completed."
            )
        ],

        "llm_calls": 1
    }


# =========================================================
# PAPER RESEARCH AGENT
# =========================================================


def extract_pdf_text(pdf_url: str) -> str:
    if not pdf_url:
        return ""

    try:
        response = requests.get(
            pdf_url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"}
        )


        response.raise_for_status()

        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)

        pages = []

        for page in reader.pages:
            text = page.extract_text() or ""

            if text.strip():
                pages.append(text)

        return "\n\n".join(pages)

    except Exception as exc:
        print(
            f"PDF extraction failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return ""



def paper_research_agent(state: ResearchState):

    print("paper_research_agent called")

    query = state["user_query"]

    try:
        result = _decode_tool_result(
            run_async(
                paper_mcp_search(
                    query,
                    limit=3
                )
            )
        )

        if isinstance(result, dict):
            papers = result.get(
                "results",
                result.get("papers", [])
            )
        elif isinstance(result, list):
            papers = result
        else:
            papers = []

        paper_results = []

        # Extract text from only one paper URL
        for paper in papers:

            if not isinstance(paper, dict):
                continue

            title = paper.get("title", "Unknown title")
            authors = paper.get("authors", "")
            year = paper.get("year", "Unknown year")
            paper_url = paper.get("paper_url", "")
            pdf_url = paper.get("pdf_url", "")
            citation_count = paper.get("citation_count", 0)

            print(f"Processing paper: {title}")

            paper_text = ""

            if pdf_url:
                paper_text = extract_pdf_text(pdf_url)

            if not paper_text:
                paper_text = paper.get("abstract", "")

            paper_results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "paper_url": paper_url,
                "pdf_url": pdf_url,
                "citation_count": citation_count,
                "answer": paper_text
            })

            # Stop after processing one paper
            break

        print(
            f"Paper research completed. "
            f"Processed {len(paper_results)} paper."
        )

    except Exception as exc:
        print(
            f"Paper search failed: "
            f"{type(exc).__name__}: {exc}"
        )

        paper_results = []

    return {
        "paper_results": paper_results,
        "messages": [
            AIMessage(
                content="Paper research completed."
            )
        ],
        "llm_calls": state.get("llm_calls", 0)
    }


# =========================================================
# NEWS RESEARCH AGENT
# =========================================================

def extract_article_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=False,
            include_links=False
        )

        return text or ""

    except Exception as e:
        print(f"Extraction failed: {url} -> {e}")
        return ""
    


    


def news_research_agent(state: ResearchState):
    print("news_research_agent called:")

    query = state["user_query"]

    try:
        result = _decode_tool_result(
            run_async(
                news_mcp_search(
                    query,
                    limit=3
                )
            )
        )

        if isinstance(result, dict):
            articles = result.get("articles", [])
        elif isinstance(result, list):
            articles = result
        else:
            articles = []

        news_results = []

        for article in articles:

            if not isinstance(article, dict):
                continue

            title = article.get("title", "")
            url = article.get("url", "")

            print(f"Processing article: {title}")

            if not url:
                continue

            # Extract original article text
            article_text = extract_article_text(url)

            if not article_text:
                print(f"Could not extract article: {url}")
                continue

            news_results.append({
                "title": title,
                "url": url,
                "source": article.get(
                    "source", {}
                ).get("name", ""),
                "published_at": article.get(
                    "publishedAt", ""
                ),
                "content": article_text
            })

            # Process only one article
            break

    except Exception as exc:
        print(
            f"News search failed: "
            f"{type(exc).__name__}: {exc}"
        )

        news_results = []

    return {
        "news_results": news_results,
        "messages": [
            AIMessage(
                content="News research completed."
            )
        ],
        "llm_calls": state.get("llm_calls", 0)
    }





def youtube_research_agent(state: ResearchState):

    print("youtube_research_agent called")

    query = state["user_query"]

    try:
        result = _decode_tool_result(
            run_async(
                youtube_mcp_search(
                    query,
                    limit=1
                )
            )
        )

        youtube_results = []

        if isinstance(result, dict):
            result = result.get("results", [])

        for video in result or []:

            if not isinstance(video, dict):
                continue

            if not video.get("title") and not video.get("url"):
                continue

            title = video.get("title", "")
            channel = video.get("channel", "")
            video_url = video.get("url", "")
            transcript = video.get("transcript", "")

            print(f"Processing YouTube video: {title}")

            if not transcript:
                print(f"Transcript unavailable: {title}")
                continue

            youtube_results.append({
                "title": title,
                "channel": channel,
                "video_url": video_url,
                "transcript": transcript
            })

            # Process only one video
            break

    except Exception as exc:
        print(
            f"YouTube research failed: "
            f"{type(exc).__name__}: {exc}"
        )

        youtube_results = []

    return {
        "youtube_results": youtube_results,
        "messages": [
            AIMessage(
                content="YouTube research completed."
            )
        ],
        "llm_calls": state.get("llm_calls", 0)
    }




# =========================================================
# RESEARCH FAN-IN
# =========================================================

def research_complete_agent(state: ResearchState):

    print("All parallel research agents completed.")

    return {
        "messages": [
            AIMessage(
                content="All research sources collected."
            )
        ]
    }



# =========================================================
# ANALYSIS AGENT
# =========================================================

def final_agent(state: ResearchState):

    print("research analysis agent called")

    query = state["user_query"]

    # Collect research from all agents
    research_data = {
        "web_sources": state.get("web_results", []),
        "academic_papers": state.get("paper_results", []),
        "news_sources": state.get("news_results", []),
        "youtube_videos": state.get("youtube_results", [])
    }

    # Convert research data into text
    context = json.dumps(
        research_data,
        ensure_ascii=False,
        indent=2,
        default=str
    )

    # Context thresholds (characters)
    MAX_CONTEXT_LENGTH = 20000
    CHUNK_SIZE = 12000

    llm_calls = 0

    try:

        print(f"Research context length: {len(context)}")

        system_prompt = """
        You are a professional AI research analysis
        and report generation assistant.

        Use only the information provided by the research agents.
        Do not invent facts, sources, or URLs.
        Preserve original source names, titles, and URLs.
        Clearly mention when information is unavailable.

        Return the final report using these sections:

        1. Research Summary
        2. Key Findings
        3. Detailed Analysis
        4. Academic Research
        5. Recent News / Reports
        6. Sources

        The Research Summary should contain 4-6 well-developed
        paragraphs explaining the main concepts, key evidence,
        different perspectives, agreements or contradictions,
        practical implications, and a balanced conclusion.

        For important sources, include the source name,
        title, useful summary, and original URL.

        Return only the research report.
        """

        # -------------------------------------------------
        # CASE 1: SMALL CONTEXT - DIRECT REPORT GENERATION
        # -------------------------------------------------
        if len(context) <= MAX_CONTEXT_LENGTH:

            print("Context is small. Generating report directly.")

            prompt = f"""
            USER QUESTION:
            {query}

            RESEARCH DATA:
            {context}

            Analyze the collected research and generate
            the complete final research report.
            """

            response = model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])

            result = response.content
            llm_calls += 1

        # -------------------------------------------------
        # CASE 2: LARGE CONTEXT - CHUNK + SUMMARIZE
        # -------------------------------------------------
        else:

            print("Context is large. Dividing into chunks.")

            chunks = []
            remaining = context

            # Split at newline boundaries when possible
            while remaining:

                if len(remaining) <= CHUNK_SIZE:
                    chunks.append(remaining)
                    break

                split_at = remaining.rfind(
                    "\n", 0, CHUNK_SIZE
                )

                # Avoid creating an excessively small chunk
                if split_at < CHUNK_SIZE // 2:
                    split_at = CHUNK_SIZE

                chunks.append(remaining[:split_at])
                remaining = remaining[split_at:].lstrip("\n")

            print(f"Total chunks: {len(chunks)}")

            chunk_summaries = []

            # Generate a summary for each chunk
            for index, chunk in enumerate(chunks, start=1):

                print(
                    f"Summarizing chunk {index}/{len(chunks)}"
                )

                chunk_prompt = f"""
                USER QUESTION:
                {query}

                RESEARCH CONTEXT - CHUNK {index}/{len(chunks)}:
                {chunk}

                Summarize the useful research information
                relevant to the user's question.

                Requirements:
                - Preserve important facts and findings.
                - Preserve source names, titles and original URLs.
                - Include relevant academic, news and video details.
                - Mention disagreements or limitations when present.
                - Do not invent facts or sources.
                - Do not generate the final report yet.
                """

                response = model.invoke([
                    SystemMessage(
                        content=(
                            "You are a research summarization "
                            "assistant. Summarize the provided "
                            "chunk accurately and preserve source links."
                        )
                    ),
                    HumanMessage(content=chunk_prompt)
                ])

                chunk_summaries.append(response.content)
                llm_calls += 1

            # Generate the final report from all chunk summaries
            print("Generating final report from chunk summaries.")

            combined_summaries = "\n\n".join(
                f"CHUNK SUMMARY {index}:\n{summary}"
                for index, summary in enumerate(
                    chunk_summaries, start=1
                )
            )

            final_prompt = f"""
            USER QUESTION:
            {query}

            SUMMARIES OF THE COLLECTED RESEARCH:
            {combined_summaries}

            Using all the summaries, synthesize a complete
            and coherent final research report.

            Requirements:
            - Combine overlapping findings without repetition.
            - Compare perspectives and identify contradictions.
            - Preserve original source names, titles and URLs.
            - Do not invent facts or missing source details.
            - Clearly identify unavailable information.
            - Follow all six sections specified in the system prompt.
            - Write a substantial Research Summary of 4-6 paragraphs.
            - Return only the final research report.
            """

            response = model.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=final_prompt)
            ])

            result = response.content
            llm_calls += 1

    except Exception as exc:

        print(
            f"Research analysis/report failed: "
            f"{type(exc).__name__}: {exc}"
        )

        result = (
            "Research analysis and report generation unavailable."
        )

    return {
        "draft_report": result,
        "final_response": result,
        "messages": [
            AIMessage(
                content="Research analysis and report completed."
            )
        ],
        "llm_calls": llm_calls
    }




# =========================================================
# HUMAN-IN-THE-LOOP (DISABLED)
# =========================================================
# The approval/revision agent and feedback evaluation flow are intentionally
# disabled. Reports are now finalized automatically after analysis. The
# legacy evaluator below is retained only as reference and is not registered
# in the graph.

def feedback_evaluation_agent(
    state: ResearchState
):
    """
    Check whether the user's feedback can be
    satisfied using the information we already have.

    If information exists:
        no new research

    If information is missing:
        create a focused research query
    """

    feedback = state.get(
        "human_feedback",
        ""
    ).strip()

    draft = state.get(
        "draft_report",
        ""
    )

    web_results = state.get(
        "web_results",
        ""
    )

    paper_results = state.get(
        "paper_results",
        ""
    )

    news_results = state.get(
        "news_results",
        ""
    )

    youtube_results = state.get(
        "youtube_results",
        ""
    )

    prompt = f"""
You are a feedback evaluation agent.

The user rejected the research report and gave feedback.

ORIGINAL USER QUERY:
{state.get("user_query", "")}

USER FEEDBACK:
{feedback}

CURRENT DRAFT REPORT:
{_prompt_text(draft)}

EXISTING WEB RESEARCH:
{_prompt_text(web_results)}

EXISTING PAPER RESEARCH:
{_prompt_text(paper_results)}

EXISTING NEWS RESEARCH:
{_prompt_text(news_results)}

EXISTING YOUTUBE RESEARCH:
{_prompt_text(youtube_results)}

Your job is to determine whether the user's feedback
can be satisfied using the information that is ALREADY
present in the existing research.

Return ONLY valid JSON:

{{
    "needs_research": true,
    "research_query": "...",
    "reason": "..."
}}

Rules:

1. needs_research = false when the existing research
   already contains enough information to satisfy the
   user's feedback.

Examples:
- Change formatting
- Make the answer shorter
- Explain an existing point in more detail
- Reorganize sections
- Add information that already exists in the research

2. needs_research = true when the user is asking for
   factual information, evidence, sources, dates,
   comparisons, statistics, examples, or details that
   are NOT available in the existing research.

3. If needs_research is true, create a focused
   standalone research query based specifically on
   the user's feedback.

4. Do not create a generic query.

5. Do not assume missing information exists.

6. Do not perform research yourself.

Return ONLY JSON.
"""

    try:

        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a research "
                        "feedback evaluator. "
                        "Return only valid JSON."
                    )
                ),
                HumanMessage(
                    content=prompt
                )
            ]
        )

        raw = response.content.strip()

        # Remove markdown fences if model adds them
        raw = raw.replace(
            "```json",
            ""
        ).replace(
            "```",
            ""
        ).strip()

        decision = json.loads(raw)

        needs_research = bool(
            decision.get(
                "needs_research",
                False
            )
        )

        research_query = str(
            decision.get(
                "research_query",
                ""
            )
        ).strip()

        reason = str(
            decision.get(
                "reason",
                ""
            )
        ).strip()

    except Exception as exc:

        print(
            "Feedback evaluation failed:",
            exc
        )

        # Conservative fallback:
        # use existing research instead of
        # unnecessarily performing another search.
        needs_research = False
        research_query = ""
        reason = (
            "Existing research will be reused "
            "because feedback evaluation failed."
        )

    return {

        "revision_requires_research":
            needs_research,

        "revision_query":
            research_query,

        "revision_reason":
            reason,

        "messages": [
            AIMessage(
                content=(
                    "Feedback evaluation completed."
                )
            )
        ],

        "llm_calls": 1,
    }




# =========================================================
# ROUTING
# =========================================================

ROUTE_MAP = {
    "guardrail_blocked": "guardrail_blocked",
    "supervisor_error": "supervisor_error",

    "web_research_agent":
        "web_research_agent",

    "paper_research_agent":
        "paper_research_agent",

    "news_research_agent":
        "news_research_agent",

    "youtube_research_agent":
    "youtube_research_agent",
}



##parallel agents working 
def route_after_guardrail(state: ResearchState):
    """Send blocked input to the blocker; otherwise run the supervisor."""

    return "guardrail_blocked" if not state.get("guardrail_allowed", True) else "supervisor"


def route_from_supervisor(state: ResearchState):

    if state.get("supervisor_failed", False):
        return "supervisor_error"

    if not state.get("guardrail_allowed", True):
        return "guardrail_blocked"

    selected = state.get("selected_agents", [])

    research_agents = [
        agent
        for agent in [
            "web_research_agent",
            "paper_research_agent",
            "news_research_agent",
            "youtube_research_agent",
        ]
        if agent in selected
    ]

    # If supervisor selected no research agent,
    # run all research agents.
    if not research_agents:
        research_agents = [
            "web_research_agent",
            "paper_research_agent",
            "news_research_agent",
            "youtube_research_agent",
        ]

    return [
        #send 
        Send(agent, state)
        for agent in research_agents
    ]


# =========================================================
# BUILD GRAPH
# =========================================================

graph = StateGraph(
    ResearchState
)
graph.add_node(
    "guardrail_agent",
    guardrail_agent
)


graph.add_node(
    "supervisor",
    supervisor_agent
)

graph.add_node(
    "guardrail_blocked",
    guardrail_blocked_agent
)

graph.add_node(
    "supervisor_error",
    supervisor_error_agent
)

graph.add_node(
    "web_research_agent",
    web_research_agent
)

graph.add_node(
    "paper_research_agent",
    paper_research_agent
)

graph.add_node(
    "news_research_agent",
    news_research_agent
)

graph.add_node(
    "youtube_research_agent",
    youtube_research_agent
)

graph.add_node(
    "research_complete",
    research_complete_agent
)

graph.add_node(
    "final_agent",
    final_agent
)

# graph.add_node(
#     "report_agent",
#     report_agent
# )




graph.add_edge(
    START,
    "guardrail_agent"
)


graph.add_conditional_edges(
    "guardrail_agent",
    route_after_guardrail,
    {
        "guardrail_blocked": "guardrail_blocked",
        "supervisor": "supervisor",
    },
)


graph.add_conditional_edges(
    "supervisor",
    route_from_supervisor,
    ROUTE_MAP,
)


# =========================================================
# PARALLEL RESEARCH → FAN-IN
# =========================================================

graph.add_edge(
    "web_research_agent",
    "research_complete"
)

graph.add_edge(
    "paper_research_agent",
    "research_complete"
)

graph.add_edge(
    "news_research_agent",
    "research_complete"
)

graph.add_edge(
    "youtube_research_agent",
    "research_complete"
)

graph.add_edge(
    "research_complete",
    "final_agent"
)

graph.add_edge(
    "final_agent",
    END
)


graph.add_edge(
    "guardrail_blocked",
    END
)

graph.add_edge(
    "supervisor_error",
    END
)


# =========================================================
# MONGODB CHECKPOINTER
# =========================================================

research_graph = None


def get_research_graph():

    global research_graph

    if research_graph is None:

        research_graph = graph.compile()

    return research_graph


# =========================================================
# SERIALIZE RESULT
# =========================================================

def _serialize_result(
    result: dict[str, Any],
):

    messages = result.get(
        "messages",
        []
    )

    last_message = (
        messages[-1].content
        if messages
        else ""
    )

    answer = (
        result.get("final_response")
        or last_message
    )

    return {

        "answer":
            answer,

        "web_results":
            result.get(
                "web_results",
                ""
            ),

        "paper_results":
            result.get(
                "paper_results",
                ""
            ),

        "news_results":
            result.get(
                "news_results",
                ""
            ),

        "draft_report": result.get("draft_report", ""),

        "analysis_route": result.get("analysis_route", ""),

        "context_token_estimate": result.get("context_token_estimate", 0),

        "selected_agents":
            result.get(
                "selected_agents",
                []
            ),

        "research_constraints":
            result.get(
                "research_constraints",
                {}
            ),

        "supervisor_reasoning":
            result.get(
                "supervisor_reasoning",
                ""
            ),

        "supervisor_error":
            result.get(
                "supervisor_error",
                ""
            ),

        "guardrail_allowed":
            result.get(
                "guardrail_allowed",
                True
            ),

        "guardrail_reason":
            result.get(
                "guardrail_reason",
                ""
            ),

        "llm_calls":
            result.get(
                "llm_calls",
                0
            ),
    }


# =========================================================
# FASTAPI - START RESEARCH
# =========================================================

def run_research_agent(
    user_input: str
):

    research_graph = (
        get_research_graph()
    )

    result = research_graph.invoke(
        {

            "messages": [
                HumanMessage(
                    content=user_input
                )
            ],

            "user_query":
                user_input,

            "guardrail_allowed":
                True,

            "guardrail_reason":
                "",

            "selected_agents":
                [],

            "research_constraints":
                empty_constraints(),

            "supervisor_reasoning":
                "",

            "supervisor_failed":
                False,

            "supervisor_error":
                "",

            "web_results":
                "",

            "paper_results":
                "",

            "news_results":
                "",
            
            "youtube_results": "",

            "draft_report":
                "",

            "combined_research_context":
                "",

            "analysis_context":
                "",

            "analysis_route":
                "",

            "context_token_estimate":
                0,

            "final_response":
                "",

            "llm_calls":
                0,
        },

    )

    return _serialize_result(
        result
    )
