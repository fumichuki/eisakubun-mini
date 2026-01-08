import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request

# .env を自動読み込み（Codespaces / ローカル両対応）
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from openai import OpenAI

# ------------------------
# Config
# ------------------------
BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR") or (BASE_DIR / "prompts"))

QUESTION_PROMPT_FILE = os.getenv("QUESTION_PROMPT_FILE") or str(PROMPTS_DIR / "question_prompt.txt")
GRADING_STEP1_PROMPT_FILE = os.getenv("GRADING_STEP1_PROMPT_FILE") or str(PROMPTS_DIR / "grading_step1_prompt.txt")
GRADING_STEP2_PROMPT_FILE = os.getenv("GRADING_STEP2_PROMPT_FILE") or str(PROMPTS_DIR / "grading_step2_prompt.txt")

MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
TEMPERATURE = float(os.getenv("TEMPERATURE") or "0")  # まずブレを消す
MAX_TOKENS = int(os.getenv("MAX_TOKENS") or "1800")

API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY) if API_KEY else None

app = Flask(__name__)

# ------------------------
# Helpers
# ------------------------
BANNED_SUBSTRINGS = [
    "Aは",
    "Bは",
    "X",
    "Y",
    "中核語",
    "一般的に",
    "より自然",
    "文脈に応じて",
    "型：",
    "※",
    "（ここで改行）",
]


def _read_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8")


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```$", "", s)
    return s.strip()


def _json_loads_strict(s: str) -> Any:
    s = _strip_code_fences(s)
    return json.loads(s)


def _word_count(text: str) -> int:
    tokens = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text)
    return len(tokens)


def _call_llm(system_prompt: str, user_payload: Any, *, temperature: float = TEMPERATURE) -> str:
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set")

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


# ------------------------
# Debug endpoints
# ------------------------

def prompt_info(path: str, full: bool = False) -> Dict[str, Any]:
    abs_path = str(Path(path).resolve())
    exists = Path(abs_path).exists()
    out: Dict[str, Any] = {
        "configured_path": path,
        "resolved_path": abs_path,
        "exists": exists,
    }
    if full and exists:
        out["content"] = _read_text(abs_path)
    return out


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "eisakubun-mini"})


@app.get("/debug/status")
def debug_status():
    return jsonify(
        {
            "service": "eisakubun-mini",
            "ok": True,
            "has_api_key": bool(API_KEY),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "prompt_files": {
                "question": QUESTION_PROMPT_FILE,
                "grading_step1": GRADING_STEP1_PROMPT_FILE,
                "grading_step2": GRADING_STEP2_PROMPT_FILE,
            },
        }
    )


@app.get("/debug/prompts")
def debug_prompts():
    full = request.args.get("full") in ("1", "true", "True")
    return jsonify(
        {
            "service": "eisakubun-mini",
            "has_api_key": bool(API_KEY),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "prompts": {
                "question_prompt": prompt_info(QUESTION_PROMPT_FILE, full=full),
                "grading_step1_prompt": prompt_info(GRADING_STEP1_PROMPT_FILE, full=full),
                "grading_step2_prompt": prompt_info(GRADING_STEP2_PROMPT_FILE, full=full),
            },
        }
    )


# ------------------------
# API: Question
# ------------------------

@app.post("/api/question")
def api_question():
    body = request.get_json(force=True, silent=True) or {}
    min_words = int(body.get("min_words") or 20)
    max_words = int(body.get("max_words") or 50)

    sys_prompt = _read_text(QUESTION_PROMPT_FILE)
    # {min_words} {max_words} を埋める
    sys_prompt = sys_prompt.replace("{min_words}", str(min_words)).replace("{max_words}", str(max_words))

    user_payload = {
        "univ": body.get("univ") or "汎用（大学受験）",
        "min_words": min_words,
        "max_words": max_words,
    }

    out = _call_llm(sys_prompt, user_payload, temperature=0)
    return jsonify({"question": out})


# ------------------------
# API: Grade (2-step, JSON->render)
# ------------------------


def _validate_points(points: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if len(points) != 5:
        errors.append(f"points must be length 5 (got {len(points)})")
    for i, p in enumerate(points):
        label = (p.get("label") or "").strip()
        explain = (p.get("explain_ja") or "").strip()
        if not label:
            errors.append(f"point[{i}].label is empty")
        if not explain:
            errors.append(f"point[{i}].explain_ja is empty")
        # 置換のとき from==to になってないか
        if "→" in label and "【補足】" not in label:
            a, b = [x.strip() for x in label.split("→", 1)]
            if a == b:
                errors.append(f"point[{i}] label has no change: {label}")
        # 禁止語
        joined = label + "\n" + explain + "\n" + json.dumps(p.get("examples", []), ensure_ascii=False)
        for bad in BANNED_SUBSTRINGS:
            if bad in joined:
                errors.append(f"point[{i}] contains banned substring: {bad}")
    return (len(errors) == 0, errors)


def _render_result(answer: str, revised: str, jp: str, points: List[Dict[str, Any]], scores: Dict[str, Any], *, min_words: int, max_words: int) -> str:
    ans_wc = _word_count(answer)
    rev_wc = _word_count(revised)

    lines: List[str] = []
    lines.append("【添削】")
    lines.append("あなたの英文：")
    lines.append(answer)
    lines.append("")
    lines.append(f"Word count: {ans_wc}")
    lines.append("")
    lines.append("修正版：")
    lines.append(revised)
    lines.append("")
    lines.append(f"Word count: {rev_wc}")
    lines.append("")
    lines.append("（修正版の日本語訳）：")
    lines.append(jp)
    lines.append("")

    lines.append("【文法・表現のポイント解説】")
    for idx, p in enumerate(points, start=1):
        label = (p.get("label") or "").strip()
        explain = (p.get("explain_ja") or "").strip()
        lines.append(f"{idx}) {label}")
        lines.append(f"解説：{explain}")
        exs = p.get("examples") or []
        if isinstance(exs, list) and exs:
            # 2文までを1行で
            ex_en = " ".join([e.get("en", "").strip() for e in exs if isinstance(e, dict) and e.get("en")][:2]).strip()
            ex_ja = " ".join([e.get("ja", "").strip() for e in exs if isinstance(e, dict) and e.get("ja")][:2]).strip()
            if ex_en and ex_ja:
                lines.append(f"例文：{ex_en}（{ex_ja}）")
        lines.append("")

    # scoring
    lines.append("【採点】")
    # 表はタブ区切りで
    lines.append("評価項目\t得点\tコメント")
    for k in ["内容", "構成", "語彙", "文法", "語数"]:
        item = (scores.get("items") or {}).get(k) if isinstance(scores.get("items"), dict) else None
        if isinstance(item, dict):
            score = item.get("score")
            comment = item.get("comment") or ""
        else:
            score = "-"
            comment = ""
        lines.append(f"{k}\t{score} / 5\t{comment}")

    total = scores.get("total")
    band = scores.get("band") or ""
    if total is not None:
        lines.append(f"合計：{total} / 25点（{band}）")
    else:
        lines.append("合計：- / 25点")

    return "\n".join(lines).strip()


@app.post("/api/grade")
def api_grade():
    body = request.get_json(force=True, silent=True) or {}
    answer = (body.get("answer") or "").strip()
    problem = (body.get("problem") or "").strip()
    min_words = int(body.get("min_words") or 20)
    max_words = int(body.get("max_words") or 50)

    if not answer:
        return jsonify({"error": "answer is required"}), 400
    if not problem:
        return jsonify({"error": "problem is required"}), 400

    step1_sys = _read_text(GRADING_STEP1_PROMPT_FILE)
    step2_sys = _read_text(GRADING_STEP2_PROMPT_FILE)

    step1_in = {
        "problem": problem,
        "min_words": min_words,
        "max_words": max_words,
        "answer": answer,
        "answer_wc": _word_count(answer),
    }

    step1_raw = _call_llm(step1_sys, step1_in, temperature=0)
    try:
        step1 = _json_loads_strict(step1_raw)
    except Exception as e:
        return jsonify({"error": f"step1 JSON parse failed: {e}", "raw": step1_raw}), 500

    revised = (step1.get("revised") or "").strip()
    edits = step1.get("edits") or []

    step2_in = {
        "problem": problem,
        "min_words": min_words,
        "max_words": max_words,
        "answer": answer,
        "answer_wc": _word_count(answer),
        "revised": revised,
        "revised_wc": _word_count(revised),
        "edits": edits,
    }

    # step2: JSON -> validate -> retry up to 2
    retries = 2
    last_raw = ""
    last_errs: List[str] = []
    for attempt in range(retries + 1):
        step2_raw = _call_llm(step2_sys, step2_in | {"attempt": attempt, "previous_errors": last_errs}, temperature=0)
        last_raw = step2_raw
        try:
            step2 = _json_loads_strict(step2_raw)
        except Exception as e:
            last_errs = [f"step2 JSON parse failed: {e}"]
            continue

        jp = (step2.get("jp_translation") or "").strip()
        points = step2.get("points") or []
        scores = step2.get("scores") or {}

        if not isinstance(points, list):
            last_errs = ["points is not a list"]
            continue

        ok, errs = _validate_points(points)
        if not ok:
            last_errs = errs
            continue

        rendered = _render_result(answer, revised, jp, points, scores, min_words=min_words, max_words=max_words)
        return jsonify({"result": rendered, "debug": {"step1": step1, "step2": step2}})

    return jsonify({"error": "step2 validation failed", "errors": last_errs, "raw": last_raw, "step1": step1}), 500


if __name__ == "__main__":
    # Codespaces では 0.0.0.0 が便利
    host = os.getenv("HOST") or "0.0.0.0"
    port = int(os.getenv("PORT") or "8000")
    app.run(host=host, port=port, debug=True)
