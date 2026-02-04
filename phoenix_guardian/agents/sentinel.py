"""SentinelAgent - Security Threat Detection using Claude Sonnet 4.

Detects potential security threats in user inputs using pattern matching,
ML-based classification, and AI-powered analysis for comprehensive threat detection.
"""

from phoenix_guardian.agents.base import BaseAgent
from typing import Dict, Any, Optional
import re
import os


class SentinelAgent(BaseAgent):
    """Detects potential security threats in user inputs.
    
    Combines regex pattern matching for known attack vectors,
    ML-based classification for learned patterns, and
    Claude-powered analysis for subtle or novel threats.
    """
    
    # Simple threat patterns
    THREAT_PATTERNS = [
        (r"<script", "XSS_ATTEMPT"),
        (r"DROP\s+TABLE", "SQL_INJECTION"),
        (r"';\s*--", "SQL_INJECTION"),
        (r"\.\.\/", "PATH_TRAVERSAL"),
        (r"admin.*password", "CREDENTIAL_PROBE"),
    ]
    
    def __init__(self):
        """Initialize agent with optional ML model."""
        super().__init__()
        self.ml_model = None
        self.vectorizer = None
        self._load_ml_model()
    
    def _load_ml_model(self):
        """Load trained ML model if available."""
        model_path = "models/threat_detector/model.joblib"
        vectorizer_path = "models/threat_detector/vectorizer.joblib"
        
        if os.path.exists(model_path) and os.path.exists(vectorizer_path):
            try:
                import joblib
                self.ml_model = joblib.load(model_path)
                self.vectorizer = joblib.load(vectorizer_path)
            except Exception as e:
                # Silently fail - ML model is optional enhancement
                pass
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze input for security threats.
        
        Args:
            input_data: {
                "user_input": str,
                "context": str (optional)
            }
        
        Returns:
            {
                "threat_detected": bool,
                "threat_type": str,
                "confidence": float,
                "details": str (optional),
                "method": str,
                "agent": str
            }
        """
        user_input = input_data.get("user_input", "")
        
        # 1. Pattern matching (fast check first)
        detected = self._pattern_check(user_input)
        if detected["threat_detected"]:
            detected["method"] = "pattern"
            detected["agent"] = "SentinelAgent"
            return detected
        
        # 2. ML model check if available
        if self.ml_model and self.vectorizer and user_input:
            ml_result = self._ml_threat_check(user_input)
            if ml_result["threat_detected"]:
                ml_result["agent"] = "SentinelAgent"
                return ml_result
        
        # 3. AI-powered analysis as fallback
        if user_input:
            ai_analysis = await self._ai_threat_check(user_input)
            if "suspicious" in ai_analysis.lower() or "malicious" in ai_analysis.lower():
                return {
                    "threat_detected": True,
                    "threat_type": "AI_FLAGGED",
                    "confidence": 0.7,
                    "details": ai_analysis,
                    "method": "ai",
                    "agent": "SentinelAgent"
                }
        
        return {
            "threat_detected": False,
            "threat_type": "SAFE",
            "confidence": 0.9,
            "details": "No threats detected",
            "method": "comprehensive",
            "agent": "SentinelAgent"
        }
    
    def _pattern_check(self, text: str) -> Dict[str, Any]:
        """Check for known attack patterns."""
        for pattern, threat_type in self.THREAT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    "threat_detected": True,
                    "threat_type": threat_type,
                    "confidence": 0.95,
                    "pattern_matched": pattern
                }
        
        return {"threat_detected": False}
    
    def _ml_threat_check(self, text: str) -> Dict[str, Any]:
        """Use trained ML model for threat detection."""
        if not self.ml_model or not self.vectorizer:
            return {"threat_detected": False}
        
        try:
            vec = self.vectorizer.transform([text])
            prediction = self.ml_model.predict(vec)[0]
            probability = self.ml_model.predict_proba(vec)[0][1]
            
            # Only flag as threat if probability is high enough
            if prediction == 1 and probability >= 0.7:
                return {
                    "threat_detected": True,
                    "threat_type": "ML_DETECTED",
                    "confidence": float(probability),
                    "method": "ml"
                }
        except Exception:
            pass
        
        return {"threat_detected": False}
    
    async def _ai_threat_check(self, text: str) -> str:
        """Use Claude to detect subtle threats."""
        prompt = f"""Analyze this user input for potential security threats:

Input: {text}

Is this a potential SQL injection, XSS, path traversal, or other attack attempt?
Reply with YES or NO followed by a brief reason (1-2 sentences)."""
        
        return await self._call_claude(prompt)
