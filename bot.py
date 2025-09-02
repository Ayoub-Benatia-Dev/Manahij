# gemini_fallback.py
# دالة جاهزة تستعمل داخل بوتك: "تحاول" Gemini بالموديل الأساسي، وإذا فشل
# تنتقل تلقائياً لموديلات بديلة عبر REST API (مثل gemini-2.0-flash).
# تقدر تدمج هذي الدالة في bot.py وتستبدل مكالمات Gemini السابقة بها.
#
# المتطلبات:
# - متغير البيئة GEMINI_API_KEY معرف بمفتاحك
# - المكتبات: requests, google.generativeai (اختياري)
#
# استدعاء نموذجي:
# text = gemini_fallback_generate(instructions, user_prompt)
# لو text == None فمعناه كل المحاولات فشلت.

import os
import time
import logging
import requests
from typing import List, Optional

# لو مثبت مكتبة genai نستخدمها أولاً (أسرع لو شغالة)
try:
    import google.generativeai as genai  # النوع الرسمي لو متوفر
except Exception:
    genai = None

logger = logging.getLogger("gemini_fallback")
logger.setLevel(logging.INFO)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# قائمة الموديلات البديلة (ترتيب التجربة: الأول يُجرَّب أولاً)
DEFAULT_MODELS = [
    os.getenv("GEMINI_MODEL", "models/gemini-1.5"),   # موديل افتراضي من عندك
    "models/gemini-2.0-flash",
    "models/gemini-2.0",
    "models/gemini-1.5-flash",
]

def _extract_text_from_gl_response(j: dict) -> Optional[str]:
    """
    نحاول نفك شيفرة الـ JSON اللي يرجعها generativelanguage API
    ونستخرج نص معقول. نرجع None إذا ما لقيناش حاجة.
    """
    if not isinstance(j, dict):
        return None

    # حالة شائعة: "candidates" تحتوي على أجزاء نصية
    if "candidates" in j and isinstance(j["candidates"], list):
        parts = []
        for c in j["candidates"]:
            if isinstance(c, dict):
                # بعض الاستجابات تحوي content -> list of parts -> text
                if "content" in c and isinstance(c["content"], list):
                    for p in c["content"]:
                        if isinstance(p, dict) and "text" in p:
                            parts.append(p["text"])
                # أحيانًا الحقل اسمه output أو text مباشرة
                if "output" in c and isinstance(c["output"], str):
                    parts.append(c["output"])
                if "text" in c and isinstance(c["text"], str):
                    parts.append(c["text"])
        if parts:
            return "\n".join(parts)

    # بعض الأشكال: outputs -> list -> content -> list -> { "text": ... }
    if "outputs" in j and isinstance(j["outputs"], list):
        parts = []
        for out in j["outputs"]:
            if isinstance(out, dict) and "content" in out and isinstance(out["content"], list):
                for p in out["content"]:
                    if isinstance(p, dict) and "text" in p:
                        parts.append(p["text"])
        if parts:
            return "\n".join(parts)

    # فالكهس: نجمع أي نصوص بسيطة موجودة داخل الـ JSON (احتياطي)
    def _collect_strings(obj):
        res = []
        if isinstance(obj, str):
            res.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                res.extend(_collect_strings(v))
        elif isinstance(obj, list):
            for item in obj:
                res.extend(_collect_strings(item))
        return res

    strings = _collect_strings(j)
    if strings:
        # نرجع أول نصوص معقولة (لا نطالع كل JSON)
        joined = "\n".join(s for s in strings if len(s.strip()) > 10)
        return joined[:10000] if joined else None

    return None


def _call_gl_rest(model: str, prompt: str, max_tokens: int = 600, timeout: int = 20) -> Optional[str]:
    """
    نادِ API مباشرة (REST) على endpoint الخاص بـ Generative Language:
    https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    نستخدم X-goog-api-key لرأس الطلب.
    """
    if not GEMINI_API_KEY:
        logger.debug("GEMINI_API_KEY not set; skipping REST call.")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY,
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        # ممكن تضيف هنا إعدادات أخرى لو تحب، مثل "maxOutputTokens" بشرط أن الـ endpoint يدعمها
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        logger.warning("REST request to model %s failed: %s", model, e)
        return None

    if resp.status_code != 200:
        logger.warning("Model %s REST returned status %s: %s", model, resp.status_code, resp.text[:300])
        return None

    try:
        j = resp.json()
    except Exception as e:
        logger.warning("Failed to parse JSON from model %s response: %s", model, e)
        return None

    text = _extract_text_from_gl_response(j)
    if text:
        logger.info("Got text from REST model %s (len=%d)", model, len(text))
    return text


def gemini_fallback_generate(instructions: str, user_prompt: str, max_tokens: int = 600,
                             attempts_per_model: int = 2, models: Optional[List[str]] = None) -> Optional[str]:
    """
    دالة مركزية: تحاول تستخدم:
      1) أولًا مكتبة google.generativeai لو موجودة (genai.generate_text) مع MODEL_NAME
      2) لو فشلت أو غير متاحة، تجرب REST على قائمة الموديلات البديلة (DEFAULT_MODELS أو اللي تمرره)
    ترجع النص المستخرج أو None لو كلشي فشل.
    """
    full_prompt = (instructions + "\n\n" + user_prompt).strip() if instructions else user_prompt
    models_to_try = models or DEFAULT_MODELS

    # 1) محاولة باستخدام مكتبة genai (لو متاحة)
    if genai and GEMINI_API_KEY:
        for attempt in range(attempts_per_model):
            try:
                logger.debug("Trying genai.generate_text attempt %d on model %s", attempt + 1, models_to_try[0])
                resp = genai.generate_text(model=models_to_try[0], prompt=full_prompt, max_output_tokens=max_tokens)
                text = getattr(resp, "text", None) or str(resp)
                if text:
                    logger.info("genai.generate_text succeeded on model %s", models_to_try[0])
                    return text.strip()
            except Exception as e:
                logger.warning("Gemini call attempt %d failed: %s", attempt + 1, e)
                # لو الخطأ 404 أو 'Requested entity was not found' نخليها تجرب الموديلات البديلة مباشرة
                # نستمر بالمحاولات القليلة قبل الانتقال
                time.sleep(0.6 + attempt * 0.8)

    # 2) تجربة REST على كل موديل بديل
    for model in models_to_try:
        # نعمل retries بسيطة لكل موديل
        wait = 1.0
        for att in range(attempts_per_model):
            logger.debug("Trying REST model %s attempt %d", model, att + 1)
            text = _call_gl_rest(model, full_prompt, max_tokens=max_tokens)
            if text:
                return text.strip()
            time.sleep(wait)
            wait *= 2.0

    # كل المحاولات فشلت
    logger.warning("All Gemini models failed (tried: %s)", models_to_try)
    return None


# ===== مثال للاستخدام داخل البوت (توضيحي) =====
if __name__ == "__main__":
    # مثال بسيط: لو شغلت الملف لوحده
    instr = "كن صريحًا باللهجة السلفية، ركّز على استخراج كلمات مفتاحية للبحث."
    prompt = "ماهو حكم العب بفري فاير"
    out = gemini_fallback_generate(instr, prompt)
    print(">>>> RESULT:\n", out or "<no result>")
