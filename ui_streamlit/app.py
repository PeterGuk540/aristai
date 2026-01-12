"""
AristAI Streamlit UI

Enhanced interface for:
- Course setup: paste syllabus + objectives, trigger plan generation, view plans
- Session management: view/post case, post messages, view thread, status control
- Instructor console: live copilot suggestions, polls management
- Reports: generate, view, export markdown, poll results, observability panel
"""
import os
import streamlit as st
import httpx
from datetime import datetime

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="AristAI", page_icon="🎓", layout="wide")

# Sidebar navigation
st.sidebar.title("AristAI")
st.sidebar.markdown("AI-Assisted Classroom Forum")
page = st.sidebar.radio(
    "Navigation",
    ["Courses", "Sessions", "Forum", "Instructor Console", "Reports"],
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Quick Links**")
st.sidebar.markdown(f"[API Docs]({API_URL}/docs)")


# ============ API HELPERS ============

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
    """Make POST request to API."""
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


def get_status_color(status: str) -> str:
    """Get color for session status."""
    return {
        "draft": "gray",
        "scheduled": "blue",
        "live": "green",
        "completed": "orange",
    }.get(status, "gray")


# ============ COURSES PAGE ============
if page == "Courses":
    st.title("Course Management")

    tab1, tab2 = st.tabs(["Create Course", "Existing Courses"])

    with tab1:
        st.subheader("Create New Course")
        st.markdown("Paste your syllabus and learning objectives to get started.")

        with st.form("create_course"):
            title = st.text_input("Course Title", placeholder="e.g., Introduction to Machine Learning")

            syllabus = st.text_area(
                "Syllabus",
                height=250,
                placeholder="Paste your full syllabus here...\n\nWeek 1: Introduction\nWeek 2: Supervised Learning\n...",
                help="Include weekly topics, readings, and course structure"
            )

            objectives = st.text_area(
                "Learning Objectives (one per line)",
                height=150,
                placeholder="Understand fundamental ML concepts\nApply supervised learning algorithms\nEvaluate model performance",
                help="These objectives will guide AI-generated session plans"
            )

            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Create Course", use_container_width=True)
            with col2:
                generate_plans = st.form_submit_button("Create & Generate Plans", use_container_width=True)

            if submitted or generate_plans:
                if not title:
                    st.error("Course title is required")
                elif not syllabus:
                    st.error("Syllabus is required")
                else:
                    objectives_list = [o.strip() for o in objectives.split("\n") if o.strip()]
                    result = api_post("/courses/", {
                        "title": title,
                        "syllabus_text": syllabus,
                        "objectives_json": objectives_list,
                    })
                    if result:
                        st.success(f"Course created with ID: {result['id']}")
                        if generate_plans:
                            plan_result = api_post(f"/courses/{result['id']}/generate_plans")
                            if plan_result:
                                st.info(f"Plan generation queued! Task ID: {plan_result['task_id']}")
                                st.markdown("Go to **Sessions** page to view generated plans.")

    with tab2:
        st.subheader("Existing Courses")

        if st.button("Refresh Courses"):
            st.rerun()

        courses = api_get("/courses/")
        if courses:
            for course in courses:
                with st.expander(f"📚 {course['title']} (ID: {course['id']})", expanded=False):
                    # Course details
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown("**Syllabus Preview:**")
                        syllabus_text = course.get('syllabus_text') or 'N/A'
                        st.text(syllabus_text[:500] + ("..." if len(syllabus_text) > 500 else ""))

                        objectives = course.get('objectives_json') or []
                        if objectives:
                            st.markdown("**Learning Objectives:**")
                            for obj in objectives[:5]:
                                st.markdown(f"- {obj}")
                            if len(objectives) > 5:
                                st.markdown(f"_...and {len(objectives) - 5} more_")

                    with col2:
                        st.markdown("**Actions:**")
                        if st.button("Generate Session Plans", key=f"gen_{course['id']}"):
                            result = api_post(f"/courses/{course['id']}/generate_plans")
                            if result:
                                st.success(f"Task queued: {result['task_id']}")

                        st.markdown(f"**Created:** {format_timestamp(course.get('created_at'))}")
        else:
            st.info("No courses found. Create one above!")


# ============ SESSIONS PAGE ============
elif page == "Sessions":
    st.title("Session Management")

    # Course selector
    courses = api_get("/courses/") or []
    if not courses:
        st.warning("No courses found. Create a course first in the Courses page.")
        st.stop()

    course_options = {f"{c['title']} (ID: {c['id']})": c['id'] for c in courses}
    selected_course = st.selectbox("Select Course", list(course_options.keys()))
    course_id = course_options[selected_course]

    tab1, tab2, tab3 = st.tabs(["View Sessions", "Create Session", "Manage Session"])

    with tab1:
        st.subheader("Course Sessions")
        st.markdown("_Sessions are generated from the course syllabus or created manually._")

        # Get all sessions for this course (we need an endpoint for this - use session fetch for now)
        session_id_input = st.number_input("Enter Session ID to view", min_value=1, step=1, key="view_session_id")

        if st.button("Load Session", key="load_session"):
            session = api_get(f"/sessions/{session_id_input}")
            if session:
                st.session_state["view_session"] = session

        if "view_session" in st.session_state and st.session_state["view_session"]:
            session = st.session_state["view_session"]

            # Session header
            status = session['status']
            st.markdown(f"### {session['title']}")
            st.markdown(f"**Status:** :{get_status_color(status)}[{status.upper()}] | **Created:** {format_timestamp(session.get('created_at'))}")

            # Session plan
            if session.get('plan_json'):
                plan = session['plan_json']

                col1, col2 = st.columns(2)
                with col1:
                    if plan.get('topics'):
                        st.markdown("**Topics:**")
                        for topic in plan.get('topics', []):
                            st.markdown(f"- {topic}")

                    if plan.get('goals'):
                        st.markdown("**Goals:**")
                        goals = plan['goals'] if isinstance(plan['goals'], list) else [plan['goals']]
                        for goal in goals:
                            st.markdown(f"- {goal}")

                with col2:
                    if plan.get('key_concepts'):
                        st.markdown("**Key Concepts:**")
                        for concept in plan.get('key_concepts', []):
                            st.markdown(f"- {concept}")

                    if plan.get('readings'):
                        st.markdown("**Readings:**")
                        for reading in plan.get('readings', []):
                            st.markdown(f"- {reading}")

                # Case study
                if plan.get('case'):
                    st.markdown("---")
                    st.markdown("**Case Study:**")
                    case = plan['case']
                    if isinstance(case, dict):
                        st.markdown(f"_{case.get('title', 'Untitled')}_")
                        st.write(case.get('scenario', case.get('description', '')))
                    else:
                        st.write(case)

                # Discussion prompts
                if plan.get('discussion_prompts'):
                    st.markdown("**Discussion Prompts:**")
                    for i, prompt in enumerate(plan['discussion_prompts'], 1):
                        st.markdown(f"{i}. {prompt}")

                # Full JSON
                with st.expander("View Full Plan JSON"):
                    st.json(plan)

                # Model info
                if session.get('model_name'):
                    st.caption(f"Generated by: {session['model_name']} | Version: {session.get('prompt_version', 'N/A')}")
            else:
                st.info("No session plan available. This session may have been created manually.")

    with tab2:
        st.subheader("Create New Session")

        with st.form("create_session"):
            session_title = st.text_input("Session Title", placeholder="e.g., Week 1: Introduction to ML")

            if st.form_submit_button("Create Session"):
                if session_title:
                    result = api_post("/sessions/", {
                        "course_id": course_id,
                        "title": session_title,
                    })
                    if result:
                        st.success(f"Session created with ID: {result['id']}")
                else:
                    st.error("Session title is required")

    with tab3:
        st.subheader("Session Status Control")

        manage_session_id = st.number_input("Session ID", min_value=1, step=1, key="manage_session_id")

        if st.button("Load Session for Management"):
            session = api_get(f"/sessions/{manage_session_id}")
            if session:
                st.session_state["manage_session"] = session

        if "manage_session" in st.session_state and st.session_state["manage_session"]:
            session = st.session_state["manage_session"]
            status = session['status']

            st.markdown(f"**{session['title']}** - Current Status: :{get_status_color(status)}[{status.upper()}]")

            st.markdown("**Change Status:**")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if status != "draft":
                    if st.button("Set to Draft", use_container_width=True):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "draft"})
                        if result:
                            st.session_state["manage_session"] = result
                            st.success("Status: Draft")
                            st.rerun()

            with col2:
                if status == "draft":
                    if st.button("Schedule", use_container_width=True):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "scheduled"})
                        if result:
                            st.session_state["manage_session"] = result
                            st.success("Status: Scheduled")
                            st.rerun()

            with col3:
                if status in ["draft", "scheduled"]:
                    if st.button("Go Live", use_container_width=True, type="primary"):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "live"})
                        if result:
                            st.session_state["manage_session"] = result
                            st.success("Session is LIVE!")
                            st.rerun()

            with col4:
                if status == "live":
                    if st.button("Complete", use_container_width=True):
                        result = api_patch(f"/sessions/{session['id']}/status", {"status": "completed"})
                        if result:
                            st.session_state["manage_session"] = result
                            st.success("Session Completed")
                            st.rerun()


# ============ FORUM PAGE ============
elif page == "Forum":
    st.title("Discussion Forum")

    session_id = st.number_input("Session ID", min_value=1, step=1, key="forum_session_id")

    if session_id:
        # Load session info
        session = api_get(f"/sessions/{session_id}")
        if session:
            status = session['status']
            st.markdown(f"**{session['title']}** - :{get_status_color(status)}[{status.upper()}]")

        tab1, tab2, tab3 = st.tabs(["Discussion", "Post Case", "Post Reply"])

        with tab1:
            st.subheader("Discussion Thread")

            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Refresh"):
                    st.rerun()

            posts = api_get(f"/posts/session/{session_id}")
            if posts:
                # Show pinned posts first
                pinned_posts = [p for p in posts if p.get('pinned')]
                unpinned_posts = [p for p in posts if not p.get('pinned')]

                st.markdown(f"**{len(posts)} posts** ({len(pinned_posts)} pinned)")
                st.markdown("---")

                for post in pinned_posts + unpinned_posts:
                    post_id = post['id']
                    is_pinned = post.get('pinned', False)
                    labels = post.get('labels_json') or []

                    # Post container
                    with st.container():
                        # Header
                        header_parts = [f"**Post #{post_id}** by User {post['user_id']}"]
                        if is_pinned:
                            header_parts.append("📌")
                        if "high-quality" in labels:
                            header_parts.append("⭐")
                        if "needs-clarification" in labels:
                            header_parts.append("❓")

                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.markdown(" ".join(header_parts))
                        with col2:
                            st.caption(format_timestamp(post.get('created_at')))

                        # Content
                        st.write(post['content'])

                        # Moderation controls
                        with st.expander("Moderate", expanded=False):
                            mod_col1, mod_col2, mod_col3, mod_col4 = st.columns(4)

                            with mod_col1:
                                pin_label = "Unpin" if is_pinned else "Pin"
                                if st.button(pin_label, key=f"pin_{post_id}"):
                                    result = api_post(f"/posts/{post_id}/pin", {"pinned": not is_pinned})
                                    if result:
                                        st.rerun()

                            with mod_col2:
                                if st.button("High Quality", key=f"hq_{post_id}"):
                                    new_labels = list(set(labels + ["high-quality"]))
                                    if "needs-clarification" in new_labels:
                                        new_labels.remove("needs-clarification")
                                    api_post(f"/posts/{post_id}/label", {"labels": new_labels})
                                    st.rerun()

                            with mod_col3:
                                if st.button("Needs Clarification", key=f"nc_{post_id}"):
                                    new_labels = list(set(labels + ["needs-clarification"]))
                                    if "high-quality" in new_labels:
                                        new_labels.remove("high-quality")
                                    api_post(f"/posts/{post_id}/label", {"labels": new_labels})
                                    st.rerun()

                            with mod_col4:
                                if labels and st.button("Clear", key=f"cl_{post_id}"):
                                    api_post(f"/posts/{post_id}/label", {"labels": []})
                                    st.rerun()

                        st.markdown("---")
            else:
                st.info("No posts yet. Start the discussion!")

        with tab2:
            st.subheader("Post Case (Instructor)")
            st.markdown("Post a case study or problem for students to discuss.")

            with st.form("post_case"):
                case_prompt = st.text_area(
                    "Case/Problem Statement",
                    height=200,
                    placeholder="Describe the case study or problem for discussion..."
                )

                if st.form_submit_button("Post Case"):
                    if case_prompt:
                        result = api_post(f"/sessions/{session_id}/case", {"prompt": case_prompt})
                        if result:
                            st.success("Case posted successfully!")
                    else:
                        st.error("Please enter a case statement")

        with tab3:
            st.subheader("Post Reply")

            with st.form("post_reply"):
                user_id = st.number_input("Your User ID", min_value=1, step=1, value=1)
                content = st.text_area("Your Response", height=150)

                if st.form_submit_button("Submit Post"):
                    if content:
                        result = api_post(f"/posts/session/{session_id}", {
                            "user_id": user_id,
                            "content": content,
                        })
                        if result:
                            st.success("Post submitted!")
                    else:
                        st.error("Please enter your response")


# ============ INSTRUCTOR CONSOLE PAGE ============
elif page == "Instructor Console":
    st.title("Instructor Console")
    st.markdown("Real-time copilot suggestions and poll management during live sessions.")

    session_id = st.number_input("Session ID", min_value=1, step=1, key="console_session_id")

    if session_id:
        # Load session info
        session = api_get(f"/sessions/{session_id}")
        if session:
            status = session['status']
            st.markdown(f"**{session['title']}** - :{get_status_color(status)}[{status.upper()}]")

        tab1, tab2, tab3 = st.tabs(["Live Copilot", "Polls", "Quick Actions"])

        with tab1:
            st.subheader("Live Copilot Suggestions")

            # Copilot controls
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Start Copilot", use_container_width=True, type="primary"):
                    result = api_post(f"/sessions/{session_id}/start_live_copilot")
                    if result:
                        st.success(f"Copilot started! Task: {result.get('task_id', 'N/A')}")

            with col2:
                if st.button("Stop Copilot", use_container_width=True):
                    result = api_post(f"/sessions/{session_id}/stop_live_copilot")
                    if result:
                        st.info("Stop requested")

            with col3:
                copilot_status = api_get(f"/sessions/{session_id}/copilot_status")
                if copilot_status:
                    is_active = copilot_status.get('copilot_active', False)
                    st.metric("Status", "ACTIVE" if is_active else "Inactive")

            st.markdown("---")

            # Fetch and display interventions
            if st.button("Refresh Suggestions"):
                st.rerun()

            interventions = api_get(f"/sessions/{session_id}/interventions")

            if interventions:
                st.markdown(f"**{len(interventions)} suggestions available**")

                for i, intervention in enumerate(interventions):
                    suggestion = intervention.get('suggestion_json', {})

                    with st.expander(
                        f"Suggestion #{intervention['id']} - {intervention.get('intervention_type', 'N/A').upper()} "
                        f"({format_timestamp(intervention.get('created_at'))})",
                        expanded=(i == 0)  # Expand most recent
                    ):
                        # Rolling summary
                        if suggestion.get('rolling_summary'):
                            st.markdown("**Discussion Summary:**")
                            st.info(suggestion['rolling_summary'])

                        # Confusion points
                        if suggestion.get('confusion_points'):
                            st.markdown("**Confusion Points:**")
                            for cp in suggestion['confusion_points']:
                                severity = cp.get('severity', 'medium')
                                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                                st.markdown(f"{severity_icon} **{cp.get('issue', 'N/A')}**")
                                st.markdown(f"  _{cp.get('explanation', '')}_")
                                if cp.get('evidence_post_ids'):
                                    st.caption(f"  Evidence: Posts {cp['evidence_post_ids']}")

                        # Instructor prompts
                        if suggestion.get('instructor_prompts'):
                            st.markdown("**Suggested Prompts:**")
                            for j, prompt in enumerate(suggestion['instructor_prompts'], 1):
                                st.markdown(f"{j}. \"{prompt.get('prompt', '')}\"")
                                st.caption(f"   Purpose: {prompt.get('purpose', 'N/A')} | Target: {prompt.get('target', 'N/A')}")

                        # Re-engagement activity
                        if suggestion.get('reengagement_activity'):
                            activity = suggestion['reengagement_activity']
                            st.markdown("**Re-engagement Activity:**")
                            st.success(f"**{activity.get('type', 'Activity')}**: {activity.get('description', '')}")
                            st.caption(f"Estimated time: {activity.get('estimated_time', 'N/A')}")

                        # Poll suggestion
                        if suggestion.get('poll_suggestion'):
                            poll = suggestion['poll_suggestion']
                            st.markdown("**Suggested Poll:**")
                            st.markdown(f"📊 {poll.get('question', 'N/A')}")
                            options = poll.get('options', [])
                            for k, opt in enumerate(options):
                                st.markdown(f"  {k+1}. {opt}")

                            # Button to create this poll
                            if st.button(f"Create This Poll", key=f"create_poll_{intervention['id']}"):
                                result = api_post(f"/polls/session/{session_id}", {
                                    "question": poll.get('question', ''),
                                    "options_json": options,
                                })
                                if result:
                                    st.success(f"Poll created! ID: {result['id']}")

                        # Overall assessment
                        if suggestion.get('overall_assessment'):
                            assessment = suggestion['overall_assessment']
                            st.markdown("**Overall Assessment:**")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Engagement", assessment.get('engagement_level', 'N/A'))
                            with col2:
                                st.metric("Understanding", assessment.get('understanding_level', 'N/A'))
                            with col3:
                                st.metric("Discussion", assessment.get('discussion_quality', 'N/A'))

                            if assessment.get('recommendation'):
                                st.info(f"**Recommendation:** {assessment['recommendation']}")

                        # Metadata
                        st.caption(f"Model: {suggestion.get('model_name', intervention.get('model_name', 'N/A'))} | "
                                   f"Evidence Posts: {intervention.get('evidence_post_ids', [])}")
            else:
                st.info("No suggestions yet. Start the copilot and wait for the first analysis (runs every 90 seconds).")

        with tab2:
            st.subheader("Polls Management")

            # Create poll manually
            st.markdown("**Create a Poll:**")
            with st.form("create_poll"):
                question = st.text_input("Poll Question")
                options_text = st.text_area("Options (one per line)", height=100)

                if st.form_submit_button("Create Poll"):
                    if question and options_text:
                        options = [o.strip() for o in options_text.split("\n") if o.strip()]
                        if len(options) >= 2:
                            result = api_post(f"/polls/session/{session_id}", {
                                "question": question,
                                "options_json": options,
                            })
                            if result:
                                st.success(f"Poll created! ID: {result['id']}")
                        else:
                            st.error("Need at least 2 options")
                    else:
                        st.error("Question and options are required")

            st.markdown("---")

            # View poll results
            st.markdown("**View Poll Results:**")
            poll_id = st.number_input("Poll ID", min_value=1, step=1, key="poll_results_id")

            if st.button("Get Results"):
                results = api_get(f"/polls/{poll_id}/results")
                if results:
                    st.markdown(f"**{results['question']}**")
                    st.markdown(f"Total votes: {results['total_votes']}")

                    # Show results as bar chart
                    options = results.get('options', [])
                    counts = results.get('vote_counts', [])

                    if options and counts:
                        import pandas as pd
                        df = pd.DataFrame({
                            'Option': options,
                            'Votes': counts
                        })
                        st.bar_chart(df.set_index('Option'))

                        # Also show as table
                        total = sum(counts) if counts else 1
                        for opt, count in zip(options, counts):
                            pct = (count / total * 100) if total > 0 else 0
                            st.markdown(f"- {opt}: **{count}** ({pct:.1f}%)")

        with tab3:
            st.subheader("Quick Actions")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Session Status:**")
                if session:
                    status = session['status']
                    if status in ["draft", "scheduled"]:
                        if st.button("Go Live Now", use_container_width=True, type="primary"):
                            result = api_patch(f"/sessions/{session_id}/status", {"status": "live"})
                            if result:
                                st.success("Session is LIVE!")
                                st.rerun()
                    elif status == "live":
                        if st.button("End Session", use_container_width=True):
                            result = api_patch(f"/sessions/{session_id}/status", {"status": "completed"})
                            if result:
                                st.success("Session completed")
                                st.rerun()

            with col2:
                st.markdown("**Generate Report:**")
                if st.button("Generate Feedback Report", use_container_width=True):
                    result = api_post(f"/reports/session/{session_id}/generate")
                    if result:
                        st.success(f"Report generation queued: {result['task_id']}")
                        st.markdown("View it in the **Reports** page.")


# ============ REPORTS PAGE ============
elif page == "Reports":
    st.title("Feedback Reports")
    st.markdown("Generate and view post-discussion analysis reports.")

    session_id = st.number_input("Session ID", min_value=1, step=1, key="report_session_id")

    if session_id:
        # Load session info
        session = api_get(f"/sessions/{session_id}")
        if session:
            st.markdown(f"**{session['title']}**")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Generate Report", use_container_width=True, type="primary"):
                result = api_post(f"/reports/session/{session_id}/generate")
                if result:
                    st.success(f"Report generation queued!")
                    st.info(f"Task ID: {result['task_id']}")
                    st.markdown("Refresh in ~30-60 seconds to see the report.")

        with col2:
            if st.button("Refresh / Load Report", use_container_width=True):
                st.session_state["current_report"] = api_get(f"/reports/session/{session_id}")

        st.markdown("---")

        # Display report
        if "current_report" not in st.session_state:
            st.session_state["current_report"] = api_get(f"/reports/session/{session_id}")

        report = st.session_state.get("current_report")

        if report:
            st.subheader(f"Report Version {report.get('version', 'N/A')}")

            # Enhanced Observability Panel (Milestone 6)
            with st.expander("Observability Summary", expanded=True):
                obs_col1, obs_col2, obs_col3, obs_col4 = st.columns(4)

                with obs_col1:
                    model_name = report.get('model_name', 'N/A')
                    used_fallback = report.get('used_fallback', 0)
                    st.metric("Model", model_name or "N/A")
                    if used_fallback == 1 or model_name == 'fallback':
                        st.caption("⚠️ Fallback mode (no LLM)")

                with obs_col2:
                    exec_time = report.get('execution_time_seconds')
                    if exec_time is not None:
                        st.metric("Execution Time", f"{exec_time:.1f}s")
                    else:
                        st.metric("Execution Time", "N/A")

                with obs_col3:
                    total_tokens = report.get('total_tokens')
                    if total_tokens:
                        st.metric("Tokens Used", f"{total_tokens:,}")
                        prompt_tokens = report.get('prompt_tokens', 0)
                        completion_tokens = report.get('completion_tokens', 0)
                        st.caption(f"Prompt: {prompt_tokens:,} | Completion: {completion_tokens:,}")
                    else:
                        st.metric("Tokens Used", "N/A")

                with obs_col4:
                    cost = report.get('estimated_cost_usd')
                    if cost is not None:
                        st.metric("Estimated Cost", f"${cost:.4f}")
                    else:
                        st.metric("Estimated Cost", "N/A")

                # Second row of observability info
                obs_col5, obs_col6, obs_col7, obs_col8 = st.columns(4)

                with obs_col5:
                    st.metric("Report ID", report.get('id', 'N/A'))

                with obs_col6:
                    st.metric("Prompt Version", report.get('prompt_version', 'N/A'))

                with obs_col7:
                    retry_count = report.get('retry_count', 0)
                    st.metric("Retries", retry_count)

                with obs_col8:
                    error_msg = report.get('error_message')
                    if error_msg:
                        st.error(f"Error: {error_msg[:50]}...")
                    else:
                        st.success("No errors")

                st.caption(f"Generated: {format_timestamp(report.get('created_at'))}")

            # Tabs for different views
            tab1, tab2, tab3 = st.tabs(["Formatted Report", "Raw Markdown", "JSON Data"])

            with tab1:
                report_md = report.get('report_md', '')
                if report_md:
                    st.markdown(report_md)
                else:
                    st.info("No markdown report available.")

            with tab2:
                report_md = report.get('report_md', '')
                if report_md:
                    st.code(report_md, language="markdown")

                    # Download button
                    st.download_button(
                        label="Download Markdown",
                        data=report_md,
                        file_name=f"report_session_{session_id}_v{report.get('version', '1')}.md",
                        mime="text/markdown",
                    )
                else:
                    st.info("No markdown report available.")

            with tab3:
                report_json = report.get('report_json', {})
                if report_json:
                    st.json(report_json)

                    # Show key sections
                    st.markdown("---")
                    st.markdown("**Report Sections:**")

                    if report_json.get('themes'):
                        with st.expander("Themes/Clusters"):
                            st.json(report_json['themes'])

                    if report_json.get('objectives_alignment'):
                        with st.expander("Objectives Alignment"):
                            st.json(report_json['objectives_alignment'])

                    if report_json.get('misconceptions'):
                        with st.expander("Misconceptions"):
                            st.json(report_json['misconceptions'])

                    if report_json.get('best_practice'):
                        with st.expander("Best Practice Answer"):
                            st.json(report_json['best_practice'])

                    if report_json.get('student_summary'):
                        with st.expander("Student Summary"):
                            st.json(report_json['student_summary'])

                    # Poll results embedded in report (Milestone 5)
                    if report_json.get('poll_results'):
                        with st.expander("Poll Results (Embedded)", expanded=True):
                            for poll in report_json['poll_results']:
                                st.markdown(f"**{poll.get('question', 'Unknown Poll')}**")
                                st.caption(f"Total votes: {poll.get('total_votes', 0)}")
                                for opt in poll.get('options', []):
                                    pct = opt.get('percentage', 0)
                                    votes = opt.get('votes', 0)
                                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                                    st.text(f"  {bar} {pct:.0f}% ({votes}) - {opt.get('text', '')}")
                                if poll.get('interpretation'):
                                    st.info(f"📊 {poll['interpretation']}")
                                st.markdown("---")

                    # Observability embedded in report (Milestone 6)
                    if report_json.get('observability'):
                        with st.expander("Observability Metadata"):
                            st.json(report_json['observability'])
                else:
                    st.info("No JSON data available.")

            # Poll results section
            st.markdown("---")
            st.subheader("Poll Results (Classroom Evidence)")

            poll_id_input = st.number_input("Enter Poll ID to view results", min_value=1, step=1, key="report_poll_id")

            if st.button("Load Poll Results"):
                poll_results = api_get(f"/polls/{poll_id_input}/results")
                if poll_results:
                    st.markdown(f"**{poll_results['question']}**")
                    st.markdown(f"_Total votes: {poll_results['total_votes']}_")

                    options = poll_results.get('options', [])
                    counts = poll_results.get('vote_counts', [])

                    if options and counts:
                        import pandas as pd
                        df = pd.DataFrame({
                            'Option': options,
                            'Votes': counts
                        })
                        st.bar_chart(df.set_index('Option'))

                        st.markdown("**Classroom State Evidence:**")
                        total = sum(counts) if counts else 1
                        for opt, count in zip(options, counts):
                            pct = (count / total * 100) if total > 0 else 0
                            st.markdown(f"- {opt}: **{count}** votes ({pct:.1f}%)")

                        st.caption("Poll results can be cited in reports as evidence of classroom understanding.")
        else:
            st.info("No report found for this session. Click 'Generate Report' to create one.")


# ============ FOOTER ============
st.sidebar.markdown("---")
st.sidebar.caption("AristAI v0.2.0")
st.sidebar.caption("AI-Assisted Classroom Forum")
