from enum import Enum

class RarityEnum(str, Enum):
    COMMON = "Обычный"
    RARE = "Редкий"
    EPIC = "Эпический"
    LEGENDARY = "Легендарный"

class BetCode(str, Enum):
    POLY = "poly"