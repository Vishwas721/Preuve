"""Import every ORM model here so `Base.metadata` is complete for Alembic."""

from app.db.base import Base
from app.modules.analysis.models import ICP, AnalysisRun, Hypothesis, Unknown
from app.modules.auth.models import ApiToken, AuthSession
from app.modules.competitors.models import Competitor, CompetitorEvidence
from app.modules.experiments.models import Experiment
from app.modules.ideas.models import Idea
from app.modules.interviews.models import Interview, InterviewNote
from app.modules.outreach.models import Message, OutreachCampaign, Suppression
from app.modules.privacy.models import DeletedPerson
from app.modules.prospects.models import Company, CompanyEvidence, Contact, LeadScore
from app.modules.reports.models import Report
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
from app.modules.workspaces.models import Invitation, Membership, Workspace
from app.modules.wtp.models import WtpSignal

__all__ = [
    "ICP",
    "AnalysisRun",
    "ApiToken",
    "AuthSession",
    "Base",
    "Company",
    "CompanyEvidence",
    "Competitor",
    "DeletedPerson",
    "Contact",
    "CompetitorEvidence",
    "Evidence",
    "EvidenceUnknown",
    "Experiment",
    "Hypothesis",
    "Idea",
    "Interview",
    "Invitation",
    "InterviewNote",
    "LeadScore",
    "Membership",
    "Message",
    "OutreachCampaign",
    "Report",
    "ResearchImport",
    "Response",
    "Suppression",
    "Unknown",
    "UnknownFinding",
    "User",
    "ValidationScore",
    "WebSource",
    "Workspace",
    "WtpSignal",
]
