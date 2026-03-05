import re
import io
import docx


def extract_numbered_paragraphs(file_content: bytes) -> list[dict]:
    """Walk the DOCX in document order (body paragraphs + table cells) and produce a flat numbered list."""
    doc = docx.Document(io.BytesIO(file_content))
    paragraphs = []
    index = 0

    # Body paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = para.style.name if para.style else ""
        para_type = "heading" if style_name.lower().startswith("heading") else "paragraph"
        paragraphs.append({
            "index": index,
            "text": para.text,
            "type": para_type,
            "location": "body",
        })
        index += 1

    # Table cell paragraphs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    style_name = para.style.name if para.style else ""
                    para_type = "heading" if style_name.lower().startswith("heading") else "paragraph"
                    paragraphs.append({
                        "index": index,
                        "text": para.text,
                        "type": para_type,
                        "location": "table",
                    })
                    index += 1

    return paragraphs


def build_llm_template_text(paragraphs: list[dict]) -> str:
    """Format the numbered paragraphs into a text block for the LLM."""
    lines = []
    for p in paragraphs:
        prefix = f"[P{p['index']}]"
        if p["type"] == "heading":
            prefix += " (heading)"
        if p["location"] == "table":
            prefix += " (table)"
        lines.append(f"{prefix} {p['text']}")
    return "\n".join(lines)


def parse_llm_response(response: str, total: int) -> dict[int, str]:
    """Parse the LLM's numbered output back into {paragraph_index: new_text}.

    Expected format: [P0] text here\n[P1] text here\n...
    If the LLM omits a paragraph number, that paragraph stays unchanged.
    """
    result = {}
    # Match [P<number>] followed by the rest of the line (greedy until next [P or end)
    # Use a pattern that captures multi-line content between markers
    pattern = re.compile(r'\[P(\d+)\]\s*(.*?)(?=\n\[P\d+\]|\Z)', re.DOTALL)
    for match in pattern.finditer(response):
        idx = int(match.group(1))
        text = match.group(2).strip()
        if idx < total:
            result[idx] = text
    return result


def fill_docx_by_index(file_content: bytes, paragraph_map: dict[int, str]) -> bytes:
    """Walk the original DOCX in the same order as extract_numbered_paragraphs.

    For each paragraph at index i, if i is in paragraph_map, replace the paragraph's
    text while preserving the first run's formatting.
    """
    doc = docx.Document(io.BytesIO(file_content))
    index = 0

    # Body paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if index in paragraph_map:
            _set_paragraph_text(para, paragraph_map[index])
        index += 1

    # Table cell paragraphs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    if index in paragraph_map:
                        _set_paragraph_text(para, paragraph_map[index])
                    index += 1

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _set_paragraph_text(paragraph, new_text: str):
    """Replace a paragraph's text, preserving the first run's formatting."""
    if paragraph.runs:
        paragraph.runs[0].text = new_text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = new_text
