const chat = document.getElementById("chat-container");
const input = document.getElementById("user-input");
const btn = document.getElementById("send-btn");

function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = `message ${cls}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function fetchQuestion() {
  const univ = document.getElementById("univ").value;
  const res = await fetch(`/api/question?univ=${encodeURIComponent(univ)}`);
  const data = await res.json();
  addMessage(data.question, "ai");
}

btn.onclick = () => {
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  if (text === "！") {
    fetchQuestion();
  }
};

input.addEventListener("keydown", e => {
  if (e.key === "Enter") btn.onclick();
});

// 初回自動表示
fetchQuestion();