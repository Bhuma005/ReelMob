"""
state_machine.py — Authoritative State Machine & Legal Lifecycle Transitions for ReelMob.
Enforces transition validation across Video Library, Upload Queue, and Cleanup lifecycles.
"""

from enum import Enum
from typing import Set, Dict, Optional
import logging

logger = logging.getLogger("reelsmob.state_machine")


class LibraryStatus(str, Enum):
    CREATED = "created"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    PROCESSING = "processing"
    READY = "ready"
    SCHEDULED = "scheduled"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    DELETE_PENDING = "delete_pending"
    CLEANED = "cleaned"
    FAILED = "failed"


class QueueStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CleanupStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


# Legal transitions for Video Library records
LEGAL_LIBRARY_TRANSITIONS: Dict[str, Set[str]] = {
    LibraryStatus.CREATED: {
        LibraryStatus.DOWNLOADING,
        LibraryStatus.DOWNLOADED,
        LibraryStatus.PROCESSING,
        LibraryStatus.READY,
        LibraryStatus.SCHEDULED,
        LibraryStatus.FAILED,
    },
    LibraryStatus.DOWNLOADING: {
        LibraryStatus.DOWNLOADED,
        LibraryStatus.READY,
        LibraryStatus.FAILED,
    },
    LibraryStatus.DOWNLOADED: {
        LibraryStatus.PROCESSING,
        LibraryStatus.READY,
        LibraryStatus.SCHEDULED,
        LibraryStatus.FAILED,
    },
    LibraryStatus.PROCESSING: {
        LibraryStatus.READY,
        LibraryStatus.SCHEDULED,
        LibraryStatus.FAILED,
    },
    LibraryStatus.READY: {
        LibraryStatus.SCHEDULED,
        LibraryStatus.UPLOADING,
        LibraryStatus.DELETE_PENDING,
        LibraryStatus.FAILED,
    },
    LibraryStatus.SCHEDULED: {
        LibraryStatus.UPLOADING,
        LibraryStatus.READY,
        LibraryStatus.DELETE_PENDING,
        LibraryStatus.FAILED,
    },
    LibraryStatus.UPLOADING: {
        LibraryStatus.PUBLISHED,
        LibraryStatus.SCHEDULED,  # Retry
        LibraryStatus.FAILED,
    },
    LibraryStatus.PUBLISHED: {
        LibraryStatus.DELETE_PENDING,
        LibraryStatus.CLEANED,  # Storage deleted while retaining permanent library record
    },
    LibraryStatus.DELETE_PENDING: {
        LibraryStatus.CLEANED,
        LibraryStatus.FAILED,
    },
    LibraryStatus.CLEANED: set(),  # Terminal state: permanent metadata retained, file deleted
    LibraryStatus.FAILED: {
        LibraryStatus.READY,
        LibraryStatus.SCHEDULED,
        LibraryStatus.DELETE_PENDING,
        LibraryStatus.CREATED,
    },
}

# Legal transitions for scheduled upload queue items
LEGAL_QUEUE_TRANSITIONS: Dict[str, Set[str]] = {
    QueueStatus.PENDING: {
        QueueStatus.CLAIMED,
        QueueStatus.CANCELLED,
    },
    QueueStatus.CLAIMED: {
        QueueStatus.UPLOADING,
        QueueStatus.PENDING,  # Lease expired / reclaimed
        QueueStatus.FAILED,
    },
    QueueStatus.UPLOADING: {
        QueueStatus.UPLOADED,
        QueueStatus.PENDING,  # Retry attempt
        QueueStatus.FAILED,
    },
    QueueStatus.UPLOADED: set(),  # Terminal state
    QueueStatus.FAILED: {
        QueueStatus.PENDING,  # Manual or automated retry
        QueueStatus.CANCELLED,
    },
    QueueStatus.CANCELLED: set(),  # Terminal state
}


def can_transition_library(from_status: str, to_status: str) -> bool:
    """Validates if a video_library state transition is legal."""
    if not from_status or from_status == to_status:
        return True
    allowed = LEGAL_LIBRARY_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def can_transition_queue(from_status: str, to_status: str) -> bool:
    """Validates if a scheduled_videos queue state transition is legal."""
    if not from_status or from_status == to_status:
        return True
    allowed = LEGAL_QUEUE_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def transition_library_status(current_status: str, next_status: str) -> str:
    """
    Enforces legal library status transition.
    Raises ValueError if transition is illegal.
    """
    if not can_transition_library(current_status, next_status):
        err = f"Illegal Library state transition: '{current_status}' -> '{next_status}'"
        logger.error(err)
        raise ValueError(err)
    return next_status


def transition_queue_status(current_status: str, next_status: str) -> str:
    """
    Enforces legal queue status transition.
    Raises ValueError if transition is illegal.
    """
    if not can_transition_queue(current_status, next_status):
        err = f"Illegal Queue state transition: '{current_status}' -> '{next_status}'"
        logger.error(err)
        raise ValueError(err)
    return next_status
