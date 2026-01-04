const qEl = document.getElementById("question");
const aEl = document.getElementById("answer");
const rEl = document.getElementById("result");
const uEl = document.getElementById("univ");
const wcEl = document.getElementById("wc");

function wordCount(s){
  return (s.trim().match(/\\b[\\w']+\\b/g) || []).length;
}

aEl.addEventListener("input", () => {
  wcEl.textContent = `現在 ${wordCount(aEl.value)}語`;
});

document.getElementById("btnQ").addEventListener("click", async () => {
  rEl.textContent = "";
  aEl.value = "";
  wcEl.textContent = "";
  const univ = encodeURIComponent(uEl.value);
  const res = await fetch(`/api/question?univ=${univ}`);
  const data = await res.json();
  qEl.textContent = data.question;
});

document.getElementById("btnG").addEventListener("click", async () => {
  const payload = {
    univ: uEl.value,
    question: qEl.textContent,
    answer: aEl.value
  };
  const res = await fetch("/api/grade", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  rEl.textContent = data.result;
});
