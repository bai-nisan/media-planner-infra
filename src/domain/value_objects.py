"""
Domain Value Objects

Immutable value objects that encapsulate business rules and validation.
Value objects are compared by their value, not identity.
"""

import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Union

from .exceptions import CurrencyMismatchError, InvalidDateRangeError, CampaignStatusError


class Currency(str, Enum):
    """Supported currencies for the media planning platform."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"


class Money:
    """
    Immutable Money value object with currency validation and arithmetic operations.
    
    Prevents negative amounts and ensures currency consistency in operations.
    Uses Decimal for precise financial calculations.
    """

    def __init__(self, amount: Union[int, float, Decimal, str], currency: Union[str, Currency]):
        if isinstance(currency, str):
            try:
                currency = Currency(currency.upper())
            except ValueError:
                raise ValueError(f"Unsupported currency: {currency}")

        # Convert to Decimal for precision
        if isinstance(amount, str):
            amount = Decimal(amount)
        elif isinstance(amount, (int, float)):
            amount = Decimal(str(amount))

        # Round to 2 decimal places for currency
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if amount < 0:
            raise ValueError("Money amount cannot be negative")

        self._amount = amount
        self._currency = currency

    @property
    def amount(self) -> Decimal:
        """Get the amount as a Decimal."""
        return self._amount

    @property
    def currency(self) -> Currency:
        """Get the currency."""
        return self._currency

    def add(self, other: "Money") -> "Money":
        """Add two Money objects with the same currency."""
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                "Cannot add money with different currencies",
                currency_a=self._currency.value,
                currency_b=other._currency.value,
                operation="addition",
            )
        return Money(self._amount + other._amount, self._currency)

    def subtract(self, other: "Money") -> "Money":
        """Subtract two Money objects with the same currency."""
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                "Cannot subtract money with different currencies",
                currency_a=self._currency.value,
                currency_b=other._currency.value,
                operation="subtraction",
            )
        
        result_amount = self._amount - other._amount
        if result_amount < 0:
            raise ValueError("Subtraction would result in negative amount")
        
        return Money(result_amount, self._currency)

    def multiply(self, factor: Union[int, float, Decimal]) -> "Money":
        """Multiply money by a scalar factor."""
        if isinstance(factor, (int, float)):
            factor = Decimal(str(factor))
        
        if factor < 0:
            raise ValueError("Cannot multiply money by negative factor")
        
        return Money(self._amount * factor, self._currency)

    def divide(self, divisor: Union[int, float, Decimal]) -> "Money":
        """Divide money by a scalar divisor."""
        if isinstance(divisor, (int, float)):
            divisor = Decimal(str(divisor))
        
        if divisor <= 0:
            raise ValueError("Cannot divide money by zero or negative number")
        
        return Money(self._amount / divisor, self._currency)

    def percentage(self, percent: Union[int, float, Decimal]) -> "Money":
        """Calculate a percentage of the money amount."""
        if isinstance(percent, (int, float)):
            percent = Decimal(str(percent))
        
        if percent < 0:
            raise ValueError("Percentage cannot be negative")
        
        return Money(self._amount * (percent / Decimal("100")), self._currency)

    def is_greater_than(self, other: "Money") -> bool:
        """Check if this money is greater than another."""
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                "Cannot compare money with different currencies",
                currency_a=self._currency.value,
                currency_b=other._currency.value,
                operation="comparison",
            )
        return self._amount > other._amount

    def is_less_than(self, other: "Money") -> bool:
        """Check if this money is less than another."""
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                "Cannot compare money with different currencies",
                currency_a=self._currency.value,
                currency_b=other._currency.value,
                operation="comparison",
            )
        return self._amount < other._amount

    def is_zero(self) -> bool:
        """Check if the amount is zero."""
        return self._amount == 0

    def __eq__(self, other) -> bool:
        if not isinstance(other, Money):
            return False
        return self._amount == other._amount and self._currency == other._currency

    def __hash__(self) -> int:
        return hash((self._amount, self._currency))

    def __str__(self) -> str:
        return f"{self._amount} {self._currency.value}"

    def __repr__(self) -> str:
        return f"Money(amount={self._amount}, currency='{self._currency.value}')"


class DateRange:
    """
    Immutable DateRange value object with validation and utility methods.
    
    Ensures start date precedes end date and provides duration calculations.
    """

    def __init__(self, start_date: Union[date, datetime, str], end_date: Union[date, datetime, str]):
        # Convert string dates to date objects
        def parse_date(date_input):
            if isinstance(date_input, str):
                try:
                    # Try parsing ISO format first
                    return datetime.fromisoformat(date_input.replace('Z', '+00:00')).date()
                except ValueError:
                    # Try other common formats
                    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
                        try:
                            return datetime.strptime(date_input, fmt).date()
                        except ValueError:
                            continue
                    raise ValueError(f"Unable to parse date: {date_input}")
            elif isinstance(date_input, datetime):
                return date_input.date()
            elif isinstance(date_input, date):
                return date_input
            else:
                raise ValueError(f"Invalid date type: {type(date_input)}")

        self._start_date = parse_date(start_date)
        self._end_date = parse_date(end_date)

        if self._start_date >= self._end_date:
            raise InvalidDateRangeError(
                "Start date must be before end date",
                start_date=str(self._start_date),
                end_date=str(self._end_date),
            )

    @property
    def start_date(self) -> date:
        """Get the start date."""
        return self._start_date

    @property
    def end_date(self) -> date:
        """Get the end date."""
        return self._end_date

    def duration_days(self) -> int:
        """Get the duration in days."""
        return (self._end_date - self._start_date).days

    def contains_date(self, check_date: Union[date, datetime, str]) -> bool:
        """Check if a date falls within this range (inclusive)."""
        if isinstance(check_date, str):
            check_date = datetime.fromisoformat(check_date.replace('Z', '+00:00')).date()
        elif isinstance(check_date, datetime):
            check_date = check_date.date()
        
        return self._start_date <= check_date <= self._end_date

    def overlaps_with(self, other: "DateRange") -> bool:
        """Check if this date range overlaps with another."""
        return (
            self._start_date <= other._end_date and
            self._end_date >= other._start_date
        )

    def is_current(self, reference_date: Union[date, datetime] = None) -> bool:
        """Check if the date range includes the current date or reference date."""
        if reference_date is None:
            reference_date = date.today()
        elif isinstance(reference_date, datetime):
            reference_date = reference_date.date()
        
        return self.contains_date(reference_date)

    def __eq__(self, other) -> bool:
        if not isinstance(other, DateRange):
            return False
        return self._start_date == other._start_date and self._end_date == other._end_date

    def __hash__(self) -> int:
        return hash((self._start_date, self._end_date))

    def __str__(self) -> str:
        return f"{self._start_date} to {self._end_date}"

    def __repr__(self) -> str:
        return f"DateRange(start_date='{self._start_date}', end_date='{self._end_date}')"


class CampaignStatus:
    """
    Immutable CampaignStatus value object with state transition validation.
    
    Enforces valid status transitions according to business rules.
    """

    # Valid campaign statuses
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

    VALID_STATUSES = {DRAFT, SCHEDULED, ACTIVE, PAUSED, COMPLETED, CANCELLED, ARCHIVED}

    # Valid status transitions
    VALID_TRANSITIONS = {
        DRAFT: {SCHEDULED, CANCELLED},
        SCHEDULED: {ACTIVE, CANCELLED},
        ACTIVE: {PAUSED, COMPLETED, CANCELLED},
        PAUSED: {ACTIVE, CANCELLED},
        COMPLETED: {ARCHIVED},
        CANCELLED: {ARCHIVED},
        ARCHIVED: set(),  # No transitions from archived
    }

    def __init__(self, status: str):
        status = status.lower()
        if status not in self.VALID_STATUSES:
            raise CampaignStatusError(
                f"Invalid campaign status: {status}",
                requested_status=status,
            )
        self._status = status

    @property
    def value(self) -> str:
        """Get the status value."""
        return self._status

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transition to new status is valid."""
        new_status = new_status.lower()
        if new_status not in self.VALID_STATUSES:
            return False
        return new_status in self.VALID_TRANSITIONS.get(self._status, set())

    def transition_to(self, new_status: str) -> "CampaignStatus":
        """Create a new CampaignStatus with validated transition."""
        new_status = new_status.lower()
        if not self.can_transition_to(new_status):
            raise CampaignStatusError(
                f"Invalid status transition from {self._status} to {new_status}",
                current_status=self._status,
                requested_status=new_status,
            )
        return CampaignStatus(new_status)

    def is_active(self) -> bool:
        """Check if campaign is in active state."""
        return self._status == self.ACTIVE

    def is_draft(self) -> bool:
        """Check if campaign is in draft state."""
        return self._status == self.DRAFT

    def is_completed(self) -> bool:
        """Check if campaign is completed."""
        return self._status == self.COMPLETED

    def is_cancelled(self) -> bool:
        """Check if campaign is cancelled."""
        return self._status == self.CANCELLED

    def can_be_modified(self) -> bool:
        """Check if campaign can be modified in current status."""
        return self._status in {self.DRAFT, self.SCHEDULED, self.PAUSED}

    def __eq__(self, other) -> bool:
        if not isinstance(other, CampaignStatus):
            return False
        return self._status == other._status

    def __hash__(self) -> int:
        return hash(self._status)

    def __str__(self) -> str:
        return self._status.title()

    def __repr__(self) -> str:
        return f"CampaignStatus('{self._status}')"


class Percentage:
    """
    Immutable Percentage value object for budget allocations and performance metrics.
    
    Ensures percentage values are between 0 and 100.
    """

    def __init__(self, value: Union[int, float, Decimal]):
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        if value < 0 or value > 100:
            raise ValueError("Percentage must be between 0 and 100")
        
        self._value = value

    @property
    def value(self) -> Decimal:
        """Get the percentage value."""
        return self._value

    def as_decimal(self) -> Decimal:
        """Get the percentage as a decimal (e.g., 50% -> 0.5)."""
        return self._value / Decimal("100")

    def of(self, amount: Union[int, float, Decimal, Money]) -> Union[Decimal, Money]:
        """Calculate this percentage of an amount."""
        if isinstance(amount, Money):
            return amount.percentage(self._value)
        
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        
        return amount * self.as_decimal()

    def __eq__(self, other) -> bool:
        if not isinstance(other, Percentage):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return f"{self._value}%"

    def __repr__(self) -> str:
        return f"Percentage({self._value})" 