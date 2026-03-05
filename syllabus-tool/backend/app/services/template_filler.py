import re
import io
import docx

PLACEHOLDER_PATTERN = re.compile(r'\[{1,3}[A-Z][A-Za-z0-9 _/,\'-]+\]{1,3}')


def detect_placeholders(text: str) -> list[str]:
    """Find all [Bracket Placeholders] in text. Returns unique list."""
    return list(set(PLACEHOLDER_PATTERN.findall(text)))


def apply_replacements_text(text: str, replacements: dict) -> str:
    """Replace all placeholders in plain text."""
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def fill_docx(file_content: bytes, replacements: dict) -> bytes:
    """Open a DOCX, replace placeholders in paragraphs + table cells, return modified bytes."""
    doc = docx.Document(io.BytesIO(file_content))

    for para in doc.paragraphs:
        for placeholder, value in replacements.items():
            if placeholder in para.text:
                _replace_in_paragraph(para, placeholder, value)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for placeholder, value in replacements.items():
                        if placeholder in para.text:
                            _replace_in_paragraph(para, placeholder, value)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _replace_in_paragraph(paragraph, placeholder, replacement):
    """Replace placeholder text across runs while preserving formatting."""
    full_text = paragraph.text
    if placeholder not in full_text:
        return
    new_text = full_text.replace(placeholder, replacement)
    # Clear all runs, set text on the first run (preserves first run's formatting)
    if paragraph.runs:
        paragraph.runs[0].text = new_text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = new_text
