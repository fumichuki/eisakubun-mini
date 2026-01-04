import os
from flask import Flask, request, jsonify, render_template
from openai import OpenAI

app = Flask(__name__)
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is not set on Render Environment Variables")
client = OpenAI()  # OPENAI_API_KEY を環境変数から読む

def load_prompt(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

QUESTION_PROMPT = load_prompt("prompts/question_prompt.txt")
GRADING_PROMPT  = load_prompt("prompts/grading_prompt.txt")

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/question")
def api_question():
    univ = request.args.get("univ", "汎用（大学受験）")
    prompt = QUESTION_PROMPT.replace("{{UNIV}}", univ)

    resp = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )
    return jsonify({"question": resp.output_text.strip()})

@app.post("/api/grade")
def api_grade():
    data = request.get_json(force=True)
    answer = (data.get("answer") or "").strip()
    question = (data.get("question") or "").strip()
    univ = (data.get("univ") or "汎用（大学受験）").strip()

    prompt = (GRADING_PROMPT
              .replace("{{UNIV}}", univ)
              .replace("{{QUESTION}}", question)
              .replace("{{ANSWER}}", answer))

    resp = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )
    return jsonify({"result": resp.output_text.strip()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
