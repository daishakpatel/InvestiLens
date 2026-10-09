"""SQLAlchemy models.

Importing this package registers every table on `Base.metadata`. Alembic's env and any test
that builds the schema import from here so nothing is missed.
"""

from app.models.base import Base
from app.models.company import Company, CompanyIdentifier, FiscalCalendar
from app.models.document import Document, DocumentChunk, Filing
from app.models.financial import (
    CorporateAction,
    FinancialFact,
    FinancialMetric,
    PriceHistory,
)
from app.models.news import InsiderTransaction, InstitutionalHolding, News
from app.models.ops import (
    DataFreshness,
    DataQualityIssue,
    EvalResult,
    EvalRun,
    IngestionDeadLetter,
    IngestionRun,
    Job,
    LlmCall,
    RetrievalLog,
)
from app.models.research import ClaimVerification, ResearchReport, ResearchSource
from app.models.user import (
    Alert,
    AuthToken,
    ChatMessage,
    ChatSession,
    Notification,
    RefreshToken,
    ReportFeedback,
    User,
    Watchlist,
    WatchlistItem,
)

__all__ = [
    "Alert",
    "AuthToken",
    "Base",
    "ChatMessage",
    "ChatSession",
    "ClaimVerification",
    "Company",
    "CompanyIdentifier",
    "CorporateAction",
    "DataFreshness",
    "DataQualityIssue",
    "Document",
    "DocumentChunk",
    "EvalResult",
    "EvalRun",
    "Filing",
    "FinancialFact",
    "FinancialMetric",
    "FiscalCalendar",
    "IngestionDeadLetter",
    "IngestionRun",
    "InsiderTransaction",
    "InstitutionalHolding",
    "Job",
    "LlmCall",
    "News",
    "Notification",
    "PriceHistory",
    "RefreshToken",
    "ReportFeedback",
    "ResearchReport",
    "ResearchSource",
    "RetrievalLog",
    "User",
    "Watchlist",
    "WatchlistItem",
]
