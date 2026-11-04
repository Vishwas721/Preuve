"""Import every ORM model here so `Base.metadata` is complete for Alembic."""

from app.db.base import Base
from app.modules.analysis.models import ICP, AnalysisRun, Hypothesis, Unknown
from app.modules.competitors.models import Competitor, CompetitorEvidence
from app.modules.ideas.models import Idea
from app.modules.interviews.models import Interview, InterviewNote
from app.modules.outreach.models import Message, OutreachCampaign, Suppression
from app.modules.prospects.models import Company, CompanyEvidence, Contact, LeadScore
from app.modules.research.models import (
    Evidence,
    EvidenceUnknown,
    ResearchImport,
    UnknownFinding,
    WebSource,
)
from app.modules.responses.models import Response
from app.modules.users.models import User
from app.modules.validation.models import ValidationScore
from app.modules.wtp.models import WtpSignal

__all__ = [
    "ICP",
    "AnalysisRun",
    "Base",
    "Company",
    "CompanyEvidence",
    "Competitor",
    "Contact",
    "CompetitorEvidence",
    "Evidence",
    "EvidenceUnknown",
    "Hypothesis",
    "Idea",
    "Interview",
    "InterviewNote",
    "LeadScore",
    "Message",
    "OutreachCampaign",
    "ResearchImport",
    "Response",
    "Suppression",
    "Unknown",
    "UnknownFinding",
    "User",
    "ValidationScore",
    "WebSource",
    "WtpSignal",
]
