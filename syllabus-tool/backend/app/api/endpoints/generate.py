from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.uploaded_file import UploadedFile
from app.services.storage import StorageService
from app.services.parser import parse_file
from app.schemas.generator import (
    GenerateRequest, FillTemplateRequest, FillTemplateResponse,
    FillTemplateJobResponse, FillTemplateStatusResponse,
    FillTemplateSection, FillTemplateResult,
    RegenerateSectionRequest, RegenerateSectionResponse,
)
from app.services.template_filler import (
    extract_numbered_paragraphs, build_llm_template_text,
    parse_llm_response, group_paragraphs_by_section, build_table_llm_prompt,
)
from app.schemas.syllabus import SyllabusData, CourseInfo, LearningGoal, ScheduleItem, Policies
from app.services.llm_factory import invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import logging
import uuid
import threading

logger = logging.getLogger(__name__)

router = APIRouter()

_LANGUAGE_NAMES = {"en": "English", "es": "Spanish (Español)"}

def _language_directive(lang: str) -> str:
    name = _LANGUAGE_NAMES.get(lang, lang)
    if lang == "en":
        return ""
    return (
        f"\n\nCRITICAL LANGUAGE REQUIREMENT: You MUST write ALL output content in {name}. "
        f"Every paragraph, heading, table cell, and description must be in {name}. "
        f"Only [P#] markers and JSON structure keys remain in English."
    )

# In-memory job store for async fill-template jobs
_fill_jobs: dict[str, dict] = {}

@router.post("/draft", response_model=SyllabusData)
async def generate_draft(request: GenerateRequest, db: Session = Depends(get_db)):
    try:
        reference_context = ""
        print(f"[GENERATE] title={request.course_title}, reference_file_id={request.reference_file_id}", flush=True)

        if request.reference_file_id:
            file_record = db.query(UploadedFile).filter(UploadedFile.id == request.reference_file_id).first()
            print(f"[GENERATE] Reference file record: {file_record.filename if file_record else 'NOT FOUND'}", flush=True)
            if file_record:
                try:
                    storage = StorageService()
                    content = storage.get_file(file_record.object_name)
                    print(f"[GENERATE] Storage returned content: {len(content) if content else 0} bytes", flush=True)
                    if content:
                        parsed_text = parse_file(file_record.filename, content)
                        print(f"[GENERATE] Parsed text length: {len(parsed_text)} chars", flush=True)
                        print(f"[GENERATE] First 300 chars: {parsed_text[:300]}", flush=True)
                        reference_context = f"\n\n--- REFERENCE DOCUMENT ({file_record.filename}) ---\n{parsed_text[:20000]}\n--- END REFERENCE DOCUMENT ---"
                except Exception as e:
                    print(f"[GENERATE] ERROR reading reference file: {e}", flush=True)
        else:
            print("[GENERATE] No reference_file_id provided", flush=True)

        system_prompt = """You are an expert curriculum designer. Your task is to generate a comprehensive syllabus draft based on the user's brief course description and optional reference material.

        You MUST return ONLY a valid JSON object matching the following structure. Do not include any markdown formatting like ```json ... ``` or potential chat text. Just the raw JSON string.

        Structure:
        {
            "course_info": {
                "title": "...",
                "code": "...",
                "instructor": "[Instructor Name]",
                "semester": "[Semester]",
                "description": "...",
                "format": "...",
                "materials": "..."
            },
            "learning_goals": [
                { "id": 1, "text": "..." }
            ],
            "schedule": [
                { "week": "1", "topic": "...", "assignment": "..." }
            ],
            "policies": {
                "academic_integrity": "...",
                "attendance": "...",
                "accessibility": "...",
                "late_work": "...",
                "grading": "..."
            },
            "custom_sections": {
                "Section Name": "Full section content as a string..."
            }
        }

        Requirements:
        1. **Learning Outcomes**: Generate 5-7 specific, measurable goals using Bloom's Taxonomy verbs.
        2. **Schedule**: Create a week-by-week schedule matching the user's specified duration. Ensure a logical progression from foundational to advanced topics.
        3. **Materials**: Recommend high-quality, relevant textbooks and resources in the 'course_info.materials' field.
        4. **custom_sections**: Use this field to capture ANY content from the reference document that does not fit the standard fields above. Examples: office hours, grading breakdown, course materials lists, university-specific policies, diversity statements, mental health resources, technology requirements, communication guidelines, prerequisites, instructor bio, TA info, etc. Preserve the original section names as keys and their full content as values. Do NOT discard any reference content.
        5. **CRITICAL — Reference Document**: If a reference document is provided, it is the PRIMARY SOURCE. Your job is to DIGITIZE and STRUCTURE it, not replace it:
           - Map standard sections (title, schedule, goals, policies) to the standard fields
           - Map ALL other sections to custom_sections — do NOT discard any content
           - Preserve the original wording, details, and specificity from the reference
           - Do NOT invent new topics or generic content when the reference provides specific content
           - If the reference has placeholder text (e.g., "[Course Title]"), keep the placeholders
        """ + _language_directive(request.language)

        if reference_context:
            user_prompt = f"""
        Course Title: {request.course_title}
        Target Audience: {request.target_audience}
        Duration: {request.duration}
        {reference_context}

        IMPORTANT: A reference document has been provided above. Use it as the primary source — extract its topics, schedule, learning goals, and policies. Structure the content into the required JSON format while preserving the original material as faithfully as possible.
        """
        else:
            user_prompt = f"""
        Course Title: {request.course_title}
        Target Audience: {request.target_audience}
        Duration: {request.duration}

        Please generate a full syllabus structure for this course from scratch.
        """

        print(f"[GENERATE] Sending to LLM: reference_context_length={len(reference_context)}, user_prompt_length={len(user_prompt)}", flush=True)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = invoke_llm(messages)
        content = response.content

        # cleanup code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
             content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Ensure IDs in learning goals
        for idx, goal in enumerate(data.get("learning_goals", [])):
            goal["id"] = idx + 1

        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to generate valid JSON content from AI.")
    except Exception as e:
        print(f"[GENERATE] ERROR: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Fill-template: chunked body + parallel table processing
# ---------------------------------------------------------------------------

def _format_syllabus_context(syllabus_content: dict) -> str:
    """Serialize saved syllabus content into a human-readable text block for LLM prompts."""
    lines = ["EXISTING SYLLABUS CONTENT (use as primary source):"]

    ci = syllabus_content.get("course_info", {})
    if ci:
        title = ci.get("title", "")
        code = ci.get("code", "")
        lines.append(f"Course: {title}" + (f" ({code})" if code else ""))
        if ci.get("instructor"):
            lines.append(f"Instructor: {ci['instructor']}")
        if ci.get("description"):
            lines.append(f"Description: {ci['description']}")
        if ci.get("semester"):
            lines.append(f"Semester: {ci['semester']}")
        if ci.get("format"):
            lines.append(f"Format: {ci['format']}")
        if ci.get("materials"):
            lines.append(f"Materials: {ci['materials']}")

    goals = syllabus_content.get("learning_goals", [])
    if goals:
        lines.append("\nLearning Goals:")
        for g in goals:
            text = g.get("text", "") if isinstance(g, dict) else str(g)
            gid = g.get("id", "") if isinstance(g, dict) else ""
            lines.append(f"  {gid}. {text}" if gid else f"  - {text}")

    schedule = syllabus_content.get("schedule", [])
    if schedule:
        lines.append("\nSchedule:")
        for s in schedule:
            if isinstance(s, dict):
                week = s.get("week", "")
                topic = s.get("topic", "")
                assignment = s.get("assignment", "")
                line = f"  Week {week}: {topic}"
                if assignment:
                    line += f" — {assignment}"
                lines.append(line)

    policies = syllabus_content.get("policies", {})
    if policies:
        lines.append("\nPolicies:")
        for key, val in policies.items():
            if val:
                label = key.replace("_", " ").title()
                lines.append(f"  {label}: {val}")

    custom = syllabus_content.get("custom_sections", {})
    if custom:
        lines.append("\nAdditional Sections:")
        for name, content in custom.items():
            lines.append(f"  {name}: {content}")

    return "\n".join(lines)


_BODY_SYSTEM_PROMPT_BASE = """You are an expert curriculum designer. You will receive a university syllabus TEMPLATE
with numbered paragraphs. Your task is to generate a COMPLETE, READY-TO-USE syllabus
for the given course by rewriting every paragraph.

RULES:
1. Output every paragraph with its original number: [P0], [P1], [P2], etc.
2. HEADINGS: Keep heading text that describes a real section (e.g., "Course Description",
   "Attendance Policy"). Remove meta-headings about template usage.
3. INSTRUCTION TEXT (text in brackets telling the instructor what to write): Replace
   entirely with real, substantive course content appropriate for the section.
4. EXAMPLE/SAMPLE TEXT: Adapt to be specific to the given course.
5. REQUIRED UNIVERSITY POLICY STATEMENTS: Keep verbatim — do not modify.
6. EMPTY paragraphs: Output as empty: [P5]
7. The final document must read as a polished, natural-language syllabus with NO
   leftover brackets, instructions, or placeholder tokens.
8. When EXISTING SYLLABUS CONTENT is provided, use it as the PRIMARY source for all content.
   Preserve the original learning goals, schedule topics, policies, and descriptions.
   Adapt formatting to match the template structure but keep the substance from the existing syllabus."""

def _body_system_prompt(lang: str = "en") -> str:
    return _BODY_SYSTEM_PROMPT_BASE + _language_directive(lang)


def _estimate_table_tokens(table_group: dict) -> int:
    """Estimate max_tokens needed for a table based on cell count."""
    n_cells = len(table_group["paragraphs"])
    if n_cells <= 32:
        return 2048
    elif n_cells <= 60:
        return 4096
    else:
        return 6144


_BODY_CHUNK_SIZE = 80  # paragraphs per LLM call

# ---------------------------------------------------------------------------
# Policy-section preservation — keywords that mark university-policy headings
# ---------------------------------------------------------------------------
_POLICY_KEYWORDS = [
    "policy", "policies", "política", "políticas",
    "academic integrity", "integridad académica",
    "accessibility", "accesibilidad",
    "disability", "discapacidad",
    "accommodation", "acomodación",
    "ada ", "title ix",
    "ferpa", "hipaa",
    "non-discrimination", "no discriminación",
    "sexual harassment", "acoso sexual",
    "mental health", "salud mental",
    "emergency", "emergencia",
    "compliance", "cumplimiento",
]


def _is_heading(paragraph: dict) -> bool:
    """Check if a paragraph is a heading (type == 'heading')."""
    return paragraph.get("type", "") == "heading"


def _split_policy_paragraphs(body_paragraphs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split body paragraphs into content vs policy.

    Walks paragraphs in order.  When a heading paragraph's text (lowercased)
    contains any policy keyword, that heading and all following paragraphs are
    marked as "policy" until the next heading is encountered.

    Returns (content_paragraphs, policy_paragraphs).
    """
    content: list[dict] = []
    policy: list[dict] = []
    in_policy = False

    for p in body_paragraphs:
        if _is_heading(p):
            text_lower = p["text"].lower()
            if any(kw in text_lower for kw in _POLICY_KEYWORDS):
                in_policy = True
            else:
                in_policy = False

        if in_policy:
            policy.append(p)
        else:
            content.append(p)

    return content, policy


def _fill_body_chunk(body_paragraphs: list[dict], course_info: dict) -> dict[int, str]:
    """Fill a single chunk of body paragraphs using the [P#] approach."""
    if not body_paragraphs:
        return {}

    template_text = build_llm_template_text(body_paragraphs)

    syllabus_block = ""
    instruction = "Generate a complete syllabus by rewriting each paragraph."
    if course_info.get("syllabus_content"):
        syllabus_block = "\n\n" + _format_syllabus_context(course_info["syllabus_content"])
        instruction = "Use the EXISTING SYLLABUS CONTENT as the primary source for rewriting each paragraph. Adapt the content to fit the template structure."

    user_prompt = f"""TEMPLATE PARAGRAPHS:
{template_text}

COURSE INFORMATION:
- Course Title: {course_info['course_title']}
- Target Audience: {course_info['target_audience']}
- Duration: {course_info['duration']}{syllabus_block}

{instruction} Output every paragraph with its [P#] number."""

    messages = [
        SystemMessage(content=_body_system_prompt(course_info.get("language", "en"))),
        HumanMessage(content=user_prompt),
    ]
    response = invoke_llm(messages, max_tokens=8192)
    return parse_llm_response(response.content, max(p["index"] for p in body_paragraphs) + 1)


def _fill_body_parallel(all_body_paragraphs: list[dict], course_info: dict) -> dict[int, str]:
    """Split body paragraphs into chunks and fill them in parallel."""
    if not all_body_paragraphs:
        return {}

    # Small enough for a single call — no chunking needed
    if len(all_body_paragraphs) <= _BODY_CHUNK_SIZE:
        return _fill_body_chunk(all_body_paragraphs, course_info)

    # Split into chunks
    chunks = [
        all_body_paragraphs[i:i + _BODY_CHUNK_SIZE]
        for i in range(0, len(all_body_paragraphs), _BODY_CHUNK_SIZE)
    ]
    print(f"[FILL-TEMPLATE] Splitting {len(all_body_paragraphs)} body paragraphs into {len(chunks)} chunks", flush=True)

    merged: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_fill_body_chunk, chunk, course_info): idx
            for idx, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            chunk_idx = futures[future]
            try:
                chunk_map = future.result()
                print(f"[FILL-TEMPLATE] Body chunk {chunk_idx + 1}/{len(chunks)} filled: {len(chunk_map)} replacements", flush=True)
                merged.update(chunk_map)
            except Exception as e:
                print(f"[FILL-TEMPLATE] Body chunk {chunk_idx + 1}/{len(chunks)} ERROR: {e}", flush=True)
    return merged


def _fill_table_chunk(table_group: dict, course_info: dict) -> dict[int, str]:
    """Fill a single table using a grid-structured prompt."""
    if not table_group["paragraphs"]:
        return {}

    grid_prompt = build_table_llm_prompt(table_group, course_info)
    max_idx = max(p["index"] for p in table_group["paragraphs"]) + 1

    headers = table_group.get("headers", [])
    header_hint = ", ".join(headers) if headers else "table data"

    lang = course_info.get("language", "en")
    system_prompt = f"""You are an expert curriculum designer filling in a syllabus table.
You will receive a table from a university syllabus template with numbered cells using [P#] markers.

RULES:
1. Output every cell with its original [P#] number.
2. Replace placeholder tokens (e.g., [[[[[##]]]]], [[[[[XX.XX]]]]]) with realistic values for the course.
3. Keep header cells that already have correct text — output them unchanged with their [P#] marker.
4. Use specific, realistic content appropriate for a university course on "{course_info['course_title']}".
5. Format: [P111] value
   One cell per line. Every [P#] from the input must appear in your output.""" + _language_directive(lang)

    syllabus_block = ""
    table_instruction = "Fill every cell in this table."
    if course_info.get("syllabus_content"):
        syllabus_block = "\n\n" + _format_syllabus_context(course_info["syllabus_content"])
        table_instruction = "Fill every cell in this table using values from the EXISTING SYLLABUS CONTENT (schedule entries, grading weights, etc.)."

    user_prompt = f"""{grid_prompt}

COURSE INFORMATION:
- Course Title: {course_info['course_title']}
- Target Audience: {course_info['target_audience']}
- Duration: {course_info['duration']}{syllabus_block}

{table_instruction} Output each cell as [P#] followed by its value, one per line."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    max_tokens = _estimate_table_tokens(table_group)
    response = invoke_llm(messages, max_tokens=max_tokens)
    return parse_llm_response(response.content, max_idx)


def _build_section(section_id: str, label: str, paragraphs: list[dict],
                   paragraph_map: dict[int, str], is_policy: bool = False) -> FillTemplateSection:
    """Build a FillTemplateSection from a group of paragraphs and the filled map."""
    indices = [p["index"] for p in paragraphs]
    original_text = "\n".join(p["text"] for p in paragraphs)
    lines = []
    for p in paragraphs:
        idx = p["index"]
        if idx in paragraph_map:
            lines.append(paragraph_map[idx])
        else:
            lines.append(p["text"])
    return FillTemplateSection(
        id=section_id,
        label=label,
        paragraph_indices=indices,
        filled_text="\n".join(lines),
        original_text=original_text,
        is_policy=is_policy,
    )


def _infer_table_label(table_group: dict) -> str:
    """Infer a human-readable label for a table from its headers."""
    headers = table_group.get("headers", [])
    if not headers:
        return f"Table {table_group['table_index']}"

    # Use first header as a hint, or join a few
    first = headers[0].strip()
    if len(headers) <= 4:
        return " / ".join(h.strip() for h in headers if h.strip()) or f"Table {table_group['table_index']}"
    return first or f"Table {table_group['table_index']}"


def _run_fill_template_job(job_id: str, file_object_name: str, reference_file_id: int,
                            course_title: str, target_audience: str, duration: str,
                            language: str = "en", syllabus_content: dict | None = None):
    """Background worker for fill-template LLM call — chunked body + parallel tables."""
    print(f"[FILL-TEMPLATE] Job {job_id} started, language={language}, has_syllabus={syllabus_content is not None}", flush=True)
    try:
        _fill_jobs[job_id]["status"] = "running"

        storage = StorageService()
        content = storage.get_file(file_object_name)
        print(f"[FILL-TEMPLATE] Storage returned {len(content) if content else 0} bytes", flush=True)
        if not content:
            _fill_jobs[job_id] = {"status": "failed", "error": "File content not found in storage"}
            return

        # 1. Extract paragraphs with table metadata
        numbered_paragraphs = extract_numbered_paragraphs(content)
        print(f"[FILL-TEMPLATE] Extracted {len(numbered_paragraphs)} paragraphs", flush=True)

        if not numbered_paragraphs:
            _fill_jobs[job_id] = {"status": "failed", "error": "No content found in the template document."}
            return

        # 2. Group into body + tables
        groups = group_paragraphs_by_section(numbered_paragraphs)
        print(f"[FILL-TEMPLATE] Body: {len(groups['body'])} paragraphs, Tables: {len(groups['tables'])}", flush=True)

        course_info = {
            "course_title": course_title,
            "target_audience": target_audience,
            "duration": duration,
            "language": language,
            "syllabus_content": syllabus_content,
        }

        # 3. Split body into content vs policy paragraphs
        content_paragraphs, policy_paragraphs = _split_policy_paragraphs(groups["body"])
        print(f"[FILL-TEMPLATE] Policy: {len(policy_paragraphs)} paragraphs preserved verbatim", flush=True)

        # 4. Fill content body — chunked in parallel for large templates
        print(f"[FILL-TEMPLATE] Filling body ({len(content_paragraphs)} content paragraphs)...", flush=True)
        merged_map: dict[int, str] = _fill_body_parallel(content_paragraphs, course_info)
        print(f"[FILL-TEMPLATE] Body filled: {len(merged_map)} replacements", flush=True)

        # 5. Copy policy paragraphs verbatim into merged_map
        for p in policy_paragraphs:
            merged_map[p["index"]] = p["text"]

        # 6. Fill tables in parallel
        if groups["tables"]:
            print(f"[FILL-TEMPLATE] Filling {len(groups['tables'])} table(s) in parallel...", flush=True)
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(_fill_table_chunk, tg, course_info): tg
                    for tg in groups["tables"]
                }
                for future in as_completed(futures):
                    tg = futures[future]
                    try:
                        table_map = future.result()
                        print(f"[FILL-TEMPLATE] Table {tg['table_index']} filled: {len(table_map)} replacements", flush=True)
                        merged_map.update(table_map)
                    except Exception as e:
                        print(f"[FILL-TEMPLATE] Table {tg['table_index']} ERROR: {e}", flush=True)
                        # Continue — partial fill is better than total failure

        # 6b. Post-process: remove any remaining template instruction markers [[[[[...]]]]]
        for p in numbered_paragraphs:
            idx = p["index"]
            original = p["text"]
            if "[[[[[" in original:
                current = merged_map.get(idx, original)
                if "[[[[[" in current:
                    merged_map[idx] = ""

        print(f"[FILL-TEMPLATE] Total replacements: {len(merged_map)}", flush=True)

        # 7. Build sections for frontend
        sections = []
        if content_paragraphs:
            sections.append(_build_section("body", "Course Content", content_paragraphs, merged_map))
        if policy_paragraphs:
            sections.append(_build_section("policy", "Policies (preserved)", policy_paragraphs, merged_map, is_policy=True))
        for tg in groups["tables"]:
            label = _infer_table_label(tg)
            sections.append(_build_section(f"table_{tg['table_index']}", label, tg["paragraphs"], merged_map))

        # 8. Build flat paragraph_map (string keys for JSON)
        paragraph_map = {str(k): v for k, v in merged_map.items()}

        _fill_jobs[job_id] = {
            "status": "completed",
            "result": FillTemplateResult(
                sections=sections,
                paragraph_map=paragraph_map,
                original_file_id=reference_file_id,
            ).model_dump(),
        }
    except Exception as e:
        print(f"[FILL-TEMPLATE] ERROR: {e}", flush=True)
        _fill_jobs[job_id] = {"status": "failed", "error": str(e)}


@router.post("/fill-template", response_model=FillTemplateJobResponse)
async def fill_template(request: FillTemplateRequest, db: Session = Depends(get_db)):
    """Kick off async fill-template job. Returns job_id immediately."""
    # Validate file exists before starting background work
    file_record = db.query(UploadedFile).filter(UploadedFile.id == request.reference_file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="Reference file not found")

    job_id = str(uuid.uuid4())
    _fill_jobs[job_id] = {"status": "pending"}

    def _safe_run():
        try:
            _run_fill_template_job(
                job_id, file_record.object_name, request.reference_file_id,
                request.course_title, request.target_audience, request.duration,
                request.language, request.syllabus_content,
            )
        except Exception as e:
            print(f"[FILL-TEMPLATE] THREAD CRASH: {e}", flush=True)
            import traceback
            traceback.print_exc()
            _fill_jobs[job_id] = {"status": "failed", "error": f"Thread crash: {e}"}

    thread = threading.Thread(target=_safe_run, daemon=True)
    thread.start()

    return FillTemplateJobResponse(job_id=job_id)


@router.get("/fill-template/status/{job_id}", response_model=FillTemplateStatusResponse)
async def fill_template_status(job_id: str):
    """Poll for fill-template job status."""
    job = _fill_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return FillTemplateStatusResponse(
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )


@router.post("/fill-template/regenerate-section", response_model=RegenerateSectionResponse)
async def regenerate_section(request: RegenerateSectionRequest, db: Session = Depends(get_db)):
    """Regenerate a single section of a filled template."""
    file_record = db.query(UploadedFile).filter(UploadedFile.id == request.reference_file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="Reference file not found")

    try:
        storage = StorageService()
        content = storage.get_file(file_record.object_name)
        if not content:
            raise HTTPException(status_code=404, detail="File content not found in storage")

        # Re-extract paragraphs to get the originals for this section
        numbered_paragraphs = extract_numbered_paragraphs(content)
        index_set = set(request.paragraph_indices)
        section_paragraphs = [p for p in numbered_paragraphs if p["index"] in index_set]

        if not section_paragraphs:
            raise HTTPException(status_code=400, detail="No matching paragraphs found for the given indices")

        course_info = {
            "course_title": request.course_title,
            "target_audience": request.target_audience,
            "duration": request.duration,
            "language": request.language,
        }

        # Determine if this is a table section or body section
        is_table = request.section_id.startswith("table_")

        if is_table:
            # Rebuild the table group structure for table regeneration
            groups = group_paragraphs_by_section(numbered_paragraphs)
            table_index_str = request.section_id.replace("table_", "")
            table_group = None
            for tg in groups["tables"]:
                if str(tg["table_index"]) == table_index_str:
                    table_group = tg
                    break
            if not table_group:
                raise HTTPException(status_code=400, detail="Table section not found in document")
            result_map = _fill_table_chunk(table_group, course_info)
        else:
            # Body section — use _fill_body_chunk with optional instruction
            if request.instruction:
                # Include the user instruction in the prompt
                template_text = build_llm_template_text(section_paragraphs)
                user_prompt = f"""TEMPLATE PARAGRAPHS:
{template_text}

COURSE INFORMATION:
- Course Title: {course_info['course_title']}
- Target Audience: {course_info['target_audience']}
- Duration: {course_info['duration']}

ADDITIONAL INSTRUCTION: {request.instruction}

Generate a complete syllabus by rewriting each paragraph. Output every paragraph with its [P#] number."""
                messages = [
                    SystemMessage(content=_body_system_prompt(course_info.get("language", "en"))),
                    HumanMessage(content=user_prompt),
                ]
                response = invoke_llm(messages, max_tokens=8192)
                result_map = parse_llm_response(response.content, max(p["index"] for p in section_paragraphs) + 1)
            else:
                result_map = _fill_body_chunk(section_paragraphs, course_info)

        # Build filled text from result
        lines = []
        for p in section_paragraphs:
            idx = p["index"]
            lines.append(result_map.get(idx, p["text"]))

        paragraph_map = {str(k): v for k, v in result_map.items() if k in index_set}

        print(f"[FILL-TEMPLATE] Section '{request.section_id}' regenerated: {len(result_map)} replacements", flush=True)

        return RegenerateSectionResponse(
            filled_text="\n".join(lines),
            paragraph_map=paragraph_map,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[FILL-TEMPLATE] Regenerate section ERROR: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
