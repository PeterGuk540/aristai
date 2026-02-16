"""Add enhanced AI features tables.

This migration adds tables for 10 new AI-powered features:
1. Smart Discussion Summarization (live_summaries)
2. AI-Powered Student Grouping (student_groups, student_group_members)
3. Personalized Follow-up Generator (personalized_followups)
4. Question Bank Builder (question_bank_items)
5. Attendance & Participation Insights (participation_snapshots, participation_alerts)
6. AI Teaching Assistant Mode (ai_assistant_messages)
7. Session Recording & Transcript Analysis (session_recordings, transcript_post_links)
8. Learning Objective Alignment Dashboard (objective_coverage)
9. Peer Review Workflow (peer_review_assignments, peer_review_feedback)
10. Multi-Language Support (post_translations, user_language_preferences)

Revision ID: 015_enhanced_ai_features
Revises: 014_canvas_push_tables
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa


revision = "017_enhanced_ai_features"
down_revision = "016_canvas_push"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============ Feature 1: Smart Discussion Summarization ============
    op.create_table(
        "live_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("key_themes", sa.JSON(), nullable=True),
        sa.Column("unanswered_questions", sa.JSON(), nullable=True),
        sa.Column("misconceptions", sa.JSON(), nullable=True),
        sa.Column("engagement_pulse", sa.String(20), nullable=True),
        sa.Column("posts_analyzed", sa.Integer(), nullable=True),
        sa.Column("last_post_id", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_summaries_session_id", "live_summaries", ["session_id"])

    # ============ Feature 2: AI-Powered Student Grouping ============
    op.create_table(
        "student_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("group_type", sa.String(50), nullable=False),
        sa.Column("topic", sa.String(500), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_groups_session_id", "student_groups", ["session_id"])

    op.create_table(
        "student_group_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["student_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_group_members_group_id", "student_group_members", ["group_id"])
    op.create_index("ix_student_group_members_user_id", "student_group_members", ["user_id"])

    # ============ Feature 3: Personalized Follow-up Generator ============
    op.create_table(
        "personalized_followups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=True),
        sa.Column("improvements", sa.JSON(), nullable=True),
        sa.Column("key_takeaways", sa.JSON(), nullable=True),
        sa.Column("suggested_resources", sa.JSON(), nullable=True),
        sa.Column("custom_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_via", sa.String(30), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personalized_followups_session_id", "personalized_followups", ["session_id"])
    op.create_index("ix_personalized_followups_user_id", "personalized_followups", ["user_id"])

    # ============ Feature 4: Question Bank Builder ============
    op.create_table(
        "question_bank_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("question_type", sa.String(30), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("rubric", sa.JSON(), nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("learning_objective", sa.String(500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("source_post_ids", sa.JSON(), nullable=True),
        sa.Column("times_used", sa.Integer(), default=0),
        sa.Column("avg_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(30), default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_bank_items_course_id", "question_bank_items", ["course_id"])
    op.create_index("ix_question_bank_items_session_id", "question_bank_items", ["session_id"])

    # ============ Feature 5: Attendance & Participation Insights ============
    op.create_table(
        "participation_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_count", sa.Integer(), default=0),
        sa.Column("reply_count", sa.Integer(), default=0),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("engagement_level", sa.String(20), nullable=True),
        sa.Column("time_active_minutes", sa.Integer(), nullable=True),
        sa.Column("at_risk", sa.Boolean(), default=False),
        sa.Column("risk_factors", sa.JSON(), nullable=True),
        sa.Column("snapshot_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_participation_snapshots_course_id", "participation_snapshots", ["course_id"])
    op.create_index("ix_participation_snapshots_user_id", "participation_snapshots", ["user_id"])

    op.create_table(
        "participation_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), default=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_participation_alerts_course_id", "participation_alerts", ["course_id"])

    # ============ Feature 6: AI Teaching Assistant Mode ============
    op.create_table(
        "ai_assistant_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("student_question", sa.Text(), nullable=False),
        sa.Column("student_post_id", sa.Integer(), nullable=True),
        sa.Column("ai_response", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("sources_used", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), default="pending"),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("instructor_edits", sa.Text(), nullable=True),
        sa.Column("response_post_id", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["response_post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_messages_session_id", "ai_assistant_messages", ["session_id"])
    op.create_index("ix_ai_assistant_messages_student_id", "ai_assistant_messages", ["student_id"])

    # ============ Feature 7: Session Recording & Transcript Analysis ============
    op.create_table(
        "session_recordings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("recording_type", sa.String(20), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("transcript_segments", sa.JSON(), nullable=True),
        sa.Column("key_moments", sa.JSON(), nullable=True),
        sa.Column("topics_discussed", sa.JSON(), nullable=True),
        sa.Column("speaker_segments", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), default="uploaded"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_recordings_session_id", "session_recordings", ["session_id"])

    op.create_table(
        "transcript_post_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Integer(), nullable=False),
        sa.Column("end_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript_snippet", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["recording_id"], ["session_recordings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_post_links_recording_id", "transcript_post_links", ["recording_id"])
    op.create_index("ix_transcript_post_links_post_id", "transcript_post_links", ["post_id"])

    # ============ Feature 8: Learning Objective Alignment Dashboard ============
    op.create_table(
        "objective_coverage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("objective_text", sa.Text(), nullable=False),
        sa.Column("objective_index", sa.Integer(), nullable=True),
        sa.Column("coverage_level", sa.String(20), nullable=True),
        sa.Column("coverage_score", sa.Float(), nullable=True),
        sa.Column("evidence_post_ids", sa.JSON(), nullable=True),
        sa.Column("coverage_summary", sa.Text(), nullable=True),
        sa.Column("gaps_identified", sa.JSON(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_objective_coverage_course_id", "objective_coverage", ["course_id"])
    op.create_index("ix_objective_coverage_session_id", "objective_coverage", ["session_id"])

    # ============ Feature 9: Peer Review Workflow ============
    op.create_table(
        "peer_review_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("submission_post_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), default="assigned"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_peer_review_assignments_session_id", "peer_review_assignments", ["session_id"])
    op.create_index("ix_peer_review_assignments_reviewer_id", "peer_review_assignments", ["reviewer_id"])

    op.create_table(
        "peer_review_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("overall_rating", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=True),
        sa.Column("areas_for_improvement", sa.JSON(), nullable=True),
        sa.Column("specific_comments", sa.Text(), nullable=True),
        sa.Column("rubric_responses", sa.JSON(), nullable=True),
        sa.Column("feedback_quality_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["assignment_id"], ["peer_review_assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_peer_review_feedback_assignment_id", "peer_review_feedback", ["assignment_id"])

    # ============ Feature 10: Multi-Language Support ============
    op.create_table(
        "post_translations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("source_language", sa.String(10), nullable=False),
        sa.Column("target_language", sa.String(10), nullable=False),
        sa.Column("translated_content", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), default=False),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_post_translations_post_id", "post_translations", ["post_id"])
    op.create_index("ix_post_translations_target_language", "post_translations", ["target_language"])

    op.create_table(
        "user_language_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("auto_translate", sa.Boolean(), default=True),
        sa.Column("show_original", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_language_preferences_user_id", "user_language_preferences", ["user_id"])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table("user_language_preferences")
    op.drop_table("post_translations")
    op.drop_table("peer_review_feedback")
    op.drop_table("peer_review_assignments")
    op.drop_table("objective_coverage")
    op.drop_table("transcript_post_links")
    op.drop_table("session_recordings")
    op.drop_table("ai_assistant_messages")
    op.drop_table("participation_alerts")
    op.drop_table("participation_snapshots")
    op.drop_table("question_bank_items")
    op.drop_table("personalized_followups")
    op.drop_table("student_group_members")
    op.drop_table("student_groups")
    op.drop_table("live_summaries")
