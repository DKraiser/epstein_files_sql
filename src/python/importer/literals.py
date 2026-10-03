from enum import Enum


class IndexedStrEnum(str, Enum):
    id: int 
    
    def __new__(cls, id_: int, value_: str):
        obj = str.__new__(cls, value_)
        obj._value_ = value_
        obj.id = id_
        return obj


class ParseStatus(IndexedStrEnum):
    SUCCESS = (1, "success")
    PARTIAL = (2, "partial")
    NULL = (3, "null")
    FAILED = (4, "failed")
    EMPTY = (5, "empty")


class MatchStatus(IndexedStrEnum):
    MATCHED = (1, "matched")
    UNRESOLVED = (2, "unresolved")


class RunStatus(IndexedStrEnum):
    COMPLETED = (1, "completed")
    CRASHED = (2, "crashed")
    INTERRUPTED = (3, "interrupted")


class FileStatus(IndexedStrEnum):
    SUCCESS = (1, "success")
    FAILED = (2, "failed")


class CuratedStatus(IndexedStrEnum):
    GOLD = (1, "gold")


class CuratedTier(IndexedStrEnum):
    NUCLEAR = (1, "nuclear")
    CRITICAL = (2, "critical")
    HIGH = (3, "high")
    MEDIUM = (4, "medium")
    SUPPORTING = (5, "supporting")


class Model(IndexedStrEnum):
    GEMINI_2_5_FLASH = (1, "gemini-2.5-flash")
    GEMINI_2_5_FLASH_LITE = (2, "gemini-2.5-flash-lite")
    GEMINI_3_FLASH_PREVIEW = (3, "gemini-3-flash-preview")
    DEEPSEEK_CHAT = (4, "deepseek-chat")
    GPT_4O_MINI = (5, "gpt-4o-mini")
    GPT_5_NANO = (6, "gpt-5-nano")
    GROK_2_VISION_LATEST = (7, "grok-2-vision-latest")
    TESSERACT_COMMUNITY = (8, "tesseract-community")