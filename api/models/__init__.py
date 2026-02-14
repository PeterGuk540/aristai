# Import all models here so Base.metadata is complete for Alembic
from api.models.user import User
from api.models.course import Course, CourseResource
from api.models.session import Session, Case
from api.models.post import Post
from api.models.poll import Poll, PollVote
from api.models.intervention import Intervention
from api.models.report import Report
from api.models.enrollment import Enrollment
from api.models.voice_audit import VoiceAudit
from api.models.course_material import CourseMaterial
from api.models.engagement import (
    StudentEngagement,
    EngagementLevel,
    SessionTimer,
    BreakoutGroup,
    BreakoutGroupMember,
    SessionTemplate,
    PreClassCheckpoint,
    CheckpointCompletion,
    AIResponseDraft,
)
from api.models.integration import (
    IntegrationConnection,
    IntegrationProviderConnection,
    IntegrationCourseMapping,
    IntegrationSyncJob,
    IntegrationSyncItem,
    IntegrationMaterialLink,
)

__all__ = [
    "User",
    "Course",
    "CourseResource",
    "Session",
    "Case",
    "Post",
    "Poll",
    "PollVote",
    "Intervention",
    "Report",
    "Enrollment",
    "VoiceAudit",
    "CourseMaterial",
    # New engagement models
    "StudentEngagement",
    "EngagementLevel",
    "SessionTimer",
    "BreakoutGroup",
    "BreakoutGroupMember",
    "SessionTemplate",
    "PreClassCheckpoint",
    "CheckpointCompletion",
    "AIResponseDraft",
    # Integration models
    "IntegrationConnection",
    "IntegrationProviderConnection",
    "IntegrationCourseMapping",
    "IntegrationSyncJob",
    "IntegrationSyncItem",
    "IntegrationMaterialLink",
]
