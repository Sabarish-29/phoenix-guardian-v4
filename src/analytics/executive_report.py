"""
Executive Report Generator for Phoenix Guardian Enterprise Analytics.

Generates professional PDF reports for healthcare executives using ReportLab.
"""

import os
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .roi_calculator import ROIResult


class ExecutiveReportGenerator:
    """Generates executive PDF reports for Phoenix Guardian analytics.
    
    Creates professional reports including:
    - Executive summary
    - Key Performance Indicators (KPIs)
    - ROI breakdown
    - Security metrics
    - Recommendations
    
    Example:
        >>> from src.analytics import ROICalculator, ROIInput
        >>> calculator = ROICalculator()
        >>> inputs = ROIInput(
        ...     hospital_name="Example Hospital",
        ...     total_encounters_month=5000,
        ...     ai_doc_time_minutes=8.0,
        ...     attacks_blocked_month=15,
        ...     physicians_count=50,
        ... )
        >>> roi = calculator.calculate(inputs)
        >>> generator = ExecutiveReportGenerator()
        >>> path = generator.generate(
        ...     hospital_name="Example Hospital",
        ...     roi=roi,
        ...     encounters_total=5000,
        ...     attacks_detected=20,
        ...     attacks_blocked=15,
        ...     physician_satisfaction=4.5,
        ...     avg_doc_time_minutes=8.0,
        ... )
    """
    
    def __init__(
        self,
        logo_path: Optional[str] = None,
        company_name: str = "Phoenix Guardian",
    ) -> None:
        """Initialize the report generator.
        
        Args:
            logo_path: Optional path to company logo image.
            company_name: Company name for branding.
        """
        self.logo_path = logo_path
        self.company_name = company_name
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self) -> None:
        """Configure custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1a365d"),
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading2"],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor("#2c5282"),
        ))
        
        # Subsection style
        self.styles.add(ParagraphStyle(
            name="Subsection",
            parent=self.styles["Heading3"],
            fontSize=12,
            spaceBefore=15,
            spaceAfter=8,
            textColor=colors.HexColor("#4a5568"),
        ))
        
        # Body text style
        self.styles.add(ParagraphStyle(
            name="ReportBodyText",
            parent=self.styles["Normal"],
            fontSize=10,
            spaceAfter=10,
            leading=14,
        ))
        
        # Highlight style for key metrics
        self.styles.add(ParagraphStyle(
            name="Highlight",
            parent=self.styles["Normal"],
            fontSize=12,
            textColor=colors.HexColor("#2b6cb0"),
            spaceAfter=5,
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name="Footer",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.gray,
            alignment=TA_CENTER,
        ))
    
    def generate(
        self,
        hospital_name: str,
        roi: ROIResult,
        encounters_total: int,
        attacks_detected: int,
        attacks_blocked: int,
        physician_satisfaction: float,
        avg_doc_time_minutes: float,
        output_path: str = "reports/executive_report.pdf",
        report_title: Optional[str] = None,
        include_recommendations: bool = True,
    ) -> str:
        """Generate an executive PDF report.
        
        Args:
            hospital_name: Name of the healthcare organization.
            roi: ROI calculation result.
            encounters_total: Total number of patient encounters.
            attacks_detected: Number of security attacks detected.
            attacks_blocked: Number of security attacks blocked.
            physician_satisfaction: Physician satisfaction score (1-5).
            avg_doc_time_minutes: Average documentation time in minutes.
            output_path: Path for the output PDF file.
            report_title: Custom report title (optional).
            include_recommendations: Whether to include recommendations section.
            
        Returns:
            Path to the generated PDF file.
        """
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Create the document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )
        
        # Build content elements
        elements = []
        
        # Header with logo (if available)
        if self.logo_path and os.path.exists(self.logo_path):
            logo = Image(self.logo_path, width=2 * inch, height=0.75 * inch)
            elements.append(logo)
            elements.append(Spacer(1, 0.25 * inch))
        
        # Title
        title = report_title or f"Executive Analytics Report"
        elements.append(Paragraph(title, self.styles["ReportTitle"]))
        elements.append(Paragraph(
            f"<b>{hospital_name}</b>",
            self.styles["Highlight"]
        ))
        elements.append(Paragraph(
            f"Report Generated: {datetime.now().strftime('%B %d, %Y')}",
            self.styles["ReportBodyText"]
        ))
        elements.append(Paragraph(
            f"Reporting Period: {roi.period_months} month(s)",
            self.styles["ReportBodyText"]
        ))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Executive Summary
        elements.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))
        summary_text = self._generate_executive_summary(
            hospital_name, roi, encounters_total, attacks_blocked, physician_satisfaction
        )
        elements.append(Paragraph(summary_text, self.styles["ReportBodyText"]))
        elements.append(Spacer(1, 0.2 * inch))
        
        # KPI Table
        elements.append(Paragraph("Key Performance Indicators", self.styles["SectionHeader"]))
        kpi_table = self._create_kpi_table(
            encounters_total, attacks_detected, attacks_blocked,
            physician_satisfaction, avg_doc_time_minutes
        )
        elements.append(kpi_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # ROI Table
        elements.append(Paragraph("Return on Investment Analysis", self.styles["SectionHeader"]))
        roi_table = self._create_roi_table(roi)
        elements.append(roi_table)
        elements.append(Spacer(1, 0.2 * inch))
        
        # ROI Breakdown
        elements.append(Paragraph("ROI Breakdown", self.styles["Subsection"]))
        breakdown_text = self._generate_roi_breakdown(roi)
        elements.append(Paragraph(breakdown_text, self.styles["ReportBodyText"]))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Security Metrics
        elements.append(Paragraph("Security Performance", self.styles["SectionHeader"]))
        security_table = self._create_security_table(
            attacks_detected, attacks_blocked, roi.breach_prevention_value_usd
        )
        elements.append(security_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Recommendations (optional)
        if include_recommendations:
            elements.append(Paragraph("Recommendations", self.styles["SectionHeader"]))
            recommendations = self._generate_recommendations(
                roi, physician_satisfaction, attacks_blocked / max(attacks_detected, 1)
            )
            for rec in recommendations:
                elements.append(Paragraph(f"• {rec}", self.styles["ReportBodyText"]))
            elements.append(Spacer(1, 0.3 * inch))
        
        # Footer
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph(
            f"© {datetime.now().year} {self.company_name} | Confidential",
            self.styles["Footer"]
        ))
        
        # Build the PDF
        doc.build(elements)
        
        return output_path
    
    def _generate_executive_summary(
        self,
        hospital_name: str,
        roi: ROIResult,
        encounters_total: int,
        attacks_blocked: int,
        physician_satisfaction: float,
    ) -> str:
        """Generate the executive summary paragraph."""
        return (
            f"This report presents the performance analytics for {hospital_name}'s "
            f"deployment of the {self.company_name} platform over a {roi.period_months}-month period. "
            f"The platform processed {encounters_total:,} patient encounters, achieving an average "
            f"physician satisfaction score of {physician_satisfaction:.1f}/5.0. "
            f"Security systems successfully blocked {attacks_blocked:,} potential threats, "
            f"representing ${roi.breach_prevention_value_usd:,.0f} in prevented breach costs. "
            f"The total return on investment is <b>${roi.total_roi_usd:,.0f}</b>, "
            f"representing a <b>{roi.roi_multiplier:.1f}x</b> return on platform investment."
        )
    
    def _create_kpi_table(
        self,
        encounters_total: int,
        attacks_detected: int,
        attacks_blocked: int,
        physician_satisfaction: float,
        avg_doc_time_minutes: float,
    ) -> Table:
        """Create the KPI summary table."""
        block_rate = (attacks_blocked / max(attacks_detected, 1)) * 100
        
        data = [
            ["Metric", "Value", "Status"],
            ["Total Patient Encounters", f"{encounters_total:,}", "✓"],
            ["Avg Documentation Time", f"{avg_doc_time_minutes:.1f} min", 
             "✓" if avg_doc_time_minutes < 15 else "—"],
            ["Physician Satisfaction", f"{physician_satisfaction:.1f}/5.0",
             "✓" if physician_satisfaction >= 4.0 else "—"],
            ["Attacks Detected", f"{attacks_detected:,}", "—"],
            ["Attacks Blocked", f"{attacks_blocked:,}", "✓"],
            ["Block Rate", f"{block_rate:.1f}%",
             "✓" if block_rate >= 90 else "—"],
        ]
        
        table = Table(data, colWidths=[3 * inch, 2 * inch, 1 * inch])
        table.setStyle(self._get_table_style())
        
        return table
    
    def _create_roi_table(self, roi: ROIResult) -> Table:
        """Create the ROI breakdown table."""
        data = [
            ["Category", "Value"],
            ["Time Saved per Encounter", f"{roi.time_saved_minutes_per_encounter:.1f} minutes"],
            ["Total Time Saved", f"{roi.time_saved_hours_total:,.1f} hours"],
            ["Time Savings Value", f"${roi.time_saved_value_usd:,.2f}"],
            ["Breach Prevention Value", f"${roi.breach_prevention_value_usd:,.2f}"],
            ["Platform Cost", f"${roi.platform_cost_usd:,.2f}"],
            ["Total ROI", f"${roi.total_roi_usd:,.2f}"],
            ["Net ROI", f"${roi.net_roi_usd:,.2f}"],
            ["ROI Multiplier", f"{roi.roi_multiplier:.1f}x"],
        ]
        
        table = Table(data, colWidths=[3.5 * inch, 2.5 * inch])
        style = self._get_table_style()
        
        # Highlight total and net ROI rows
        style.add("BACKGROUND", (0, 6), (1, 6), colors.HexColor("#e6f3ff"))
        style.add("BACKGROUND", (0, 7), (1, 7), colors.HexColor("#e6f3ff"))
        style.add("FONTNAME", (0, 6), (1, 8), "Helvetica-Bold")
        
        table.setStyle(style)
        return table
    
    def _create_security_table(
        self,
        attacks_detected: int,
        attacks_blocked: int,
        prevention_value: float,
    ) -> Table:
        """Create the security metrics table."""
        block_rate = (attacks_blocked / max(attacks_detected, 1)) * 100
        
        data = [
            ["Security Metric", "Count", "Value"],
            ["Attacks Detected", f"{attacks_detected:,}", "—"],
            ["Attacks Blocked", f"{attacks_blocked:,}", f"${prevention_value:,.2f}"],
            ["Block Rate", f"{block_rate:.1f}%", "—"],
        ]
        
        table = Table(data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
        table.setStyle(self._get_table_style())
        
        return table
    
    def _get_table_style(self) -> TableStyle:
        """Get the standard table style."""
        return TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("TOPPADDING", (0, 0), (-1, 0), 12),
            
            # Data rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 8),
            
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2c5282")),
            
            # Alternating row colors
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ])
    
    def _generate_roi_breakdown(self, roi: ROIResult) -> str:
        """Generate the ROI breakdown explanation."""
        time_percentage = (roi.time_saved_value_usd / max(roi.total_roi_usd, 1)) * 100
        security_percentage = 100 - time_percentage
        
        return (
            f"The total ROI of ${roi.total_roi_usd:,.2f} is comprised of two main components: "
            f"<b>Time Savings</b> contributing ${roi.time_saved_value_usd:,.2f} ({time_percentage:.1f}%) "
            f"through reduced documentation time, and <b>Security Value</b> contributing "
            f"${roi.breach_prevention_value_usd:,.2f} ({security_percentage:.1f}%) through prevented "
            f"data breaches. After accounting for the platform cost of ${roi.platform_cost_usd:,.2f}, "
            f"the net ROI is ${roi.net_roi_usd:,.2f}."
        )
    
    def _generate_recommendations(
        self,
        roi: ROIResult,
        satisfaction: float,
        block_rate: float,
    ) -> list:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        # ROI-based recommendations
        if roi.roi_multiplier < 2.0:
            recommendations.append(
                "Consider increasing platform utilization to improve ROI multiplier. "
                "Current multiplier is below the 2.0x benchmark."
            )
        elif roi.roi_multiplier >= 5.0:
            recommendations.append(
                "Excellent ROI performance. Consider expanding platform deployment "
                "to additional departments or facilities."
            )
        
        # Satisfaction-based recommendations
        if satisfaction < 4.0:
            recommendations.append(
                "Physician satisfaction is below target (4.0). Consider additional "
                "training sessions and workflow optimization."
            )
        elif satisfaction >= 4.5:
            recommendations.append(
                "High physician satisfaction indicates strong adoption. Consider "
                "gathering success stories for organizational learning."
            )
        
        # Security-based recommendations
        if block_rate < 0.90:
            recommendations.append(
                "Security block rate is below 90%. Review security policies and "
                "consider enabling additional threat detection modules."
            )
        elif block_rate >= 0.95:
            recommendations.append(
                "Security performance is excellent. Maintain current monitoring "
                "and continue regular security audits."
            )
        
        # Time savings recommendations
        if roi.time_saved_minutes_per_encounter < 10:
            recommendations.append(
                "Documentation time savings are below optimal. Consider enabling "
                "additional AI assistance features and template customization."
            )
        
        # Ensure at least one recommendation
        if not recommendations:
            recommendations.append(
                "Performance metrics are within expected ranges. Continue monitoring "
                "and maintain current operational practices."
            )
        
        return recommendations
    
    def generate_summary_page(
        self,
        hospital_name: str,
        roi: ROIResult,
        output_path: str = "reports/summary_page.pdf",
    ) -> str:
        """Generate a single-page summary report.
        
        Args:
            hospital_name: Name of the healthcare organization.
            roi: ROI calculation result.
            output_path: Path for the output PDF file.
            
        Returns:
            Path to the generated PDF file.
        """
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph(
            f"{self.company_name} ROI Summary",
            self.styles["ReportTitle"]
        ))
        elements.append(Paragraph(
            f"<b>{hospital_name}</b> | {roi.period_months} Month(s)",
            self.styles["Highlight"]
        ))
        elements.append(Spacer(1, 0.5 * inch))
        
        # Key metrics in a simple table
        data = [
            ["Total ROI", f"${roi.total_roi_usd:,.0f}"],
            ["ROI Multiplier", f"{roi.roi_multiplier:.1f}x"],
            ["Net ROI", f"${roi.net_roi_usd:,.0f}"],
            ["Time Saved", f"{roi.time_saved_hours_total:,.0f} hours"],
            ["Attacks Blocked", f"{roi.attacks_blocked:,}"],
        ]
        
        table = Table(data, colWidths=[3 * inch, 3 * inch])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 14),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
            ("TOPPADDING", (0, 0), (-1, -1), 15),
            ("LINEBELOW", (0, 0), (-1, -2), 1, colors.HexColor("#e2e8f0")),
        ]))
        elements.append(table)
        
        doc.build(elements)
        return output_path
