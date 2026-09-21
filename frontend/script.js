const queryInput = document.getElementById("queryInput");
const submitBtn = document.getElementById("submitBtn");
const loading = document.getElementById("loading");
const resultCard = document.getElementById("resultCard");
const errorMsg = document.getElementById("errorMsg");

const resultQuery = document.getElementById("resultQuery");
const confidenceBar = document.getElementById("confidenceBar");
const confidenceValue = document.getElementById("confidenceValue");
const resultValue = document.getElementById("resultValue");
const resultSql = document.getElementById("resultSql");
const resultExplanation = document.getElementById("resultExplanation");

document.querySelectorAll(".example-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    queryInput.value = chip.dataset.query;
    runQuery();
  });
});

submitBtn.addEventListener("click", runQuery);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runQuery();
});

async function runQuery() {
  const question = queryInput.value.trim();
  if (!question) return;

  resultCard.classList.add("hidden");
  errorMsg.classList.add("hidden");
  loading.classList.remove("hidden");

  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: question }),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    renderResult(data);
  } catch (err) {
    errorMsg.textContent = `Something went wrong: ${err.message}`;
    errorMsg.classList.remove("hidden");
  } finally {
    loading.classList.add("hidden");
  }
}

function renderResult(data) {
  resultQuery.textContent = data.query;

  const confidence = data.confidence_score ?? 0;
  confidenceBar.style.width = `${confidence * 100}%`;
  confidenceValue.textContent = confidence.toFixed(2);

  let color = "#e0555a"; // bad
  if (confidence >= 0.7) color = "#4caf7d"; // good
  else if (confidence >= 0.4) color = "#e8a33d"; // warn
  confidenceBar.style.background = color;
  confidenceValue.style.color = color;

  resultValue.textContent =
    typeof data.result === "object"
      ? JSON.stringify(data.result, null, 2)
      : String(data.result);

  resultSql.textContent = data.generated_logic || "N/A";
  resultExplanation.textContent = data.explanation || "N/A";

  resultCard.classList.remove("hidden");
}
