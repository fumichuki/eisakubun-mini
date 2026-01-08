const chat = document.getElementById("chat-container");
const input = document.getElementById("user-input");
const btn = document.getElementById("send-btn");

let currentQuestion = ""; // 現在の問題を保持

function addMessage(text, cls, status = null) {
  const div = document.createElement("div");
  div.className = `message ${cls}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = cls === "ai" ? "🤖" : "🧑";

  const content = document.createElement("div");
  content.className = "content";

  const meta = document.createElement("div");
  meta.className = "meta";
  const role = document.createElement("div");
  role.className = "role";
  role.textContent = cls === "ai" ? "Assistant" : "You";
  const time = document.createElement("div");
  time.className = "time";
  time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  meta.appendChild(role);
  meta.appendChild(time);

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (cls === "ai") {
    if (status) {
      bubble.textContent = status;
      bubble.classList.add("status");
    } else {
      bubble.classList.add("typing");
    }
    content.appendChild(meta);
    content.appendChild(bubble);
    div.appendChild(avatar);
    div.appendChild(content);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;

    if (!status) {
      setTimeout(() => {
        bubble.classList.remove("typing");
        bubble.textContent = text ?? "";
        chat.scrollTop = chat.scrollHeight;
      }, 450);
    }
  } else {
    bubble.textContent = text;
    content.appendChild(meta);
    content.appendChild(bubble);
    div.appendChild(avatar);
    div.appendChild(content);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  return bubble;
}

async function fetchQuestion() {
  const univ = document.getElementById("univ").value;

  const statusBubble = addMessage("", "ai", "【問題生成中】");

  try {
    const res = await fetch(`/api/question?univ=${encodeURIComponent(univ)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    // ✅ ここが本丸：result / question どっちでも拾う
    const q = data.question ?? data.result ?? data.text ?? data.message ?? "";

    currentQuestion = q;

    statusBubble.classList.remove("status");
    statusBubble.classList.add("typing");
    setTimeout(() => {
      statusBubble.classList.remove("typing");
      statusBubble.textContent = q || "（問題の取得に失敗しました）";
      chat.scrollTop = chat.scrollHeight;
    }, 450);
  } catch (error) {
    statusBubble.textContent = "エラーが発生しました。";
    console.error(error);
  }
}

async function fetchGrade(answer) {
  const statusBubble = addMessage("", "ai", "【採点中】");

  try {
    const res = await fetch("/api/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        // ✅ app.py が要求しているキー名に合わせる
        problem: currentQuestion,
        answer: answer,
        // 40〜60語にしたいなら明示（不要なら消してOK）
        min_words: 40,
        max_words: 60,
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();
    const out = data.result ?? data.question ?? "";

    statusBubble.classList.remove("status");
    statusBubble.classList.add("typing");
    setTimeout(() => {
      statusBubble.classList.remove("typing");
      statusBubble.textContent = out || "（採点結果の取得に失敗しました）";
      chat.scrollTop = chat.scrollHeight;
    }, 450);
  } catch (error) {
    statusBubble.textContent = "エラーが発生しました。";
    console.error(error);
  }
}

btn.onclick = () => {
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  if (text === "！") {
    fetchQuestion();
  } else {
    fetchGrade(text);
  }
};

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") btn.onclick();
});

// 初回自動表示
fetchQuestion();
