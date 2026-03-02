"""Maps syllabus-tool content schema to forum course schema."""


def syllabus_to_forum_course(content: dict, title: str) -> dict:
    """Convert syllabus-tool content dict into forum CourseCreate fields.

    Returns dict with: title, syllabus_text, syllabus_json, objectives_json
    """
    course_info = content.get("course_info", {})

    # Map learning_goals: [{id, text}] → str[]
    raw_goals = content.get("learning_goals", [])
    objectives = []
    for g in raw_goals:
        if isinstance(g, str):
            objectives.append(g)
        elif isinstance(g, dict) and g.get("text"):
            objectives.append(g["text"])

    # Map schedule: week str → int
    raw_schedule = content.get("schedule", [])
    forum_schedule = []
    for idx, item in enumerate(raw_schedule):
        week_str = str(item.get("week", idx + 1))
        try:
            week_int = int(week_str)
        except ValueError:
            week_int = idx + 1
        forum_schedule.append({
            "week": week_int,
            "module": item.get("topic", ""),
            "topic": item.get("topic", ""),
        })

    # Extract learning_resources from course_info.materials
    materials_raw = course_info.get("materials", "")
    learning_resources = []
    if materials_raw:
        lines = [l.strip() for l in materials_raw.split("\n") if l.strip()]
        learning_resources = lines if lines else [materials_raw]

    policies = content.get("policies", {})

    # Build forum-schema syllabus_json
    syllabus_json = {
        "course_info": {
            "title": course_info.get("title", title),
            "code": course_info.get("code"),
            "semester": course_info.get("semester"),
            "instructor": course_info.get("instructor"),
            "description": course_info.get("description", ""),
            "prerequisites": course_info.get("prerequisites"),
        },
        "learning_goals": objectives,
        "learning_resources": learning_resources,
        "schedule": forum_schedule,
        "policies": {
            "grading": policies.get("grading", ""),
            "attendance": policies.get("attendance", ""),
            "academic_integrity": policies.get("academic_integrity", ""),
            "accessibility": policies.get("accessibility", ""),
            "office_hours": None,
        },
    }

    # Build human-readable syllabus text
    lines = []
    if course_info.get("title"):
        lines.append(f"Course: {course_info['title']}")
    if course_info.get("description"):
        lines.append(f"\n{course_info['description']}")
    if objectives:
        lines.append("\nLearning Goals:")
        for g in objectives:
            lines.append(f"- {g}")
    if raw_schedule:
        lines.append("\nSchedule:")
        for item in raw_schedule:
            assignment = f" - {item['assignment']}" if item.get("assignment") else ""
            lines.append(f"Week {item.get('week', '?')}: {item.get('topic', '')}{assignment}")
    syllabus_text = "\n".join(lines)

    return {
        "title": title,
        "syllabus_text": syllabus_text,
        "syllabus_json": syllabus_json,
        "objectives_json": objectives,
    }
