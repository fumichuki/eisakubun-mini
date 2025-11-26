from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello from Render + Codespaces!"

@app.route("/api/question")
def get_question():
    """
    最小バージョン：
    固定の英作文問題を JSON で返すだけのAPI
    """
    question = {
        "theme": "環境問題",
        "title": "プラスチックごみと私たちの生活",
        "instruction": "次の内容を40〜60語の英文で書きなさい。",
        "japanese": [
            "現代社会ではプラスチックごみが増え続け、海や川の生き物に大きな影響を与えています。",
            "私たち一人ひとりが、使い捨てプラスチックを減らすためにできることについて述べなさい。"
        ],
        "word_limit_min": 40,
        "word_limit_max": 60,
        "hints": [
            {"en": "plastic waste", "ja": "プラスチックごみ"},
            {"en": "environment", "ja": "環境"},
            {"en": "reduce", "ja": "減らす"},
            {"en": "reusable bag", "ja": "再利用できるバッグ"},
            {"en": "responsibility", "ja": "責任"}
        ]
    }
    return jsonify(question)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)