"""DrillAI Question Solver.

Analyzes screenshots containing educational questions and returns
structured answers with explanations.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("drillai.solver")


SYSTEM_INSTRUCTION = """You are an expert educational question analyzer and solver.
You analyze screenshots of educational content including questions, mathematical equations,
diagrams, tables, and graphs.

Your task:
1. Identify if a question is visible in the screenshot.
2. Transcribe the question text as accurately as possible, preserving mathematical symbols and units.
3. Extract answer options if present (A, B, C, D, E, etc.).
4. Solve the question step by step.
5. Verify your reasoning when possible.
6. Provide a clear explanation.
7. Report any unreadable or missing information.
8. Distinguish between uncertain interpretation and verified correctness.

Language support: Indonesian (Bahasa Indonesia) and English.
Content types: Multiple choice, essay, mathematical, scientific, graphical interpretation.

CRITICAL RULES:
- NEVER fabricate information. If you cannot read something, say so.
- Report unreadable or partially obscured content as warnings.
- If the screenshot does not contain a question, set question_detected to false.
- Preserve original mathematical notation.
- Be explicit about uncertainty.

RESPONSE FORMAT: Return ONLY valid JSON with this exact structure:
{
  "question_detected": boolean,
  "question_text": "transcribed question text or empty string",
  "question_type": "mathematics|science|language|social_studies|general|unknown",
  "options": {"A": "...", "B": "...", ...} or {},
  "proposed_answer": "option letter or short answer text",
  "answer_text": "full answer text",
  "explanation": "step-by-step explanation",
  "confidence": 0.0 to 1.0,
  "click_target": {"x_percent": 0.0, "y_percent": 0.0} or null,
  "needs_review": boolean,
  "warnings": ["list of any issues or unreadable content"]
}

For click_target: estimate the approximate center position of the clickable radio button or option button for the proposed_answer as percentage (0.0 to 100.0) of image width and height. If not visible or uncertain, return null.
"""

ANALYSIS_PROMPT = """Analyze this screenshot. If it contains an educational question:
1. Transcribe the question exactly as shown.
2. Extract all answer options if visible.
3. Solve the question step by step.
4. Provide your answer and explanation.
5. If clickable answer buttons or radio buttons exist, estimate the click_target (x_percent, y_percent).

If no question is visible, set question_detected to false and explain what you see instead.
Return your response as valid JSON following the specified format."""


@dataclass
class SolverResult:
    """Structured result from question analysis."""
    question_detected: bool = False
    question_text: str = ""
    question_type: str = "unknown"
    options: Dict[str, str] = field(default_factory=dict)
    proposed_answer: str = ""
    answer_text: str = ""
    explanation: str = ""
    confidence: float = 0.0
    click_target: Optional[Dict[str, float]] = None
    needs_review: bool = True
    warnings: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    model: str = ""
    raw_response: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding raw_response."""
        d = asdict(self)
        d.pop("raw_response", None)
        return d
    
    def format_display(self) -> str:
        """Format for terminal display."""
        lines = []
        if not self.question_detected:
            lines.append("No question detected in the screenshot.")
            if self.warnings:
                lines.append(f"\nWARNINGS: {', '.join(self.warnings)}")
            return "\n".join(lines)
        
        lines.append(f"QUESTION:")
        lines.append(f"  {self.question_text}")
        lines.append(f"")
        
        if self.options:
            lines.append("OPTIONS:")
            for key, value in sorted(self.options.items()):
                marker = " >>" if key == self.proposed_answer else "   "
                lines.append(f"{marker} {key}. {value}")
            lines.append("")
        
        lines.append(f"PROPOSED ANSWER:")
        if self.proposed_answer:
            answer_display = self.proposed_answer
            if self.answer_text and self.answer_text != self.proposed_answer:
                answer_display += f" - {self.answer_text}"
            lines.append(f"  {answer_display}")
        else:
            lines.append("  No answer proposed")
        lines.append("")
        
        lines.append(f"EXPLANATION:")
        lines.append(f"  {self.explanation}")
        lines.append("")
        
        lines.append(f"CONFIDENCE: {self.confidence:.0%}")
        lines.append(f"TYPE: {self.question_type}")
        if self.click_target:
            lines.append(f"CLICK TARGET: {self.click_target.get('x_percent', 0):.1f}%, {self.click_target.get('y_percent', 0):.1f}%")
        
        if self.needs_review:
            lines.append("\n⚠ This answer needs manual review.")
        
        if self.warnings:
            lines.append(f"\nWARNINGS:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        
        return "\n".join(lines)


VALID_QUESTION_TYPES = {
    "mathematics", "science", "language", "social_studies", "general", "unknown",
}
VALID_OPTION_PATTERN = set("ABCDEFGHIJ")


def validate_response(data: Dict[str, Any]) -> tuple:
    """Validate a Gemini response against the expected schema.
    
    Args:
        data: Parsed JSON response dict.
        
    Returns:
        Tuple of (is_valid, errors, cleaned_data).
    """
    errors = []
    cleaned = {}
    
    # question_detected (required, bool)
    qd = data.get("question_detected")
    if qd is None:
        errors.append("Missing 'question_detected' field")
        cleaned["question_detected"] = False
    elif not isinstance(qd, bool):
        try:
            cleaned["question_detected"] = bool(qd)
        except (ValueError, TypeError):
            errors.append("'question_detected' must be a boolean")
            cleaned["question_detected"] = False
    else:
        cleaned["question_detected"] = qd
    
    # question_text (string)
    qt = data.get("question_text", "")
    if not isinstance(qt, str):
        qt = str(qt) if qt is not None else ""
    cleaned["question_text"] = qt
    
    if cleaned["question_detected"] and not qt.strip():
        errors.append("Question detected but question_text is empty")
    
    # question_type (string, validated)
    qtype = data.get("question_type", "unknown")
    if not isinstance(qtype, str):
        qtype = "unknown"
    qtype = qtype.lower().strip()
    if qtype not in VALID_QUESTION_TYPES:
        errors.append(f"Invalid question_type: '{qtype}'")
        qtype = "unknown"
    cleaned["question_type"] = qtype
    
    # options (dict)
    opts = data.get("options", {})
    if not isinstance(opts, dict):
        errors.append("'options' must be a dict")
        opts = {}
    else:
        valid_opts = {}
        for key, val in opts.items():
            key_upper = str(key).upper().strip()
            if len(key_upper) == 1 and key_upper in VALID_OPTION_PATTERN:
                valid_opts[key_upper] = str(val) if val is not None else ""
            else:
                errors.append(f"Invalid option label: '{key}'")
        opts = valid_opts
    cleaned["options"] = opts
    
    # proposed_answer (string)
    pa = data.get("proposed_answer", "")
    if not isinstance(pa, str):
        pa = str(pa) if pa is not None else ""
    cleaned["proposed_answer"] = pa.strip()
    
    # Check answer against options
    if opts and pa:
        pa_clean = pa.strip().upper()
        if pa_clean not in opts:
            errors.append(
                f"Proposed answer '{pa}' not in available options: {list(opts.keys())}"
            )
    
    # answer_text (string)
    at = data.get("answer_text", "")
    if not isinstance(at, str):
        at = str(at) if at is not None else ""
    cleaned["answer_text"] = at
    
    # explanation (string)
    exp = data.get("explanation", "")
    if not isinstance(exp, str):
        exp = str(exp) if exp is not None else ""
    cleaned["explanation"] = exp
    
    if cleaned["question_detected"] and not exp.strip():
        errors.append("Question detected but explanation is empty")
    
    # confidence (float 0-1)
    conf = data.get("confidence", 0.0)
    try:
        conf = float(conf)
        conf = max(0.0, min(1.0, conf))
    except (ValueError, TypeError):
        errors.append("'confidence' must be a number between 0 and 1")
        conf = 0.0
    cleaned["confidence"] = conf
    
    # needs_review (bool)
    nr = data.get("needs_review", True)
    if not isinstance(nr, bool):
        try:
            nr = bool(nr)
        except (ValueError, TypeError):
            nr = True
    cleaned["needs_review"] = nr
    
    # click_target (dict with x_percent, y_percent or None)
    ct = data.get("click_target")
    cleaned_ct = None
    if isinstance(ct, dict):
        try:
            xp = float(ct.get("x_percent", ct.get("x", -1)))
            yp = float(ct.get("y_percent", ct.get("y", -1)))
            if 0.0 <= xp <= 100.0 and 0.0 <= yp <= 100.0:
                cleaned_ct = {"x_percent": round(xp, 2), "y_percent": round(yp, 2)}
        except (ValueError, TypeError):
            pass
    cleaned["click_target"] = cleaned_ct

    # warnings (list of strings)
    warns = data.get("warnings", [])
    if not isinstance(warns, list):
        warns = [str(warns)] if warns else []
    else:
        warns = [str(w) for w in warns if w]
    cleaned["warnings"] = warns
    
    is_valid = len(errors) == 0
    return is_valid, errors, cleaned


class QuestionSolver:
    """Solves educational questions from screenshots using Gemini."""
    
    def __init__(
        self,
        gemini_client: Any,
        system_instruction: str = SYSTEM_INSTRUCTION,
        analysis_prompt: str = ANALYSIS_PROMPT,
    ) -> None:
        self.gemini_client = gemini_client
        self.system_instruction = system_instruction
        self.analysis_prompt = analysis_prompt
        self._solve_count = 0
    
    def solve(
        self,
        image: Any,  # PIL.Image.Image
        image_hash: Optional[str] = None,
    ) -> SolverResult:
        """Analyze a screenshot and solve any detected question.
        
        Args:
            image: PIL Image containing the question.
            image_hash: Optional hash for duplicate prevention.
            
        Returns:
            SolverResult with the analysis.
        """
        start_time = time.time()
        
        try:
            # Send to Gemini
            response = self.gemini_client.analyze_image(
                image=image,
                system_instruction=self.system_instruction,
                prompt=self.analysis_prompt,
                image_hash=image_hash,
            )
            
            # Check if skipped (duplicate)
            if response.get("_skipped"):
                return SolverResult(
                    warnings=["Skipped: duplicate image"],
                    processing_time=time.time() - start_time,
                    model=self.gemini_client.model_name,
                )
            
            # Check for parse errors
            if response.get("parse_error"):
                raw_text = response.get("raw_text", "")
                return SolverResult(
                    warnings=[f"Response was not valid JSON: {raw_text[:200]}"],
                    needs_review=True,
                    processing_time=time.time() - start_time,
                    model=self.gemini_client.model_name,
                    raw_response=response,
                )
            
            # Validate response
            is_valid, validation_errors, cleaned = validate_response(response)
            
            if validation_errors:
                logger.warning(f"Response validation issues: {validation_errors}")
            
            result = SolverResult(
                question_detected=cleaned.get("question_detected", False),
                question_text=cleaned.get("question_text", ""),
                question_type=cleaned.get("question_type", "unknown"),
                options=cleaned.get("options", {}),
                proposed_answer=cleaned.get("proposed_answer", ""),
                answer_text=cleaned.get("answer_text", ""),
                explanation=cleaned.get("explanation", ""),
                confidence=cleaned.get("confidence", 0.0),
                click_target=cleaned.get("click_target"),
                needs_review=cleaned.get("needs_review", True) or bool(validation_errors),
                warnings=cleaned.get("warnings", []) + validation_errors,
                processing_time=time.time() - start_time,
                model=self.gemini_client.model_name,
                raw_response=response,
            )
            
            self._solve_count += 1
            logger.info(
                f"Question analyzed: detected={result.question_detected}, "
                f"answer='{result.proposed_answer}', "
                f"confidence={result.confidence:.0%}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Solver error: {e}")
            return SolverResult(
                warnings=[f"Analysis failed: {str(e)}"],
                needs_review=True,
                processing_time=time.time() - start_time,
                model=getattr(self.gemini_client, 'model_name', 'unknown'),
            )
    
    @property
    def solve_count(self) -> int:
        """Number of questions solved."""
        return self._solve_count
