from enum import Enum


class MemoryCategory(str, Enum):
    USER_PROFILE = "user_profile"
    ACTIVE_PROJECTS = "active_projects"
    BUSINESS_PLANS = "business_plans"
    TECHNICAL_BUILDS = "technical_builds"
    FINANCIAL_CONTEXT = "financial_context"
    PERSONAL_NOTES = "personal_notes"
    SESSION_CONTEXT = "session_context"
    ARCHIVED_HISTORY = "archived_history"


CATEGORY_LABELS = {
    MemoryCategory.USER_PROFILE: "User Profile & Preferences",
    MemoryCategory.ACTIVE_PROJECTS: "Active Projects",
    MemoryCategory.BUSINESS_PLANS: "Business Plans",
    MemoryCategory.TECHNICAL_BUILDS: "Technical Builds",
    MemoryCategory.FINANCIAL_CONTEXT: "Financial / Car / Job",
    MemoryCategory.PERSONAL_NOTES: "Personal Notes",
    MemoryCategory.SESSION_CONTEXT: "Session Context",
    MemoryCategory.ARCHIVED_HISTORY: "Archived History",
}

PERMANENT_CATEGORIES = {
    MemoryCategory.USER_PROFILE,
    MemoryCategory.ACTIVE_PROJECTS,
    MemoryCategory.BUSINESS_PLANS,
    MemoryCategory.TECHNICAL_BUILDS,
    MemoryCategory.FINANCIAL_CONTEXT,
    MemoryCategory.PERSONAL_NOTES,
    MemoryCategory.ARCHIVED_HISTORY,
}

EPHEMERAL_CATEGORIES = {MemoryCategory.SESSION_CONTEXT}