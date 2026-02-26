"""
Shared LLM utilities for all workflows.

Provides:
- LLM initialization with token tracking
- Cost calculation for OpenAI and Anthropic
- Token counting utilities
- Rolling summary for token control
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from api.core.config import get_settings

logger = logging.getLogger(__name__)


# Cost per 1M tokens (as of Jan 2025)
COST_PER_1M_TOKENS = {
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},  # Fastest for voice
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
}

# Default token limits
DEFAULT_MAX_INPUT_TOKENS = 8000
DEFAULT_MAX_OUTPUT_TOKENS = 4000


@dataclass
class LLMMetrics:
    """Metrics from LLM invocation."""
    model_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    execution_time_seconds: float = 0.0
    used_fallback: bool = False
    error_message: Optional[str] = None
    retry_count: int = 0  # Number of retries for this invocation


@dataclass
class LLMResponse:
    """Response from LLM invocation with metrics."""
    content: Optional[str] = None
    metrics: LLMMetrics = field(default_factory=LLMMetrics)
    success: bool = False


def get_llm_with_tracking():
    """
    Get the appropriate LLM based on available API keys.

    Returns:
        Tuple of (llm_instance, model_name) or (None, None) if no keys available
    """
    settings = get_settings()

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.7,
        ), "gpt-4o-mini"
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            api_key=settings.anthropic_api_key,
            temperature=0.7,
        ), "claude-3-haiku-20240307"
    else:
        return None, None


def get_fast_voice_llm():
    """
    Get a speed-optimized LLM for voice responses.

    Uses lower temperature (0.3) for faster, more deterministic responses.
    max_tokens=500 to accommodate structured JSON responses from extraction.

    Returns:
        Tuple of (llm_instance, model_name) or (None, None) if no keys available
    """
    settings = get_settings()

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0.3,  # Lower for faster, more deterministic responses
            max_tokens=500,   # Increased for structured JSON responses
        ), "gpt-4o-mini"
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
            max_tokens=500,   # Increased for structured JSON responses
        ), "claude-3-haiku-20240307"
    else:
        return None, None


def get_turbo_voice_llm():
    """
    Ultra-fast LLM for voice - uses gpt-3.5-turbo for maximum speed.

    gpt-3.5-turbo is ~2-3x faster than gpt-4o-mini for simple classification tasks.
    Uses very low temperature (0.1) and minimal tokens (150) for speed.

    Returns:
        Tuple of (llm_instance, model_name) or (None, None) if no keys available
    """
    settings = get_settings()

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-3.5-turbo",
            api_key=settings.openai_api_key,
            temperature=0.1,  # Very low for deterministic, fast responses
            max_tokens=150,   # Minimal tokens for quick classification
        ), "gpt-3.5-turbo"
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-3-haiku-20240307",
            api_key=settings.anthropic_api_key,
            temperature=0.1,
            max_tokens=150,
        ), "claude-3-haiku-20240307"
    else:
        return None, None


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost in USD for token usage."""
    if model_name not in COST_PER_1M_TOKENS:
        # Default to gpt-4o-mini pricing if unknown
        model_name = "gpt-4o-mini"

    costs = COST_PER_1M_TOKENS[model_name]
    input_cost = (prompt_tokens / 1_000_000) * costs["input"]
    output_cost = (completion_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Rough estimate: ~4 characters per token for English text.
    """
    if not text:
        return 0
    return len(text) // 4


def invoke_llm_with_metrics(llm, prompt: str, model_name: str, json_mode: bool = False) -> LLMResponse:
    """
    Invoke LLM and return response with metrics.

    Args:
        llm: LangChain LLM instance
        prompt: The prompt to send
        model_name: Name of the model for cost calculation
        json_mode: If True, enforce JSON output format (OpenAI only)

    Returns:
        LLMResponse with content and metrics
    """
    metrics = LLMMetrics(model_name=model_name)
    start_time = time.time()

    try:
        # Use JSON mode if requested (OpenAI only)
        if json_mode and "gpt" in model_name.lower():
            # Bind response_format for JSON mode
            llm_with_json = llm.bind(response_format={"type": "json_object"})
            response = llm_with_json.invoke(prompt)
        else:
            response = llm.invoke(prompt)
        metrics.execution_time_seconds = round(time.time() - start_time, 3)

        # Extract token usage if available
        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            # OpenAI format
            if 'token_usage' in metadata:
                usage = metadata['token_usage']
                metrics.prompt_tokens = usage.get('prompt_tokens', 0)
                metrics.completion_tokens = usage.get('completion_tokens', 0)
                metrics.total_tokens = usage.get('total_tokens', 0)
            # Anthropic format
            elif 'usage' in metadata:
                usage = metadata['usage']
                metrics.prompt_tokens = usage.get('input_tokens', 0)
                metrics.completion_tokens = usage.get('output_tokens', 0)
                metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens

        # If no token info from API, estimate
        if metrics.total_tokens == 0:
            metrics.prompt_tokens = estimate_tokens(prompt)
            metrics.completion_tokens = estimate_tokens(response.content) if response.content else 0
            metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens

        # Calculate cost
        metrics.estimated_cost_usd = calculate_cost(
            model_name, metrics.prompt_tokens, metrics.completion_tokens
        )

        return LLMResponse(
            content=response.content,
            metrics=metrics,
            success=True
        )

    except Exception as e:
        metrics.execution_time_seconds = round(time.time() - start_time, 3)
        metrics.error_message = str(e)
        logger.exception(f"LLM invocation failed: {e}")
        return LLMResponse(
            content=None,
            metrics=metrics,
            success=False
        )


def invoke_llm_with_retry(
    llm,
    prompt: str,
    model_name: str,
    max_retries: int = 2,
    retry_delay: float = 1.0,
) -> LLMResponse:
    """
    Invoke LLM with automatic retry on failure.

    Args:
        llm: LangChain LLM instance
        prompt: The prompt to send
        model_name: Name of the model for cost calculation
        max_retries: Maximum number of retry attempts (default: 2)
        retry_delay: Delay between retries in seconds (default: 1.0)

    Returns:
        LLMResponse with content, metrics, and retry count
    """
    retry_count = 0

    for attempt in range(max_retries + 1):
        response = invoke_llm_with_metrics(llm, prompt, model_name)

        if response.success:
            response.metrics.retry_count = retry_count
            return response

        # Failed - increment retry count and try again (unless last attempt)
        if attempt < max_retries:
            retry_count += 1
            logger.warning(f"LLM call failed, retrying ({retry_count}/{max_retries})...")
            time.sleep(retry_delay)

    # All retries exhausted
    response.metrics.retry_count = retry_count
    return response


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response:
        return None

    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nResponse: {text[:500]}")
        return None


# ============ Rolling Summary for Token Control ============

@dataclass
class RollingSummaryResult:
    """Result from rolling summary creation."""
    recent_posts: List[Dict[str, Any]]
    older_summary_text: Optional[str] = None
    summarization_applied: bool = False
    posts_summarized: int = 0
    total_posts: int = 0
    recent_posts_count: int = 0


def create_rolling_summary(
    posts: List[Dict[str, Any]],
    max_posts: int = 20,
    summarize_older: bool = True,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Create a rolling summary of posts to control token usage.

    If there are more than max_posts, keeps the most recent max_posts
    and summarizes the older ones.

    Args:
        posts: List of post dictionaries
        max_posts: Maximum number of full posts to include
        summarize_older: Whether to summarize older posts

    Returns:
        Tuple of (recent_posts, older_summary_text)
    """
    if len(posts) <= max_posts:
        return posts, None

    recent_posts = posts[-max_posts:]
    older_posts = posts[:-max_posts]

    if not summarize_older:
        return recent_posts, None

    # Create summary of older posts
    older_summary_parts = []
    older_summary_parts.append(f"[Earlier discussion: {len(older_posts)} posts summarized]")

    # Extract key points from older posts
    student_count = sum(1 for p in older_posts if p.get("author_role") == "student")
    instructor_count = sum(1 for p in older_posts if p.get("author_role") == "instructor")
    older_summary_parts.append(f"  - {student_count} student posts, {instructor_count} instructor posts")

    # Include pinned posts fully
    pinned = [p for p in older_posts if p.get("pinned")]
    if pinned:
        older_summary_parts.append("  - Key pinned posts:")
        for p in pinned[:3]:
            content_preview = p["content"][:100] + "..." if len(p["content"]) > 100 else p["content"]
            older_summary_parts.append(f"    [Post #{p['post_id']}]: {content_preview}")

    # Include high-quality posts
    high_quality = [p for p in older_posts if "high-quality" in (p.get("labels") or [])]
    if high_quality and high_quality != pinned:
        older_summary_parts.append("  - High-quality contributions:")
        for p in high_quality[:2]:
            content_preview = p["content"][:100] + "..." if len(p["content"]) > 100 else p["content"]
            older_summary_parts.append(f"    [Post #{p['post_id']}]: {content_preview}")

    older_summary = "\n".join(older_summary_parts)
    return recent_posts, older_summary


def create_rolling_summary_with_metadata(
    posts: List[Dict[str, Any]],
    max_posts: int = 20,
    summarize_older: bool = True,
) -> RollingSummaryResult:
    """
    Create a rolling summary of posts with full metadata.

    Enhanced version that returns metadata for explainability and QA.

    Args:
        posts: List of post dictionaries
        max_posts: Maximum number of full posts to include
        summarize_older: Whether to summarize older posts

    Returns:
        RollingSummaryResult with posts, summary text, and metadata
    """
    total_posts = len(posts)

    if total_posts <= max_posts:
        return RollingSummaryResult(
            recent_posts=posts,
            older_summary_text=None,
            summarization_applied=False,
            posts_summarized=0,
            total_posts=total_posts,
            recent_posts_count=total_posts,
        )

    recent_posts, older_summary = create_rolling_summary(posts, max_posts, summarize_older)
    posts_summarized = total_posts - len(recent_posts)

    return RollingSummaryResult(
        recent_posts=recent_posts,
        older_summary_text=older_summary,
        summarization_applied=True,
        posts_summarized=posts_summarized,
        total_posts=total_posts,
        recent_posts_count=len(recent_posts),
    )


def chunk_posts_for_analysis(
    posts: List[Dict[str, Any]],
    chunk_size: int = 15,
) -> List[List[Dict[str, Any]]]:
    """
    Split posts into chunks for batch analysis.

    Args:
        posts: List of post dictionaries
        chunk_size: Maximum posts per chunk

    Returns:
        List of post chunks
    """
    if not posts:
        return []

    chunks = []
    for i in range(0, len(posts), chunk_size):
        chunks.append(posts[i:i + chunk_size])
    return chunks


def format_posts_for_prompt(posts: List[Dict[str, Any]]) -> str:
    """Format posts for inclusion in prompts."""
    if not posts:
        return "No posts in this discussion."

    lines = []
    for p in posts:
        role_label = "INSTRUCTOR" if p.get("author_role") == "instructor" else "STUDENT"
        pinned = " [PINNED]" if p.get("pinned") else ""
        labels = f" [{', '.join(p.get('labels', []))}]" if p.get("labels") else ""
        lines.append(f"[Post #{p['post_id']}] ({role_label}{pinned}{labels}) {p.get('timestamp', '')}")
        lines.append(f"  {p['content']}")
        lines.append("")
    return "\n".join(lines)


# ============ Aggregation Helpers ============

def aggregate_metrics(metrics_list: List[LLMMetrics]) -> LLMMetrics:
    """Aggregate multiple LLM metrics into one."""
    if not metrics_list:
        return LLMMetrics()

    return LLMMetrics(
        model_name=metrics_list[0].model_name,
        prompt_tokens=sum(m.prompt_tokens for m in metrics_list),
        completion_tokens=sum(m.completion_tokens for m in metrics_list),
        total_tokens=sum(m.total_tokens for m in metrics_list),
        estimated_cost_usd=sum(m.estimated_cost_usd for m in metrics_list),
        execution_time_seconds=sum(m.execution_time_seconds for m in metrics_list),
        used_fallback=any(m.used_fallback for m in metrics_list),
        error_message=next((m.error_message for m in metrics_list if m.error_message), None),
        retry_count=sum(m.retry_count for m in metrics_list),  # Total retries across all calls
    )
