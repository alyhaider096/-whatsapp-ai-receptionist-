import enum


class UserRole(str, enum.Enum):
    owner = "owner"
    staff = "staff"


class ConversationStatus(str, enum.Enum):
    open = "open"
    needs_human = "needs_human"
    human = "human"
    closed = "closed"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class MessageType(str, enum.Enum):
    text = "text"
    audio = "audio"
    image = "image"
    document = "document"


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class LeadStatus(str, enum.Enum):
    new = "new"
    qualified = "qualified"
    needs_human = "needs_human"
    booked = "booked"
    lost = "lost"
