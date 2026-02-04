"""
Change Management Evidence Collector (CC8).

Collects evidence of change management controls:
- Code deployments to production
- Pull request approvals
- Code review records
- Testing results before deployment
- Emergency change procedures

DEMONSTRATES:
- Changes require approval before production
- Code review required (2+ reviewers)
- Automated testing gates deployment
- Emergency change process documented
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

from phoenix_guardian.compliance.evidence_types import (
    Evidence,
    DeploymentEvidence,
    ChangeApprovalEvidence,
    TSCCriterion,
    EvidenceType,
    EvidenceSource,
)

logger = logging.getLogger(__name__)


class ChangeManagementCollector:
    """
    Collects CC8 (Change Management) evidence.
    
    Sources:
    - GitHub Actions (CI/CD logs)
    - Pull request metadata
    - Deployment logs
    - Change request system
    """
    
    # Control descriptions
    CONTROL_DESCRIPTIONS = {
        "deployment": "Production deployments require approval and automated testing",
        "code_review": "All code changes require review by at least 2 reviewers",
        "testing": "Automated tests must pass before deployment",
        "approval": "Changes require documented approval before production deployment",
        "emergency": "Emergency changes follow expedited but documented process",
    }
    
    # Minimum reviewers required
    MIN_REVIEWERS = 2
    
    async def collect(
        self,
        start_date: str,
        end_date: str
    ) -> List[Evidence]:
        """
        Collect all change management evidence.
        """
        evidence: List[Evidence] = []
        
        # Production deployments
        deployment_evidence = await self._collect_deployments(
            start_date, end_date
        )
        evidence.extend(deployment_evidence)
        
        # Code reviews
        review_evidence = await self._collect_code_reviews(
            start_date, end_date
        )
        evidence.extend(review_evidence)
        
        # Test results
        test_evidence = await self._collect_test_results(
            start_date, end_date
        )
        evidence.extend(test_evidence)
        
        # Change approvals
        approval_evidence = await self._collect_change_approvals(
            start_date, end_date
        )
        evidence.extend(approval_evidence)
        
        logger.info(f"Collected {len(evidence)} change management evidence items")
        return evidence
    
    async def _collect_deployments(
        self,
        start_date: str,
        end_date: str
    ) -> List[DeploymentEvidence]:
        """
        Collect production deployment records.
        
        SOURCE: GitHub Actions, CI/CD logs
        DEMONSTRATES: Approval required, testing passed
        """
        # In production: Query GitHub Actions API
        # GET /repos/{owner}/{repo}/actions/runs
        
        deployments: List[DeploymentEvidence] = []
        
        # Mock: Production deployments
        for i in range(5):
            deployment = DeploymentEvidence(
                evidence_id=f"deploy_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.DEPLOYMENT_RECORD,
                evidence_source=EvidenceSource.GITHUB_ACTIONS,
                tsc_criteria=[TSCCriterion.CC8_CHANGE_MANAGEMENT],
                control_description=self.CONTROL_DESCRIPTIONS["deployment"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "workflow_name": "Deploy to Production",
                    "workflow_run_id": f"run_{i:06d}",
                    "conclusion": "success",
                    "tests_run": 3315,
                    "tests_passed": 3315,
                },
                deployment_id=f"deployment_{uuid.uuid4().hex[:8]}",
                git_commit_sha=f"abc123def456{i:03d}",
                pull_request_number=f"PR-{1000 + i}",
                approver_ids=["reviewer_1", "reviewer_2"],
                tests_passed=True,
                test_coverage_percent=87.5,
                environment="production",
                rollback_available=True,
            )
            deployment.data_hash = deployment.compute_hash()
            deployments.append(deployment)
        
        return deployments
    
    async def _collect_code_reviews(
        self,
        start_date: str,
        end_date: str
    ) -> List[Evidence]:
        """
        Collect code review evidence.
        
        SOURCE: GitHub Pull Request API
        DEMONSTRATES: All changes reviewed by 2+ reviewers
        """
        reviews: List[Evidence] = []
        
        # Mock: Code reviews
        for i in range(8):
            review = Evidence(
                evidence_id=f"review_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.CODE_REVIEW,
                evidence_source=EvidenceSource.GITHUB_ACTIONS,
                tsc_criteria=[TSCCriterion.CC8_CHANGE_MANAGEMENT],
                control_description=self.CONTROL_DESCRIPTIONS["code_review"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "pull_request": f"PR-{1000 + i}",
                    "title": f"Feature: Implement feature {i}",
                    "author": f"developer_{i % 5}",
                    "reviewers": ["reviewer_1", "reviewer_2"],
                    "approvals": 2,
                    "changes_requested": 0,
                    "comments": 5 + i,
                    "files_changed": 10 + i,
                    "lines_added": 200 + (i * 50),
                    "lines_removed": 50 + (i * 10),
                    "merged_at": datetime.now().isoformat(),
                },
            )
            review.data_hash = review.compute_hash()
            reviews.append(review)
        
        return reviews
    
    async def _collect_test_results(
        self,
        start_date: str,
        end_date: str
    ) -> List[Evidence]:
        """
        Collect automated test results.
        
        SOURCE: CI/CD pipeline
        DEMONSTRATES: Tests pass before deployment
        """
        results: List[Evidence] = []
        
        # Mock: Test results per deployment
        for i in range(5):
            result = Evidence(
                evidence_id=f"test_result_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.CODE_REVIEW,  # Reusing for test results
                evidence_source=EvidenceSource.GITHUB_ACTIONS,
                tsc_criteria=[TSCCriterion.CC8_CHANGE_MANAGEMENT],
                control_description=self.CONTROL_DESCRIPTIONS["testing"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "test_suite": "full",
                    "tests_total": 3315,
                    "tests_passed": 3315,
                    "tests_failed": 0,
                    "tests_skipped": 0,
                    "coverage_percent": 87.5,
                    "duration_seconds": 245,
                    "commit_sha": f"abc123def456{i:03d}",
                },
            )
            result.data_hash = result.compute_hash()
            results.append(result)
        
        return results
    
    async def _collect_change_approvals(
        self,
        start_date: str,
        end_date: str
    ) -> List[ChangeApprovalEvidence]:
        """
        Collect change approval records.
        
        SOURCE: Change management system
        DEMONSTRATES: Changes require approval
        """
        approvals: List[ChangeApprovalEvidence] = []
        
        # Mock: Change approvals
        for i in range(5):
            approval = ChangeApprovalEvidence(
                evidence_id=f"approval_{uuid.uuid4().hex[:12]}",
                evidence_type=EvidenceType.CHANGE_APPROVAL,
                evidence_source=EvidenceSource.GITHUB_ACTIONS,
                tsc_criteria=[TSCCriterion.CC8_CHANGE_MANAGEMENT],
                control_description=self.CONTROL_DESCRIPTIONS["approval"],
                collected_at=datetime.now().isoformat(),
                event_timestamp=start_date,
                data_hash="",
                data={
                    "approval_type": "production_deployment",
                    "risk_level": "medium",
                    "rollback_plan": True,
                },
                change_id=f"CHG-{1000 + i}",
                change_type="feature_release",
                requestor_id=f"developer_{i}",
                approver_ids=["lead_1", "security_1"],
                approval_timestamp=datetime.now().isoformat(),
                justification=f"Feature release for sprint {i + 1}",
            )
            approval.data_hash = approval.compute_hash()
            approvals.append(approval)
        
        return approvals
    
    async def get_deployment_statistics(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Get deployment statistics for dashboards.
        """
        return {
            "total_deployments": 5,
            "successful_deployments": 5,
            "failed_deployments": 0,
            "rollbacks": 0,
            "average_deploy_time_minutes": 12,
            "deployments_with_approval": 5,
            "deployments_with_tests": 5,
        }
