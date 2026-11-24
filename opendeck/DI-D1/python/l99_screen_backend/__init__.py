"""L99 Screen Backend - Offline screen-output backend for OpenDeck button images."""

from .image_processor import ImageProcessor, ImageValidationResult, ProcessedImage
from .icon_cache import IconCache, CacheEntry
from .layout import LayoutModel, ButtonLayout
from .state_manager import StateManager, ButtonStateRecord, LogicalButtonState, PhysicalConfirmStatus
from .mock_transport import MockScreenTransport, TransportRecord, TransportStatus
from .backend import ScreenBackend, ImageUpdateRequest, ImageUpdateResult
from .callback_handler import CallbackHandler, CallbackResult, SetImageCallback
from .callback_adapter import CallbackAdapter, CallbackMessage
from .callback_spool_consumer import CallbackSpoolConsumer, ProcessingResult, ConsumerStats
from .transport import ScreenTransport, TransportStatus, TransportRecord, MockScreenTransport as MockScreenTransportV2, MailboxTransport, load_slot_config
from .dirty_regions import DirtyRegionTracker, DirtyRegion, RegionStatus
from .scheduler import IconUpdateScheduler, PendingUpdate, UpdateStatus
from .di_backend import DIDynamicBackend, DynamicUpdateResult

__all__ = [
    "ImageProcessor",
    "ImageValidationResult",
    "ProcessedImage",
    "IconCache",
    "CacheEntry",
    "LayoutModel",
    "ButtonLayout",
    "StateManager",
    "ButtonStateRecord",
    "LogicalButtonState",
    "PhysicalConfirmStatus",
    "MockScreenTransport",
    "TransportRecord",
    "TransportStatus",
    "ScreenBackend",
    "ImageUpdateRequest",
    "ImageUpdateResult",
    "CallbackHandler",
    "CallbackResult",
    "SetImageCallback",
    "CallbackAdapter",
    "CallbackMessage",
    "CallbackSpoolConsumer",
    "ProcessingResult",
    "ConsumerStats",
    # DI-D1 additions
    "ScreenTransport",
    "MockScreenTransportV2",
    "DirtyRegionTracker",
    "DirtyRegion",
    "RegionStatus",
    "IconUpdateScheduler",
    "PendingUpdate",
    "UpdateStatus",
    "DIDynamicBackend",
    "DynamicUpdateResult",
]

__version__ = "2.0.0-di-d1"