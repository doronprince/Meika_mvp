import enum


class ExpenseCategory(str, enum.Enum):
    GROCERIES = "groceries"
    CAFES_AND_DINING = "cafes_and_dining"
    TRANSPORTATION = "transportation"
    HOUSING_AND_UTILITIES = "housing_and_utilities"
    EDUCATION = "education"
    APPAREL = "apparel"
    ELECTRONICS = "electronics"
    OTHER = "other"


class TransitMode(str, enum.Enum):
    WALK = "walk"
    SUBWAY_BUS = "subway_bus"
    TAXI = "taxi"


class StoreType(str, enum.Enum):
    ONLINE = "online"
    LOCAL_SUPERMARKET = "local_supermarket"
    TRADITIONAL_MARKET = "traditional_market"
    CONVENIENCE_STORE = "convenience_store"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


def enum_values(py_enum: type[enum.Enum]) -> list[str]:
    """DB-stored values for a str Enum, in declaration order. Single source of
    truth shared between ORM column definitions and the Alembic migration."""
    return [member.value for member in py_enum]
