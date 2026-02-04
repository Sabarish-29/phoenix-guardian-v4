"""
ROI Calculator for Phoenix Guardian Enterprise Analytics.

Calculates return on investment metrics for healthcare organizations
using AI-powered documentation and security features.
"""

from dataclasses import dataclass
from typing import Optional

# Industry Constants
AVG_HEALTHCARE_BREACH_COST_USD: float = 10_900_000  # Average cost of a healthcare data breach
TRADITIONAL_DOC_TIME_MINUTES: float = 25.0  # Average time for traditional documentation
PHYSICIAN_HOURLY_RATE_USD: float = 150.0  # Average physician hourly rate
DEFAULT_PLATFORM_COST_USD: float = 50_000.0  # Default monthly platform cost


@dataclass
class ROIInput:
    """Input parameters for ROI calculation.
    
    Attributes:
        hospital_name: Name of the healthcare organization.
        total_encounters_month: Average number of patient encounters per month.
        ai_doc_time_minutes: Average AI-assisted documentation time in minutes.
        attacks_blocked_month: Number of security attacks blocked per month.
        physicians_count: Number of physicians using the platform.
        months_active: Number of months the platform has been active.
        platform_cost_usd: Monthly platform cost (optional, uses default if not provided).
    """
    hospital_name: str
    total_encounters_month: int
    ai_doc_time_minutes: float
    attacks_blocked_month: int
    physicians_count: int
    months_active: int = 1
    platform_cost_usd: Optional[float] = None
    
    def __post_init__(self) -> None:
        """Validate input parameters."""
        if self.total_encounters_month < 0:
            raise ValueError("total_encounters_month must be non-negative")
        if self.ai_doc_time_minutes < 0:
            raise ValueError("ai_doc_time_minutes must be non-negative")
        if self.ai_doc_time_minutes > TRADITIONAL_DOC_TIME_MINUTES:
            raise ValueError(
                f"ai_doc_time_minutes ({self.ai_doc_time_minutes}) cannot exceed "
                f"traditional time ({TRADITIONAL_DOC_TIME_MINUTES})"
            )
        if self.attacks_blocked_month < 0:
            raise ValueError("attacks_blocked_month must be non-negative")
        if self.physicians_count < 0:
            raise ValueError("physicians_count must be non-negative")
        if self.months_active < 1:
            raise ValueError("months_active must be at least 1")
        if self.platform_cost_usd is not None and self.platform_cost_usd < 0:
            raise ValueError("platform_cost_usd must be non-negative")


@dataclass
class ROIResult:
    """Result of ROI calculation.
    
    Attributes:
        hospital_name: Name of the healthcare organization.
        period_months: Number of months in the calculation period.
        time_saved_minutes_per_encounter: Minutes saved per encounter.
        time_saved_hours_total: Total hours saved across all encounters.
        time_saved_value_usd: Dollar value of time saved.
        attacks_blocked: Total number of attacks blocked.
        breach_prevention_value_usd: Dollar value of prevented breaches.
        total_roi_usd: Total ROI in dollars.
        roi_multiplier: ROI as a multiplier of platform cost.
        platform_cost_usd: Total platform cost for the period.
        net_roi_usd: Net ROI after subtracting platform cost.
    """
    hospital_name: str
    period_months: int
    time_saved_minutes_per_encounter: float
    time_saved_hours_total: float
    time_saved_value_usd: float
    attacks_blocked: int
    breach_prevention_value_usd: float
    total_roi_usd: float
    roi_multiplier: float
    platform_cost_usd: float = 0.0
    net_roi_usd: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        return {
            "hospital_name": self.hospital_name,
            "period_months": self.period_months,
            "time_saved_minutes_per_encounter": round(self.time_saved_minutes_per_encounter, 2),
            "time_saved_hours_total": round(self.time_saved_hours_total, 2),
            "time_saved_value_usd": round(self.time_saved_value_usd, 2),
            "attacks_blocked": self.attacks_blocked,
            "breach_prevention_value_usd": round(self.breach_prevention_value_usd, 2),
            "total_roi_usd": round(self.total_roi_usd, 2),
            "roi_multiplier": round(self.roi_multiplier, 2),
            "platform_cost_usd": round(self.platform_cost_usd, 2),
            "net_roi_usd": round(self.net_roi_usd, 2),
        }
    
    def summary(self) -> str:
        """Generate a human-readable summary of the ROI result."""
        return (
            f"ROI Summary for {self.hospital_name}\n"
            f"{'=' * 50}\n"
            f"Period: {self.period_months} month(s)\n"
            f"Time Saved: {self.time_saved_hours_total:,.1f} hours "
            f"(${self.time_saved_value_usd:,.2f})\n"
            f"Attacks Blocked: {self.attacks_blocked} "
            f"(${self.breach_prevention_value_usd:,.2f} in prevented losses)\n"
            f"Platform Cost: ${self.platform_cost_usd:,.2f}\n"
            f"Total ROI: ${self.total_roi_usd:,.2f}\n"
            f"Net ROI: ${self.net_roi_usd:,.2f}\n"
            f"ROI Multiplier: {self.roi_multiplier:.1f}x\n"
        )


class ROICalculator:
    """Calculator for Phoenix Guardian platform ROI.
    
    Calculates the return on investment based on:
    - Time saved through AI-assisted documentation
    - Value of prevented security breaches
    - Platform costs
    
    Example:
        >>> calculator = ROICalculator()
        >>> inputs = ROIInput(
        ...     hospital_name="Example Hospital",
        ...     total_encounters_month=5000,
        ...     ai_doc_time_minutes=8.0,
        ...     attacks_blocked_month=15,
        ...     physicians_count=50,
        ...     months_active=12,
        ... )
        >>> result = calculator.calculate(inputs)
        >>> print(f"Total ROI: ${result.total_roi_usd:,.2f}")
    """
    
    def __init__(
        self,
        breach_cost_usd: float = AVG_HEALTHCARE_BREACH_COST_USD,
        traditional_doc_time: float = TRADITIONAL_DOC_TIME_MINUTES,
        physician_rate_usd: float = PHYSICIAN_HOURLY_RATE_USD,
        breach_probability: float = 0.001,
    ) -> None:
        """Initialize the ROI calculator.
        
        Args:
            breach_cost_usd: Average cost of a healthcare data breach.
            traditional_doc_time: Traditional documentation time in minutes.
            physician_rate_usd: Physician hourly rate in USD.
            breach_probability: Probability that a blocked attack would have 
                               resulted in a breach (default 0.1% per attack).
        """
        self.breach_cost_usd = breach_cost_usd
        self.traditional_doc_time = traditional_doc_time
        self.physician_rate_usd = physician_rate_usd
        self.breach_probability = breach_probability
    
    def calculate(self, inputs: ROIInput) -> ROIResult:
        """Calculate ROI based on the provided inputs.
        
        The calculation includes:
        1. Time Savings: (traditional_time - ai_time) × encounters × months / 60 × hourly_rate
        2. Breach Prevention: attacks × months × breach_probability × breach_cost
        3. ROI Multiplier: total_roi / (platform_cost × months)
        
        Args:
            inputs: ROI calculation input parameters.
            
        Returns:
            ROIResult containing all calculated metrics.
        """
        # Calculate time saved per encounter
        time_saved_per_encounter = self.traditional_doc_time - inputs.ai_doc_time_minutes
        
        # Calculate total encounters over the period
        total_encounters = inputs.total_encounters_month * inputs.months_active
        
        # Calculate total time saved in hours
        total_time_saved_minutes = time_saved_per_encounter * total_encounters
        total_time_saved_hours = total_time_saved_minutes / 60.0
        
        # Calculate dollar value of time saved
        time_saved_value = total_time_saved_hours * self.physician_rate_usd
        
        # Calculate total attacks blocked
        total_attacks_blocked = inputs.attacks_blocked_month * inputs.months_active
        
        # Calculate breach prevention value
        # Each blocked attack has a probability of preventing a breach
        breach_prevention_value = (
            total_attacks_blocked * self.breach_probability * self.breach_cost_usd
        )
        
        # Calculate total ROI
        total_roi = time_saved_value + breach_prevention_value
        
        # Calculate platform cost (explicitly check None to allow 0.0)
        platform_cost = (
            inputs.platform_cost_usd 
            if inputs.platform_cost_usd is not None 
            else DEFAULT_PLATFORM_COST_USD
        )
        total_platform_cost = platform_cost * inputs.months_active
        
        # Calculate net ROI
        net_roi = total_roi - total_platform_cost
        
        # Calculate ROI multiplier (avoid division by zero)
        if total_platform_cost > 0:
            roi_multiplier = total_roi / total_platform_cost
        else:
            roi_multiplier = float("inf") if total_roi > 0 else 0.0
        
        return ROIResult(
            hospital_name=inputs.hospital_name,
            period_months=inputs.months_active,
            time_saved_minutes_per_encounter=time_saved_per_encounter,
            time_saved_hours_total=total_time_saved_hours,
            time_saved_value_usd=time_saved_value,
            attacks_blocked=total_attacks_blocked,
            breach_prevention_value_usd=breach_prevention_value,
            total_roi_usd=total_roi,
            roi_multiplier=roi_multiplier,
            platform_cost_usd=total_platform_cost,
            net_roi_usd=net_roi,
        )
    
    def calculate_break_even_months(
        self,
        encounters_per_month: int,
        ai_doc_time_minutes: float,
        attacks_blocked_month: int,
        platform_cost_usd: Optional[float] = None,
    ) -> float:
        """Calculate the number of months to break even.
        
        Args:
            encounters_per_month: Average encounters per month.
            ai_doc_time_minutes: AI documentation time in minutes.
            attacks_blocked_month: Attacks blocked per month.
            platform_cost_usd: Monthly platform cost.
            
        Returns:
            Number of months to break even (may be fractional).
        """
        monthly_cost = platform_cost_usd or DEFAULT_PLATFORM_COST_USD
        
        # Calculate monthly value
        time_saved_per_encounter = self.traditional_doc_time - ai_doc_time_minutes
        monthly_time_saved_hours = (time_saved_per_encounter * encounters_per_month) / 60.0
        monthly_time_value = monthly_time_saved_hours * self.physician_rate_usd
        
        monthly_breach_value = (
            attacks_blocked_month * self.breach_probability * self.breach_cost_usd
        )
        
        monthly_value = monthly_time_value + monthly_breach_value
        
        if monthly_value <= 0:
            return float("inf")
        
        return monthly_cost / monthly_value
    
    def project_annual_roi(self, inputs: ROIInput) -> ROIResult:
        """Project ROI for a full year based on current metrics.
        
        Args:
            inputs: Current ROI inputs (will be projected to 12 months).
            
        Returns:
            ROIResult projected for 12 months.
        """
        annual_inputs = ROIInput(
            hospital_name=inputs.hospital_name,
            total_encounters_month=inputs.total_encounters_month,
            ai_doc_time_minutes=inputs.ai_doc_time_minutes,
            attacks_blocked_month=inputs.attacks_blocked_month,
            physicians_count=inputs.physicians_count,
            months_active=12,
            platform_cost_usd=inputs.platform_cost_usd,
        )
        return self.calculate(annual_inputs)
    
    def compare_scenarios(
        self,
        base_inputs: ROIInput,
        improved_ai_time: Optional[float] = None,
        increased_encounters: Optional[int] = None,
    ) -> dict:
        """Compare ROI between current and improved scenarios.
        
        Args:
            base_inputs: Current baseline inputs.
            improved_ai_time: Improved AI documentation time (optional).
            increased_encounters: Increased monthly encounters (optional).
            
        Returns:
            Dictionary with base and improved ROI results and delta.
        """
        base_result = self.calculate(base_inputs)
        
        improved_inputs = ROIInput(
            hospital_name=base_inputs.hospital_name,
            total_encounters_month=increased_encounters or base_inputs.total_encounters_month,
            ai_doc_time_minutes=improved_ai_time or base_inputs.ai_doc_time_minutes,
            attacks_blocked_month=base_inputs.attacks_blocked_month,
            physicians_count=base_inputs.physicians_count,
            months_active=base_inputs.months_active,
            platform_cost_usd=base_inputs.platform_cost_usd,
        )
        improved_result = self.calculate(improved_inputs)
        
        return {
            "base": base_result,
            "improved": improved_result,
            "delta_roi_usd": improved_result.total_roi_usd - base_result.total_roi_usd,
            "delta_multiplier": improved_result.roi_multiplier - base_result.roi_multiplier,
        }
