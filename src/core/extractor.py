"""
PDF text extraction with layout information using pdfplumber.

Extracts words with bounding boxes and formats layout for LLM consumption.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pdfplumber

from src.config.settings import settings


@dataclass
class ExtractedDocument:
    """Extracted PDF document with rich layout information."""

    layout_text: str  # Formatted text with coordinates for LLM
    words: List[Dict[str, Any]]  # Raw word data with bbox
    meta: Dict[str, Any]  # Metadata (source, engine, has_tables, etc.)


class PdfExtractor:
    """Extract text and layout from PDF files using pdfplumber."""

    def load(self, pdf_path: str) -> ExtractedDocument:
        """
        Extract text with layout information from PDF.

        Args:
            pdf_path: Path to PDF (absolute or relative)

        Returns:
            ExtractedDocument with layout_text and words

        Raises:
            FileNotFoundError: If PDF doesn't exist
            ValueError: If PDF is empty
        """
        resolved_path = resolve_pdf_path(pdf_path)

        if not resolved_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        with pdfplumber.open(str(resolved_path)) as pdf:
            if len(pdf.pages) == 0:
                raise ValueError("Empty PDF: no pages found")

            page = pdf.pages[0]
            page_width = float(page.width)
            page_height = float(page.height)

            # Extract words with bounding boxes
            words_raw = page.extract_words()
            if not words_raw:
                raise ValueError("Empty PDF: no text content")

            # Enrich words with zone information
            words = []
            for word in words_raw:
                bbox = [
                    float(word["x0"]),
                    float(word["top"]),
                    float(word["x1"]),
                    float(word["bottom"]),
                ]
                zone = self._calculate_zone(bbox, page_width, page_height)

                words.append(
                    {
                        "text": word["text"],
                        "bbox": bbox,
                        "zone": zone,
                    }
                )

            # Detect tables
            tables = page.find_tables()
            has_tables = len(tables) > 0

            # Group words into lines
            lines = self._group_words_to_lines(words)

            # Format layout text for LLM
            layout_text = self._format_layout_text(lines)

            meta = {
                "source": str(resolved_path.resolve()),
                "engine": "pdfplumber",
                "pages": 1,
                "page_width": page_width,
                "page_height": page_height,
                "has_tables": has_tables,
                "word_count": len(words),
                "line_count": len(lines),
            }

            return ExtractedDocument(
                layout_text=layout_text,
                words=words,
                meta=meta,
            )

    def _calculate_zone(
        self, bbox: List[float], page_width: float, page_height: float
    ) -> str:
        """
        Calculate zone position on page (9-grid system).

        Args:
            bbox: Bounding box [x0, y0, x1, y1]
            page_width: Page width
            page_height: Page height

        Returns:
            Zone name (e.g., "TOP-LEFT", "CENTER", etc.)
        """
        x_center = (bbox[0] + bbox[2]) / 2
        y_center = (bbox[1] + bbox[3]) / 2

        # Divide page into 3x3 grid
        x_third = page_width / 3
        y_third = page_height / 3

        # Determine horizontal position
        if x_center < x_third:
            h_pos = "LEFT"
        elif x_center < 2 * x_third:
            h_pos = "CENTER"
        else:
            h_pos = "RIGHT"

        # Determine vertical position
        if y_center < y_third:
            v_pos = "TOP"
        elif y_center < 2 * y_third:
            v_pos = "MIDDLE"
        else:
            v_pos = "BOTTOM"

        # Combine positions (skip "MIDDLE" prefix for center row)
        if v_pos == "MIDDLE":
            return h_pos
        else:
            return f"{v_pos}-{h_pos}"

    def _group_words_to_lines(self, words: List[Dict]) -> List[Dict]:
        """
        Group words into lines by Y-coordinate proximity.

        Args:
            words: List of word dictionaries with bbox

        Returns:
            List of line dictionaries with aggregated bbox and text
        """
        if not words:
            return []

        # Sort words by Y position (top to bottom), then X (left to right)
        sorted_words = sorted(words, key=lambda w: (w["bbox"][1], w["bbox"][0]))

        lines = []
        current_line = []
        current_y = sorted_words[0]["bbox"][1]
        y_threshold = 5  # Points tolerance for same line

        for word in sorted_words:
            word_y = word["bbox"][1]

            # Check if word belongs to current line
            if abs(word_y - current_y) <= y_threshold:
                current_line.append(word)
            else:
                # Save current line and start new one
                if current_line:
                    lines.append(self._create_line_dict(current_line))
                current_line = [word]
                current_y = word_y

        # Don't forget last line
        if current_line:
            lines.append(self._create_line_dict(current_line))

        return lines

    def _create_line_dict(self, words: List[Dict]) -> Dict:
        """
        Create line dictionary from words.

        Args:
            words: List of words in the line

        Returns:
            Line dictionary with text, bbox, and zone
        """
        # Sort words left to right
        words_sorted = sorted(words, key=lambda w: w["bbox"][0])

        # Combine text
        text = " ".join(w["text"] for w in words_sorted)

        # Calculate bounding box
        x0 = min(w["bbox"][0] for w in words_sorted)
        y0 = min(w["bbox"][1] for w in words_sorted)
        x1 = max(w["bbox"][2] for w in words_sorted)
        y1 = max(w["bbox"][3] for w in words_sorted)

        # Use zone from first word (most representative)
        zone = words_sorted[0]["zone"]

        return {
            "text": text,
            "bbox": [x0, y0, x1, y1],
            "zone": zone,
            "word_count": len(words_sorted),
        }

    def _format_layout_text(self, lines: List[Dict]) -> str:
        """
        Format lines as layout text for LLM.

        Args:
            lines: List of line dictionaries

        Returns:
            Formatted text with coordinates
        """
        formatted_lines = []

        for line in lines:
            zone = line["zone"]
            bbox = line["bbox"]
            text = line["text"]

            # Format: [ZONE] [x:X0-X1, y:Y0] text
            x0, y0, x1, _ = bbox
            formatted = f"[{zone}] [x:{int(x0)}-{int(x1)}, y:{int(y0)}] {text}"
            formatted_lines.append(formatted)

        return "\n".join(formatted_lines)


def resolve_pdf_path(pdf_path_str: str) -> Path:
    """
    Resolve PDF path using PDF_BASE_PATH if needed.

    Args:
        pdf_path_str: Path string (absolute or relative)

    Returns:
        Resolved Path object
    """
    candidate = Path(pdf_path_str)

    if candidate.is_absolute():
        return candidate

    # Try current directory first
    resolved = (Path.cwd() / candidate).resolve()
    if resolved.exists():
        return resolved

    # Try base path if configured
    if settings.pdf_base_path:
        base_dir = Path(settings.pdf_base_path).expanduser()
        return (base_dir / candidate).resolve()

    return resolved


def load_pdf_bytes(pdf_path: Path) -> bytes:
    """Load PDF file as bytes."""
    return pdf_path.read_bytes()


def hash_pdf_bytes(pdf_bytes: bytes) -> str:
    """Generate SHA256 hash of PDF bytes."""
    return hashlib.sha256(pdf_bytes).hexdigest()


def hash_extraction_schema(schema: Dict[str, str]) -> str:
    """Generate hash of extraction schema."""
    encoded = json.dumps(schema, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def filter_layout_by_keywords(
    layout_text: str,
    extraction_schema: Dict[str, str],
    max_lines: int = 0,
) -> str:
    """
    Filter layout lines to only those containing keywords from extraction schema.

    Args:
        layout_text: Full layout text with all lines
        extraction_schema: Dict of field names to descriptions
        max_lines: Maximum lines to return (0 = unlimited)

    Returns:
        Filtered layout text with relevant lines only
    """
    if not extraction_schema or max_lines == 0:
        return layout_text

    # Extract keywords from schema
    keywords = set()
    stopwords = {
        "do",
        "da",
        "de",
        "o",
        "a",
        "para",
        "com",
        "em",
        "no",
        "na",
        "os",
        "as",
    }

    for field_name, description in extraction_schema.items():
        # From field name: "nome_completo" -> ["nome", "completo"]
        field_parts = field_name.lower().replace("_", " ").split()
        keywords.update(
            part for part in field_parts if part not in stopwords and len(part) > 2
        )

        # From description: "Nome completo do titular" -> ["nome", "completo", "titular"]
        desc_parts = description.lower().split()
        keywords.update(
            part for part in desc_parts if part not in stopwords and len(part) > 2
        )

    if not keywords:
        # No valid keywords - return original (or truncated by max_lines)
        if max_lines > 0:
            lines = layout_text.split("\n")[:max_lines]
            return "\n".join(lines)
        return layout_text

    # Filter lines containing keywords
    lines = layout_text.split("\n")
    relevant_lines = []

    for line in lines:
        line_lower = line.lower()
        # Check if any keyword appears in line
        if any(keyword in line_lower for keyword in keywords):
            relevant_lines.append(line)

    # If no matches found, return first max_lines (fallback)
    if not relevant_lines:
        if max_lines > 0:
            return "\n".join(lines[:max_lines])
        return layout_text

    # Limit to max_lines if specified
    if max_lines > 0 and len(relevant_lines) > max_lines:
        relevant_lines = relevant_lines[:max_lines]

    return "\n".join(relevant_lines)
