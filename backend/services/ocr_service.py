"""
OCR Service — extracts text from student handwriting images.

Modes (set in DB settings):
  local      — Tesseract only (fastest, offline)
  vision_api — Send image to LLM vision model (most accurate for messy handwriting)
  hybrid     — Try local first; if confidence is low, fall back to vision API
"""

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def image_to_base64(image_path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for an image file."""
    path = Path(image_path)
    suffix = path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    media_type = media_map.get(suffix, "image/png")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, media_type


def preprocess_image(image_path: str) -> str:
    """
    Apply basic preprocessing to improve OCR accuracy:
    - Convert to grayscale
    - Increase contrast
    - Binarize (threshold)
    Returns path to the preprocessed image.
    """
    try:
        from PIL import Image, ImageFilter, ImageEnhance
        import numpy as np

        img = Image.open(image_path).convert("L")  # grayscale
        # Enhance contrast
        img = ImageEnhance.Contrast(img).enhance(2.0)
        # Simple threshold binarization
        arr = np.array(img)
        arr = (arr > 128).astype("uint8") * 255
        img = Image.fromarray(arr)

        out_path = image_path.replace(".", "_processed.")
        img.save(out_path)
        return out_path
    except Exception as e:
        logger.warning(f"Image preprocessing failed: {e}, using original")
        return image_path


def ocr_local(image_path: str) -> tuple[str, float]:
    """
    Run Tesseract on the image.
    Returns (text, confidence) where confidence is 0–100.
    """
    try:
        import pytesseract
        from PIL import Image

        processed = preprocess_image(image_path)
        img = Image.open(processed)

        # Get text + confidence data
        data = pytesseract.image_to_data(
            img,
            config="--psm 6 -l eng+equ",  # psm 6 = assume uniform block of text
            output_type=pytesseract.Output.DICT,
        )
        texts = [
            t for t, c in zip(data["text"], data["conf"])
            if isinstance(c, (int, float)) and c > 0 and t.strip()
        ]
        confs = [
            float(c) for c in data["conf"]
            if isinstance(c, (int, float)) and c > 0
        ]
        text = " ".join(texts)
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return text, avg_conf
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        return "", 0.0


def ocr_vision_api(image_path: str, db) -> str:
    """
    Send image to the configured LLM's vision endpoint.
    Returns extracted text.
    """
    import litellm
    from backend.services.llm_service import _get_llm_settings, _build_model_string

    cfg = _get_llm_settings(db)
    provider = cfg.get("llm_provider", "openai")
    api_key = cfg.get("llm_api_key", "")
    model = cfg.get("llm_model_name", "gpt-4o")
    base_url = cfg.get("llm_base_url") or None

    if not api_key:
        raise ValueError("No API key configured for vision OCR")

    b64_data, media_type = image_to_base64(image_path)
    model_str = _build_model_string(provider, model)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "This is a student's handwritten math solution. "
                        "Please extract ALL the text and mathematical expressions exactly as written. "
                        "Include numbers, symbols, working steps, and the final answer. "
                        "Preserve structure — use newlines for separate steps. "
                        "Do not interpret or evaluate; just transcribe faithfully."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{b64_data}"},
                },
            ],
        }
    ]

    kwargs = {
        "model": model_str,
        "messages": messages,
        "api_key": api_key,
        "max_tokens": 1500,
    }
    if base_url:
        kwargs["base_url"] = base_url

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content


def extract_text_from_image(image_path: str, db=None, mode: str = "hybrid") -> str:
    """
    Main OCR entry point.
    mode: 'local' | 'vision_api' | 'hybrid'
    db: SQLAlchemy session (required for vision_api and hybrid modes)
    """
    if mode == "local":
        text, _ = ocr_local(image_path)
        return text

    if mode == "vision_api":
        if db is None:
            raise ValueError("DB session required for vision_api mode")
        return ocr_vision_api(image_path, db)

    # hybrid: local first, fall back to vision if confidence < 60
    text, confidence = ocr_local(image_path)
    logger.info(f"Local OCR confidence: {confidence:.1f}%")

    if confidence >= 60 or db is None:
        return text

    logger.info("Low confidence — falling back to vision API")
    try:
        return ocr_vision_api(image_path, db)
    except Exception as e:
        logger.warning(f"Vision API fallback failed: {e}, using local result")
        return text


def get_ocr_mode(db) -> str:
    """Read OCR mode from DB settings."""
    from backend.models.settings import AppSetting
    setting = db.query(AppSetting).filter(AppSetting.key == "ocr_mode").first()
    return setting.value if setting else "hybrid"
