"""
Game data model.

Represents a single referee game with earnings, payment status, and metadata.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Game:
    """Represents a single referee game entry.

    Attributes:
        season: Season identifier (e.g., '2025/2026').
        gameNumber: Unique game number for the season.
        date: Game date (ISO format: YYYY-MM-DD).
        location: Game location/venue.
        transportation: Transportation cost.
        food: Food/meal cost.
        gamePayment: Referee payment for the game.
        paidStatus: Payment status ('Yes', 'No', or None).
        paymentDate: Date when payment was received (ISO format).
        observations: Notes or comments about the game.
    """
    season: str
    gameNumber: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    transportation: float = 0.0
    food: float = 0.0
    gamePayment: float = 0.0
    paidStatus: Optional[str] = None
    paymentDate: Optional[str] = None
    observations: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert game instance to dictionary.

        Returns:
            Dictionary representation of the game.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Game':
        """Create game instance from dictionary.

        Args:
            data: Dictionary with game attributes.

        Returns:
            Game instance with matching attributes.
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
