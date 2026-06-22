"""
ML Model Integration for Workflow Analysis

Integrates the trained Naive Bayes classifier into the workflow analysis pipeline
to provide validation, pattern discovery, and enhanced insights.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Optional

from src.analysis.train_nb import MultinomialNB, _iter_jsonl
from src.analysis.featurize_timelines import TimelineFeaturizer, tool_family_from_dataset_filename
from src.analysis.workflows import PRWorkflow, WorkflowEvent


def _parse_iso8601_utc(s: str) -> Optional[datetime]:
    """Parse ISO8601 UTC timestamp."""
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _load_model_json(path: str | Path) -> MultinomialNB:
    """Load a saved MultinomialNB model from JSON."""
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    m = MultinomialNB(alpha=float(obj["alpha"]))
    m.classes_ = list(obj["classes"])
    m.log_prior_ = {k: float(v) for k, v in obj["log_prior"].items()}
    m.log_prob_ = {c: {f: float(lp) for f, lp in d.items()} for c, d in obj["log_prob"].items()}
    m.vocab_ = list(obj["vocab"])
    return m


def extract_features_from_workflow(workflow: PRWorkflow) -> Dict:
    """
    Extract ML model features from a PRWorkflow object.
    Converts workflow events into the same feature format used for training.
    """
    # Map workflow tool names to model class names
    tool_mapping = {
        "Claude": "Claude_Code",
        "Copilot": "Copilot",
        "Cursor": "Cursor",
        "Devin": "Devin",
        "OpenAI": "OpenAI_Codex"
    }
    model_tool_name = tool_mapping.get(workflow.tool, workflow.tool)
    
    featurizer = TimelineFeaturizer(
        pr_key=workflow.pr_id,
        tool_family=model_tool_name
    )
    
    # Convert WorkflowEvents back to dict format for featurizer
    for wf_event in workflow.events:
        item = {
            "event": wf_event.event_type,
            "actor": {"login": wf_event.actor} if wf_event.actor else None,
            "created_at": wf_event.timestamp,
        }
        featurizer.update(item)
    
    features = featurizer.finalize()
    return features


@dataclass
class MLValidationResult:
    """Result of ML model validation for a workflow."""
    workflow: PRWorkflow
    predicted_tool: Optional[str]
    actual_tool: str
    confidence: float  # Log probability difference between top 2 predictions
    is_match: bool
    features: Dict


@dataclass
class ToolPatternInsight:
    """Insight about tool-specific patterns from ML model."""
    tool: str
    distinctive_features: List[Tuple[str, float]]  # (feature, score)
    pattern_summary: str


class MLWorkflowAnalyzer:
    """Integrates ML model into workflow analysis."""
    
    def __init__(self, model_path: str | Path = ".tmp/model_nb.json"):
        """Initialize with trained model."""
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Train model first: python -m src.analysis.pipeline train --save-model {model_path}"
            )
        self.model = _load_model_json(self.model_path)
        self.tool_mapping = {
            "Claude": "Claude_Code",
            "Copilot": "Copilot",
            "Cursor": "Cursor",
            "Devin": "Devin",
            "OpenAI": "OpenAI_Codex"
        }
    
    def predict_tool(self, workflow: PRWorkflow) -> Tuple[Optional[str], float]:
        """
        Predict which tool was used based on workflow features.
        Returns (predicted_tool, confidence_score).
        """
        features = extract_features_from_workflow(workflow)
        predicted = self.model.predict_one(features)
        
        # Calculate confidence as log probability difference
        if not predicted or not self.model.classes_:
            return None, 0.0
        
        # Get log probabilities for all classes
        feats: Dict[str, int] = {}
        for k, v in features.items():
            if isinstance(k, str) and (k.startswith("ev:") or k.startswith("tr:")):
                if isinstance(v, (int, float)) and v:
                    feats[k] = int(v)
        
        scores = {}
        for c in self.model.classes_:
            score = self.model.log_prior_[c]
            lp = self.model.log_prob_[c]
            for f, cnt in feats.items():
                if f in lp:
                    score += cnt * lp[f]
            scores[c] = score
        
        # Confidence = difference between top 2 scores
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_scores) >= 2:
            confidence = sorted_scores[0][1] - sorted_scores[1][1]
        else:
            confidence = sorted_scores[0][1] if sorted_scores else 0.0
        
        # Map back to workflow tool names
        reverse_mapping = {v: k for k, v in self.tool_mapping.items()}
        mapped_tool = reverse_mapping.get(predicted, predicted)
        
        return mapped_tool, confidence
    
    def validate_workflow(self, workflow: PRWorkflow) -> MLValidationResult:
        """
        Validate a workflow by comparing predicted tool to actual tool.
        """
        predicted_tool, confidence = self.predict_tool(workflow)
        features = extract_features_from_workflow(workflow)
        
        return MLValidationResult(
            workflow=workflow,
            predicted_tool=predicted_tool,
            actual_tool=workflow.tool,
            confidence=confidence,
            is_match=(predicted_tool == workflow.tool),
            features=features
        )
    
    def get_tool_patterns(self, top_k: int = 10) -> Dict[str, ToolPatternInsight]:
        """
        Extract distinctive workflow patterns for each tool from the model.
        """
        insights = {}
        
        for tool_name, model_class in self.tool_mapping.items():
            if model_class not in (self.model.classes_ or []):
                continue
            
            # Get top features for this tool class
            scores: List[Tuple[str, float]] = []
            for f in (self.model.vocab_ or []):
                lp_c = self.model.log_prob_[model_class].get(f)
                if lp_c is None:
                    continue
                # Score = log P(feature|class) - mean_{other classes} log P(feature|other)
                others = [
                    self.model.log_prob_[c2].get(f) 
                    for c2 in (self.model.classes_ or []) 
                    if c2 != model_class
                ]
                others = [x for x in others if x is not None]
                if not others:
                    continue
                score = lp_c - (sum(others) / len(others))
                scores.append((f, score))
            
            scores.sort(key=lambda t: t[1], reverse=True)
            top_features = scores[:top_k]
            
            # Generate pattern summary
            pattern_summary = self._summarize_patterns(top_features)
            
            insights[tool_name] = ToolPatternInsight(
                tool=tool_name,
                distinctive_features=top_features,
                pattern_summary=pattern_summary
            )
        
        return insights
    
    def _summarize_patterns(self, features: List[Tuple[str, float]]) -> str:
        """Generate human-readable summary of workflow patterns."""
        if not features:
            return "No distinctive patterns identified."
        
        summaries = []
        
        # Group by feature type
        events = [f for f, _ in features if f.startswith("ev:")]
        transitions = [f for f, _ in features if f.startswith("tr:")]
        
        if events:
            event_names = [e.replace("ev:", "") for e in events[:3]]
            summaries.append(f"Distinctive events: {', '.join(event_names)}")
        
        if transitions:
            # Extract common patterns from transitions
            transition_patterns = defaultdict(int)
            for t in transitions[:5]:
                parts = t.replace("tr:", "").split("->")
                if len(parts) == 2:
                    transition_patterns[parts[0]] += 1
            
            if transition_patterns:
                top_pattern = max(transition_patterns.items(), key=lambda x: x[1])
                summaries.append(f"Common transition: {top_pattern[0]} → ...")
        
        return "; ".join(summaries) if summaries else "Patterns identified but not easily summarized."
    
    def analyze_validation_results(
        self, 
        workflows: List[PRWorkflow],
        min_confidence: float = 1.0
    ) -> Dict:
        """
        Analyze validation results across multiple workflows.
        Returns statistics about prediction accuracy and mismatches.
        """
        results = [self.validate_workflow(w) for w in workflows]
        
        total = len(results)
        matches = sum(1 for r in results if r.is_match)
        mismatches = [r for r in results if not r.is_match]
        high_confidence = [r for r in results if r.confidence >= min_confidence]
        high_confidence_mismatches = [
            r for r in results 
            if not r.is_match and r.confidence >= min_confidence
        ]
        
        # Group mismatches by actual tool
        mismatch_by_tool = defaultdict(list)
        for r in mismatches:
            mismatch_by_tool[r.actual_tool].append(r)
        
        return {
            "total_workflows": total,
            "matches": matches,
            "mismatches": len(mismatches),
            "accuracy": matches / total if total > 0 else 0.0,
            "high_confidence_count": len(high_confidence),
            "high_confidence_mismatches": len(high_confidence_mismatches),
            "mismatch_by_tool": {
                tool: len(mismatches) 
                for tool, mismatches in mismatch_by_tool.items()
            },
            "sample_mismatches": [
                {
                    "pr_id": r.workflow.pr_id,
                    "actual": r.actual_tool,
                    "predicted": r.predicted_tool,
                    "confidence": r.confidence,
                    "url": r.workflow.url
                }
                for r in mismatches[:10]
            ]
        }
    
    def find_anomalous_workflows(
        self,
        workflows: List[PRWorkflow],
        confidence_threshold: float = 2.0
    ) -> List[MLValidationResult]:
        """
        Find workflows that are predicted with high confidence but mismatch actual tool.
        These may represent interesting edge cases or data quality issues.
        """
        results = [self.validate_workflow(w) for w in workflows]
        return [
            r for r in results 
            if not r.is_match and r.confidence >= confidence_threshold
        ]


def integrate_ml_analysis(workflow: PRWorkflow, analyzer: MLWorkflowAnalyzer) -> Dict:
    """
    Integrate ML analysis results into a workflow object.
    Returns a dictionary with ML-derived insights.
    """
    validation = analyzer.validate_workflow(workflow)
    patterns = analyzer.get_tool_patterns()
    
    return {
        "predicted_tool": validation.predicted_tool,
        "prediction_confidence": validation.confidence,
        "tool_match": validation.is_match,
        "tool_patterns": {
            tool: {
                "summary": insight.pattern_summary,
                "top_features": insight.distinctive_features[:5]
            }
            for tool, insight in patterns.items()
        }
    }
