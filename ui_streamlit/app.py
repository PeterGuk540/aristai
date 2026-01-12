"""
AristAI Streamlit UI

Minimal MVP interface for:
- Course setup and syllabus input
- Session management
- Forum posting
- Triggering workflows
- Viewing outputs
"""
import os
import streamlit as st
import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="AristAI", page_icon="🎓", layout="wide")

# Sidebar navigation
st.sidebar.title("AristAI")
page = st.sidebar.radio(
    "Navigation",
    ["Courses", "Sessions", "Forum", "Reports"],
)


def api_get(endpoint: str):
    """Make GET request to API."""
    try:
        response = httpx.get(f"{API_URL}/api{endpoint}", timeout=30.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, data: dict = None):
    """Make POST request to API. If data is None or empty, send no body."""
    try:
        if data:
            response = httpx.post(f"{API_URL}/api{endpoint}", json=data, timeout=30.0)
        else:
            response = httpx.post(f"{API_URL}/api{endpoint}", timeout=30.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        st.error(f"API Error: {e}")
        return None


def api_patch(endpoint: str, data: dict):
    """Make PATCH request to API."""
    try:
        response = httpx.patch(f"{API_URL}/api{endpoint}", json=data, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        st.error(f"API Error: {e}")
        return None


def format_timestamp(ts) -> str:
    """Safely format a timestamp for display."""
    if not ts or not isinstance(ts, str):
        return "N/A"
    return ts[:19].replace("T", " ")


# ============ COURSES PAGE ============
if page == "Courses":
    st.title("Course Management")

    # Create new course
    st.subheader("Create New Course")
    with st.form("create_course"):
        title = st.text_input("Course Title")
        syllabus = st.text_area("Syllabus", height=200)
        objectives = st.text_area("Learning Objectives (one per line)")

        if st.form_submit_button("Create Course"):
            objectives_list = [o.strip() for o in objectives.split("\n") if o.strip()]
            result = api_post("/courses/", {
                "title": title,
                "syllabus_text": syllabus,
                "objectives_json": objectives_list,
            })
            if result:
                st.success(f"Course created with ID: {result['id']}")

    # List courses
    st.subheader("Existing Courses")
    courses = api_get("/courses/")
    if courses:
        for course in courses:
            with st.expander(f"📚 {course['title']} (ID: {course['id']})"):
                st.write(f"**Syllabus:** {(course.get('syllabus_text') or 'N/A')[:500]}...")
                if st.button(f"Generate Session Plans", key=f"gen_{course['id']}"):
                    result = api_post(f"/courses/{course['id']}/generate_plans")
                    if result:
                        st.info(f"Task queued: {result['task_id']}")


# ============ SESSIONS PAGE ============
elif page == "Sessions":
    st.title("Session Management")

    # Select course
    courses = api_get("/courses/") or []
    course_options = {f"{c['title']} (ID: {c['id']})": c['id'] for c in courses}

    if course_options:
        selected = st.selectbox("Select Course", list(course_options.keys()))
        course_id = course_options[selected]

        # Create session
        st.subheader("Create New Session")
        with st.form("create_session"):
            session_title = st.text_input("Session Title")
            if st.form_submit_button("Create Session"):
                result = api_post("/sessions/", {
                    "course_id": course_id,
                    "title": session_title,
                })
                if result:
                    st.success(f"Session created with ID: {result['id']}")

        # Fetch session by ID
        st.subheader("View & Manage Session")
        fetch_session_id = st.number_input("Session ID to fetch", min_value=1, step=1, key="fetch_session")
        if st.button("Fetch Session"):
            st.session_state["current_session"] = api_get(f"/sessions/{fetch_session_id}")

        # Display session details if fetched
        if "current_session" in st.session_state and st.session_state["current_session"]:
            session = st.session_state["current_session"]
            st.write(f"**Title:** {session['title']}")

            # Status badge with color
            status = session['status']
            status_colors = {
                "draft": "gray",
                "scheduled": "blue",
                "live": "green",
                "completed": "orange",
            }
            st.write(f"**Status:** :{status_colors.get(status, 'gray')}[{status.upper()}]")
            st.write(f"**Created:** {format_timestamp(session.get('created_at'))}")

            # Session status controls
            st.subheader("Session Status")
            status_col1, status_col2, status_col3, status_col4 = st.columns(4)

            with status_col1:
                if status != "draft":
                    if st.button("Set to Draft", key="status_draft"):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "draft"})
                        if result:
                            st.session_state["current_session"] = result
                            st.success("Status updated to Draft")
                            st.rerun()

            with status_col2:
                if status in ["draft"]:
                    if st.button("Schedule", key="status_scheduled"):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "scheduled"})
                        if result:
                            st.session_state["current_session"] = result
                            st.success("Status updated to Scheduled")
                            st.rerun()

            with status_col3:
                if status in ["draft", "scheduled"]:
                    if st.button("Go Live", key="status_live"):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "live"})
                        if result:
                            st.session_state["current_session"] = result
                            st.success("Session is now LIVE!")
                            st.rerun()

            with status_col4:
                if status == "live":
                    if st.button("Complete Session", key="status_completed"):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "completed"})
                        if result:
                            st.session_state["current_session"] = result
                            st.success("Session completed")
                            st.rerun()

            # Show session plan
            if session.get('plan_json'):
                with st.expander("View Session Plan"):
                    st.json(session['plan_json'])
    else:
        st.warning("No courses found. Create a course first.")


# ============ FORUM PAGE ============
elif page == "Forum":
    st.title("Discussion Forum")

    session_id = st.number_input("Session ID", min_value=1, step=1)

    if session_id:
        # Post case (instructor)
        st.subheader("Post Case (Instructor)")
        with st.form("post_case"):
            case_prompt = st.text_area("Case/Problem Statement")
            if st.form_submit_button("Post Case"):
                result = api_post(f"/sessions/{session_id}/case", {
                    "prompt": case_prompt,
                })
                if result:
                    st.success("Case posted!")

        # Post reply (student/instructor)
        st.subheader("Post Reply")
        with st.form("post_reply"):
            user_id = st.number_input("Your User ID", min_value=1, step=1, value=1)
            content = st.text_area("Your Response")
            if st.form_submit_button("Submit Post"):
                result = api_post(f"/posts/session/{session_id}", {
                    "user_id": user_id,
                    "content": content,
                })
                if result:
                    st.success("Post submitted!")

        # View posts with moderation controls
        st.subheader("Discussion Thread")
        if st.button("Refresh Posts"):
            st.rerun()

        posts = api_get(f"/posts/session/{session_id}")
        if posts:
            # Show pinned posts first
            pinned_posts = [p for p in posts if p.get('pinned')]
            unpinned_posts = [p for p in posts if not p.get('pinned')]

            for post in pinned_posts + unpinned_posts:
                post_id = post['id']
                is_pinned = post.get('pinned', False)
                labels = post.get('labels_json') or []

                # Post header with badges
                header_parts = [f"**User {post['user_id']}**"]
                if is_pinned:
                    header_parts.append("📌 PINNED")
                if "high-quality" in labels:
                    header_parts.append("⭐ High Quality")
                if "needs-clarification" in labels:
                    header_parts.append("❓ Needs Clarification")
                header_parts.append(f"({format_timestamp(post.get('created_at'))})")

                st.markdown(" | ".join(header_parts))
                st.write(post['content'])

                # Moderation controls (expandable)
                with st.expander(f"Moderate Post #{post_id}", expanded=False):
                    mod_col1, mod_col2 = st.columns(2)

                    with mod_col1:
                        # Pin/Unpin button
                        pin_label = "Unpin" if is_pinned else "Pin"
                        if st.button(f"{pin_label}", key=f"pin_{post_id}"):
                            result = api_post(f"/posts/{post_id}/pin", {"pinned": not is_pinned})
                            if result:
                                st.success(f"Post {'unpinned' if is_pinned else 'pinned'}!")
                                st.rerun()

                    with mod_col2:
                        # Quick label buttons
                        if st.button("Mark High Quality", key=f"hq_{post_id}"):
                            new_labels = list(set(labels + ["high-quality"]))
                            if "needs-clarification" in new_labels:
                                new_labels.remove("needs-clarification")
                            result = api_post(f"/posts/{post_id}/label", {"labels": new_labels})
                            if result:
                                st.success("Marked as high quality!")
                                st.rerun()

                        if st.button("Needs Clarification", key=f"nc_{post_id}"):
                            new_labels = list(set(labels + ["needs-clarification"]))
                            if "high-quality" in new_labels:
                                new_labels.remove("high-quality")
                            result = api_post(f"/posts/{post_id}/label", {"labels": new_labels})
                            if result:
                                st.success("Marked as needs clarification!")
                                st.rerun()

                        if labels and st.button("Clear Labels", key=f"cl_{post_id}"):
                            result = api_post(f"/posts/{post_id}/label", {"labels": []})
                            if result:
                                st.success("Labels cleared!")
                                st.rerun()

                st.divider()
        else:
            st.info("No posts yet.")

        # Live copilot
        st.subheader("Instructor Copilot")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start Live Copilot"):
                result = api_post(f"/sessions/{session_id}/start_live_copilot")
                if result:
                    st.info(f"Copilot started: {result['task_id']}")
        with col2:
            if st.button("View Interventions"):
                interventions = api_get(f"/sessions/{session_id}/interventions")
                if interventions:
                    for i in interventions:
                        st.json(i['suggestion_json'])
                else:
                    st.info("No interventions yet.")


# ============ REPORTS PAGE ============
elif page == "Reports":
    st.title("Feedback Reports")

    session_id = st.number_input("Session ID", min_value=1, step=1, key="report_session")

    if session_id:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Generate Report"):
                result = api_post(f"/reports/session/{session_id}/generate")
                if result:
                    st.info(f"Report generation queued: {result['task_id']}")

        with col2:
            if st.button("View Latest Report"):
                report = api_get(f"/reports/session/{session_id}")
                if report:
                    st.subheader(f"Report {report['version']}")
                    st.markdown(report.get('report_md') or 'No markdown content')

                    with st.expander("View JSON"):
                        st.json(report.get('report_json') or {})
