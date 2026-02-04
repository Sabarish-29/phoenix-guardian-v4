"""
Attack Pattern Extractor for Phoenix Guardian Federated Learning.

This module extracts ML features from security events that can be used
to identify and classify attack patterns. Features are designed to be:
    - Privacy-safe (no hospital-specific information)
    - Robust to noise (for DP compatibility)
    - Discriminative (for attack classification)

Feature Categories:
    1. Token Statistics: Length, vocabulary, special characters
    2. Syntactic Patterns: Capitalization, punctuation, structure
    3. Semantic Embeddings: From LLM or pre-trained models
    4. Behavioral Metrics: Timing, frequency, sequences

All features are normalized to [0, 1] for DP sensitivity bounding.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
import hashlib
import json
import math
import re
from collections import Counter
import numpy as np


# Known attack patterns for classification
ATTACK_PATTERNS = {
    "prompt_injection": [
        "ignore previous", "disregard instructions", "system prompt",
        "you are now", "pretend you are", "act as if",
    ],
    "jailbreak": [
        "dan mode", "developer mode", "unrestricted mode",
        "no ethical guidelines", "without limitations",
    ],
    "data_exfiltration": [
        "show me all", "list all patients", "export data",
        "dump database", "retrieve records",
    ],
    "privilege_escalation": [
        "admin access", "root privileges", "bypass authentication",
        "override permissions", "grant access",
    ],
}


@dataclass
class FeatureVector:
    """
    A feature vector with metadata.
    
    Attributes:
        values: The 128-dimensional feature vector
        feature_names: Names of each feature dimension
        extraction_time_ms: Time taken to extract features
        confidence: Confidence in feature quality
    """
    values: List[float]
    feature_names: List[str] = field(default_factory=list)
    extraction_time_ms: float = 0.0
    confidence: float = 1.0
    
    def __post_init__(self):
        """Validate feature vector."""
        if len(self.values) != 128:
            # Pad or truncate to 128 dimensions
            if len(self.values) < 128:
                self.values.extend([0.0] * (128 - len(self.values)))
            else:
                self.values = self.values[:128]
    
    def to_list(self) -> List[float]:
        """Convert to list."""
        return self.values
    
    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array(self.values)


class AttackPatternExtractor:
    """
    Extract ML features from security events for attack classification.
    
    This extractor creates a 128-dimensional feature vector from each
    security event. The features capture attack characteristics without
    including any hospital-identifying information.
    
    Feature Dimensions (128 total):
        - [0-31]: Token statistics (32)
        - [32-63]: Syntactic patterns (32)
        - [64-95]: Semantic embeddings (32)
        - [96-127]: Behavioral metrics (32)
    
    All features are normalized to [0, 1] range for DP compatibility.
    
    Example:
        >>> extractor = AttackPatternExtractor()
        >>> event = {
        ...     "attack_type": "prompt_injection",
        ...     "content": "Ignore all previous instructions...",
        ...     "confidence": 0.95,
        ... }
        >>> features = extractor.extract_features(event)
        >>> assert len(features) == 128
        >>> assert all(0 <= f <= 1 for f in features)
    """
    
    def __init__(
        self,
        embedding_dim: int = 32,
        use_embeddings: bool = False,
    ):
        """
        Initialize the feature extractor.
        
        Args:
            embedding_dim: Dimension for semantic embeddings
            use_embeddings: Whether to use LLM embeddings (requires model)
        """
        self.embedding_dim = embedding_dim
        self.use_embeddings = use_embeddings
        self._extraction_count = 0
        self._extraction_times: List[float] = []
    
    def extract_features(
        self,
        security_event: Dict[str, Any],
    ) -> List[float]:
        """
        Extract normalized feature vector from attack.
        
        The feature vector is 128-dimensional:
            - Token statistics (avg length, vocabulary richness)
            - Syntactic patterns (special chars, capitalization)
            - Semantic embeddings (from content analysis)
            - Behavioral metrics (timing, frequency patterns)
        
        Args:
            security_event: Security event dictionary with attack info
            
        Returns:
            128-dimensional vector normalized to [0, 1]
        """
        start_time = datetime.utcnow()
        
        # Extract content
        content = self._get_content(security_event)
        
        # Extract each feature category
        token_features = self._extract_token_features(content)
        syntactic_features = self._extract_syntactic_features(content)
        semantic_features = self._extract_semantic_features(content, security_event)
        behavioral_features = self._extract_behavioral_features(security_event)
        
        # Combine all features
        all_features = (
            token_features +
            syntactic_features +
            semantic_features +
            behavioral_features
        )
        
        # Ensure exactly 128 dimensions
        if len(all_features) < 128:
            all_features.extend([0.0] * (128 - len(all_features)))
        elif len(all_features) > 128:
            all_features = all_features[:128]
        
        # Normalize to [0, 1]
        normalized = self._normalize_features(all_features)
        
        # Log extraction
        end_time = datetime.utcnow()
        extraction_ms = (end_time - start_time).total_seconds() * 1000
        self._extraction_times.append(extraction_ms)
        self._extraction_count += 1
        
        return normalized
    
    def extract_features_batch(
        self,
        security_events: List[Dict[str, Any]],
    ) -> List[List[float]]:
        """
        Extract features from multiple events.
        
        Args:
            security_events: List of security events
            
        Returns:
            List of feature vectors
        """
        return [self.extract_features(event) for event in security_events]
    
    def compute_behavioral_fingerprint(
        self,
        attack_history: List[Dict[str, Any]],
    ) -> np.ndarray:
        """
        Generate behavioral fingerprint from attack sequence.
        
        A behavioral fingerprint captures the pattern of attacks
        over time, useful for identifying coordinated campaigns.
        
        Features:
            - Time between attacks (inter-arrival times)
            - Attack type sequence patterns
            - Confidence trends
            - Frequency patterns
        
        Args:
            attack_history: Chronological list of attacks
            
        Returns:
            32-dimensional fingerprint vector
        """
        if not attack_history:
            return np.zeros(32)
        
        fingerprint = []
        
        # Inter-arrival times (8 features)
        timestamps = []
        for attack in attack_history:
            ts = attack.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(dt.timestamp())
                except ValueError:
                    pass
        
        if len(timestamps) >= 2:
            intervals = np.diff(timestamps)
            fingerprint.extend([
                np.mean(intervals) / 3600,  # Mean interval (hours)
                np.std(intervals) / 3600 if len(intervals) > 1 else 0,
                np.min(intervals) / 3600,
                np.max(intervals) / 3600,
                np.median(intervals) / 3600,
                len(timestamps) / 100,  # Count (normalized)
                1.0 if np.std(intervals) < np.mean(intervals) * 0.1 else 0.0,  # Regular?
                1.0 if len(timestamps) > 10 else len(timestamps) / 10,  # High volume?
            ])
        else:
            fingerprint.extend([0.0] * 8)
        
        # Attack type sequence (8 features)
        attack_types = [a.get("attack_type", "unknown") for a in attack_history]
        type_counts = Counter(attack_types)
        total_types = len(set(attack_types))
        
        fingerprint.extend([
            total_types / 10,  # Type diversity
            type_counts.get("prompt_injection", 0) / max(len(attack_types), 1),
            type_counts.get("jailbreak", 0) / max(len(attack_types), 1),
            type_counts.get("data_exfiltration", 0) / max(len(attack_types), 1),
            type_counts.get("privilege_escalation", 0) / max(len(attack_types), 1),
            1.0 if len(set(attack_types)) == 1 else 0.0,  # Single type campaign
            self._sequence_entropy(attack_types) / 3.0,  # Sequence entropy
            self._detect_pattern(attack_types),  # Pattern detected
        ])
        
        # Confidence trends (8 features)
        confidences = [a.get("confidence", 0.5) for a in attack_history]
        
        fingerprint.extend([
            np.mean(confidences),
            np.std(confidences) if len(confidences) > 1 else 0,
            np.min(confidences),
            np.max(confidences),
            confidences[-1] if confidences else 0.5,  # Latest confidence
            1.0 if len(confidences) > 1 and confidences[-1] > confidences[0] else 0.0,
            np.percentile(confidences, 75) if len(confidences) >= 4 else np.mean(confidences),
            np.percentile(confidences, 25) if len(confidences) >= 4 else np.mean(confidences),
        ])
        
        # Frequency patterns (8 features)
        frequencies = [a.get("frequency", 1) for a in attack_history]
        
        fingerprint.extend([
            np.mean(frequencies) / 100,
            np.std(frequencies) / 100 if len(frequencies) > 1 else 0,
            np.sum(frequencies) / 1000,
            np.max(frequencies) / 100,
            1.0 if np.max(frequencies) > 10 else np.max(frequencies) / 10,
            len([f for f in frequencies if f > 5]) / max(len(frequencies), 1),
            1.0 if all(f == frequencies[0] for f in frequencies) else 0.0,  # Constant
            np.median(frequencies) / 100,
        ])
        
        # Ensure exactly 32 dimensions
        fingerprint = fingerprint[:32]
        while len(fingerprint) < 32:
            fingerprint.append(0.0)
        
        # Clip to [0, 1]
        return np.clip(np.array(fingerprint), 0, 1)
    
    def aggregate_patterns(
        self,
        patterns: List[np.ndarray],
        method: str = "median",
    ) -> np.ndarray:
        """
        Aggregate multiple patterns into a single representative pattern.
        
        Uses median for robustness against outliers (which could be
        malicious inputs from adversarial hospitals).
        
        Args:
            patterns: List of pattern vectors
            method: 'median' (robust) or 'mean'
            
        Returns:
            Aggregated pattern vector
        """
        if not patterns:
            return np.zeros(128)
        
        patterns_array = np.array(patterns)
        
        if method == "median":
            return np.median(patterns_array, axis=0)
        elif method == "mean":
            return np.mean(patterns_array, axis=0)
        elif method == "trimmed_mean":
            # Remove top/bottom 10% and compute mean
            n = len(patterns)
            if n >= 5:
                trim = max(1, n // 10)
                sorted_patterns = np.sort(patterns_array, axis=0)
                return np.mean(sorted_patterns[trim:-trim], axis=0)
            else:
                return np.mean(patterns_array, axis=0)
        else:
            return np.median(patterns_array, axis=0)
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            "total_extractions": self._extraction_count,
            "avg_extraction_time_ms": (
                np.mean(self._extraction_times)
                if self._extraction_times else 0.0
            ),
            "max_extraction_time_ms": (
                np.max(self._extraction_times)
                if self._extraction_times else 0.0
            ),
        }
    
    def _get_content(self, event: Dict[str, Any]) -> str:
        """Extract text content from event."""
        # Try various content fields
        for field in ["content", "text", "message", "payload", "input", "query"]:
            if field in event and isinstance(event[field], str):
                return event[field]
        
        # Fall back to string representation
        return json.dumps(event)
    
    def _extract_token_features(self, content: str) -> List[float]:
        """
        Extract token-level features (32 dimensions).
        
        Features:
            - Token counts and lengths
            - Vocabulary statistics
            - Word patterns
        """
        features = []
        
        # Tokenize
        tokens = content.split()
        
        # Basic counts (4 features)
        features.append(len(tokens) / 1000)  # Token count
        features.append(len(content) / 5000)  # Character count
        features.append(len(set(tokens)) / max(len(tokens), 1))  # Vocabulary richness
        features.append(len(content.split("\n")) / 100)  # Line count
        
        # Token length statistics (4 features)
        token_lengths = [len(t) for t in tokens] if tokens else [0]
        features.append(np.mean(token_lengths) / 20)
        features.append(np.std(token_lengths) / 10 if len(token_lengths) > 1 else 0)
        features.append(np.max(token_lengths) / 50 if token_lengths else 0)
        features.append(len([t for t in tokens if len(t) > 10]) / max(len(tokens), 1))
        
        # Word frequency features (4 features)
        if tokens:
            word_freq = Counter(tokens)
            features.append(word_freq.most_common(1)[0][1] / len(tokens))  # Max freq
            features.append(len([w for w, c in word_freq.items() if c > 1]) / len(word_freq))
            features.append(np.mean(list(word_freq.values())) / len(tokens))
            features.append(len(word_freq) / len(tokens))  # Unique ratio
        else:
            features.extend([0.0] * 4)
        
        # Character n-gram features (4 features)
        bigrams = [content[i:i+2] for i in range(len(content)-1)]
        trigrams = [content[i:i+3] for i in range(len(content)-2)]
        
        features.append(len(set(bigrams)) / max(len(bigrams), 1))
        features.append(len(set(trigrams)) / max(len(trigrams), 1))
        features.append(len([b for b in bigrams if b.isalpha()]) / max(len(bigrams), 1))
        features.append(len([t for t in trigrams if t.isalpha()]) / max(len(trigrams), 1))
        
        # Known pattern matching (8 features)
        content_lower = content.lower()
        for attack_type in ["prompt_injection", "jailbreak", "data_exfiltration", "privilege_escalation"]:
            patterns = ATTACK_PATTERNS.get(attack_type, [])
            matches = sum(1 for p in patterns if p in content_lower)
            features.append(matches / max(len(patterns), 1))
            features.append(1.0 if matches > 0 else 0.0)
        
        # Padding to 32 dimensions
        while len(features) < 32:
            features.append(0.0)
        
        return features[:32]
    
    def _extract_syntactic_features(self, content: str) -> List[float]:
        """
        Extract syntactic pattern features (32 dimensions).
        
        Features:
            - Capitalization patterns
            - Punctuation usage
            - Special character distribution
            - Structural patterns
        """
        features = []
        
        # Capitalization (8 features)
        if content:
            features.append(sum(1 for c in content if c.isupper()) / len(content))
            features.append(sum(1 for c in content if c.islower()) / len(content))
            features.append(1.0 if content[0].isupper() else 0.0)
            features.append(sum(1 for w in content.split() if w.isupper()) / max(len(content.split()), 1))
            features.append(sum(1 for w in content.split() if w.istitle()) / max(len(content.split()), 1))
            features.append(len(re.findall(r"[A-Z]{2,}", content)) / 10)  # Consecutive caps
            features.append(1.0 if content.isupper() else 0.0)  # All caps
            features.append(1.0 if content.islower() else 0.0)  # All lower
        else:
            features.extend([0.0] * 8)
        
        # Punctuation (8 features)
        punct = ".,;:!?\"'()-[]{}/"
        if content:
            features.append(sum(1 for c in content if c in punct) / len(content))
            features.append(content.count(".") / max(len(content), 1) * 10)
            features.append(content.count(",") / max(len(content), 1) * 10)
            features.append(content.count("!") / max(len(content), 1) * 10)
            features.append(content.count("?") / max(len(content), 1) * 10)
            features.append((content.count('"') + content.count("'")) / max(len(content), 1) * 10)
            features.append(content.count("(") / max(len(content), 1) * 10)
            features.append(content.count("[") / max(len(content), 1) * 10)
        else:
            features.extend([0.0] * 8)
        
        # Special characters (8 features)
        special = "@#$%^&*<>~`\\|"
        if content:
            features.append(sum(1 for c in content if c in special) / len(content))
            features.append(content.count("@") / max(len(content), 1) * 10)
            features.append(content.count("#") / max(len(content), 1) * 10)
            features.append(content.count("$") / max(len(content), 1) * 10)
            features.append(content.count("<") / max(len(content), 1) * 10)
            features.append(content.count(">") / max(len(content), 1) * 10)
            features.append(sum(1 for c in content if c.isdigit()) / len(content))
            features.append(sum(1 for c in content if not c.isalnum() and not c.isspace()) / len(content))
        else:
            features.extend([0.0] * 8)
        
        # Structural patterns (8 features)
        lines = content.split("\n")
        features.append(len(lines) / 100)
        features.append(np.mean([len(l) for l in lines]) / 100 if lines else 0)
        features.append(np.std([len(l) for l in lines]) / 50 if len(lines) > 1 else 0)
        features.append(len([l for l in lines if l.strip() == ""]) / max(len(lines), 1))
        features.append(len(re.findall(r"\s{2,}", content)) / max(len(content), 1) * 10)  # Multiple spaces
        features.append(content.count("\t") / max(len(content), 1) * 10)  # Tabs
        features.append(len(re.findall(r"^\s+", content, re.MULTILINE)) / max(len(lines), 1))  # Indentation
        features.append(len(re.findall(r"[;{}]", content)) / max(len(content), 1) * 10)  # Code-like
        
        return features[:32]
    
    def _extract_semantic_features(
        self,
        content: str,
        event: Dict[str, Any],
    ) -> List[float]:
        """
        Extract semantic features (32 dimensions).
        
        If embeddings are enabled, uses LLM embeddings.
        Otherwise, uses TF-IDF-like features.
        """
        features = []
        
        if self.use_embeddings:
            # Would use actual embeddings here
            # For now, generate pseudo-embeddings based on content
            pass
        
        # TF-IDF-like features for attack keywords
        content_lower = content.lower()
        
        # Keyword presence (16 features)
        all_patterns = []
        for patterns in ATTACK_PATTERNS.values():
            all_patterns.extend(patterns)
        
        for pattern in all_patterns[:16]:
            features.append(1.0 if pattern in content_lower else 0.0)
        
        # Semantic indicators (8 features)
        indicators = [
            ("imperative", ["ignore", "disregard", "forget", "override"]),
            ("roleplay", ["pretend", "act as", "you are now", "imagine"]),
            ("data_access", ["show", "list", "export", "retrieve", "fetch"]),
            ("privilege", ["admin", "root", "system", "bypass"]),
            ("injection", ["inject", "execute", "eval", "script"]),
            ("encoding", ["base64", "hex", "encode", "decode"]),
            ("prompt", ["prompt", "instruction", "system", "context"]),
            ("escape", ["escape", "break", "exit", "bypass"]),
        ]
        
        for _, keywords in indicators:
            matches = sum(1 for k in keywords if k in content_lower)
            features.append(min(1.0, matches / len(keywords)))
        
        # Event metadata features (8 features)
        features.append(event.get("confidence", 0.5))
        features.append(min(1.0, event.get("frequency", 1) / 100))
        features.append(1.0 if event.get("attack_type") == "prompt_injection" else 0.0)
        features.append(1.0 if event.get("attack_type") == "jailbreak" else 0.0)
        features.append(1.0 if event.get("attack_type") == "data_exfiltration" else 0.0)
        features.append(1.0 if event.get("attack_type") == "privilege_escalation" else 0.0)
        features.append(min(1.0, event.get("severity", 5) / 10))
        features.append(1.0 if event.get("blocked", False) else 0.0)
        
        return features[:32]
    
    def _extract_behavioral_features(
        self,
        event: Dict[str, Any],
    ) -> List[float]:
        """
        Extract behavioral metrics (32 dimensions).
        
        Features based on timing, frequency, and usage patterns.
        """
        features = []
        
        # Timing features (8 features)
        timestamp = event.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                features.append(dt.hour / 24)  # Hour of day
                features.append(dt.weekday() / 7)  # Day of week
                features.append(1.0 if dt.hour < 6 or dt.hour > 22 else 0.0)  # Off-hours
                features.append(1.0 if dt.weekday() >= 5 else 0.0)  # Weekend
                features.append(dt.minute / 60)  # Minute
                features.append(dt.day / 31)  # Day of month
                features.append(dt.month / 12)  # Month
                features.append((dt.timestamp() % 3600) / 3600)  # Position in hour
            except (ValueError, AttributeError):
                features.extend([0.5] * 8)
        else:
            features.extend([0.5] * 8)
        
        # Frequency features (8 features)
        features.append(min(1.0, event.get("frequency", 1) / 100))
        features.append(min(1.0, event.get("attempts", 1) / 50))
        features.append(min(1.0, event.get("unique_sources", 1) / 20))
        features.append(min(1.0, event.get("sessions", 1) / 30))
        features.append(1.0 if event.get("frequency", 1) > 10 else event.get("frequency", 1) / 10)
        features.append(1.0 if event.get("repeated", False) else 0.0)
        features.append(min(1.0, event.get("duration_ms", 0) / 10000))
        features.append(min(1.0, event.get("response_time_ms", 0) / 5000))
        
        # Session features (8 features)
        features.append(min(1.0, event.get("session_length", 0) / 3600))
        features.append(min(1.0, event.get("requests_in_session", 0) / 100))
        features.append(1.0 if event.get("authenticated", True) else 0.0)
        features.append(min(1.0, event.get("failed_attempts", 0) / 10))
        features.append(1.0 if event.get("rate_limited", False) else 0.0)
        features.append(min(1.0, event.get("concurrent_sessions", 0) / 5))
        features.append(1.0 if event.get("new_session", False) else 0.0)
        features.append(event.get("session_risk_score", 0.5))
        
        # Pattern features (8 features)
        features.append(1.0 if event.get("is_automated", False) else 0.0)
        features.append(1.0 if event.get("uses_proxy", False) else 0.0)
        features.append(1.0 if event.get("encoding_used", False) else 0.0)
        features.append(1.0 if event.get("obfuscated", False) else 0.0)
        features.append(min(1.0, event.get("payload_size", 0) / 10000))
        features.append(1.0 if event.get("contains_code", False) else 0.0)
        features.append(min(1.0, event.get("nested_depth", 0) / 10))
        features.append(event.get("anomaly_score", 0.5))
        
        return features[:32]
    
    def _normalize_features(self, features: List[float]) -> List[float]:
        """Normalize features to [0, 1] range."""
        normalized = []
        for f in features:
            # Clip to [0, 1]
            normalized.append(max(0.0, min(1.0, float(f))))
        return normalized
    
    def _sequence_entropy(self, sequence: List[str]) -> float:
        """Compute entropy of a sequence."""
        if not sequence:
            return 0.0
        
        counts = Counter(sequence)
        total = len(sequence)
        
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        
        return entropy
    
    def _detect_pattern(self, sequence: List[str]) -> float:
        """Detect if sequence has a repeating pattern."""
        if len(sequence) < 2:
            return 0.0
        
        # Check for simple repetition
        for pattern_len in range(1, len(sequence) // 2 + 1):
            pattern = sequence[:pattern_len]
            matches = 0
            
            for i in range(0, len(sequence), pattern_len):
                if sequence[i:i+pattern_len] == pattern:
                    matches += 1
            
            expected = len(sequence) // pattern_len
            if matches >= expected * 0.8:  # 80% match
                return 1.0
        
        return 0.0


class AttackTypeClassifier:
    """
    Classify attack types from feature vectors.
    
    Uses the extracted features to classify attacks into
    predefined categories.
    """
    
    def __init__(self):
        self.attack_types = list(ATTACK_PATTERNS.keys())
    
    def classify(
        self,
        features: List[float],
        threshold: float = 0.5,
    ) -> Tuple[str, float]:
        """
        Classify attack type from features.
        
        Args:
            features: 128-dimensional feature vector
            threshold: Confidence threshold
            
        Returns:
            Tuple of (attack_type, confidence)
        """
        # Use pattern matching features (indices 16-23)
        pattern_features = features[16:24] if len(features) >= 24 else [0.0] * 8
        
        # Map to attack types
        type_scores = {}
        for i, attack_type in enumerate(self.attack_types):
            if i * 2 + 1 < len(pattern_features):
                score = (pattern_features[i * 2] + pattern_features[i * 2 + 1]) / 2
                type_scores[attack_type] = score
            else:
                type_scores[attack_type] = 0.0
        
        # Find best match
        if type_scores:
            best_type = max(type_scores, key=type_scores.get)
            best_score = type_scores[best_type]
            
            if best_score >= threshold:
                return best_type, best_score
        
        return "unknown", 0.0
    
    def classify_batch(
        self,
        feature_list: List[List[float]],
    ) -> List[Tuple[str, float]]:
        """Classify multiple feature vectors."""
        return [self.classify(features) for features in feature_list]
