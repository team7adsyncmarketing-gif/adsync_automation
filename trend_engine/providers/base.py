"""Abstract base interface and error taxonomy for trend data providers."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from ..storage.models import ReelItem


class TrendProviderError(Exception):
    """Base exception for all trend provider operations."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(TrendProviderError):
    """Raised on HTTP 401: Invalid or expired API credentials."""
    pass


class PaymentRequiredError(TrendProviderError):
    """Raised on HTTP 402: Account out of credits or requires paid subscription."""
    pass


class ForbiddenError(TrendProviderError):
    """Raised on HTTP 403: Endpoint access forbidden."""
    pass


class RateLimitError(TrendProviderError):
    """Raised on HTTP 429: Rate limit hit. Check retry_after."""
    def __init__(self, message: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=429, details=details)
        self.retry_after = retry_after


class ProviderServerError(TrendProviderError):
    """Raised on HTTP 5xx: Upstream server failure."""
    pass


class BaseTrendProvider(ABC):
    """Abstract interface for social media trend extraction providers."""

    @abstractmethod
    def fetch_trending_reels(self, limit: Optional[int] = None) -> List[ReelItem]:
        """Fetches trending reels and returns normalized ReelItem objects."""
        pass

    @abstractmethod
    def fetch_reels_by_keyword(self, query: str, limit: Optional[int] = None, cursor: Optional[str] = None) -> Tuple[List[ReelItem], Optional[str]]:
        """Fetches reels matching a specific keyword or phrase and returns normalized ReelItem objects + next cursor."""
        pass

    @abstractmethod
    def fetch_reels_by_hashtag(self, hashtag: str, limit: Optional[int] = None, cursor: Optional[str] = None) -> Tuple[List[ReelItem], Optional[str]]:
        """Fetches reels tagged under a specific hashtag and returns normalized ReelItem objects + next cursor."""
        pass

    @abstractmethod
    def fetch_reels_by_creator(self, handle: str, limit: Optional[int] = None, cursor: Optional[str] = None) -> Tuple[List[ReelItem], Optional[Dict[str, Any]], Optional[str]]:
        """Fetches recent reels and profile details for an Instagram creator/handle."""
        pass

    @abstractmethod
    def validate_connection(self) -> Dict[str, Any]:
        """Checks API health and credential status without unnecessary credit consumption."""
        pass

