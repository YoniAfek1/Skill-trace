console.log("[DEBUG] static.script: loaded");

async function runAnalysis() {
  console.log("[DEBUG] runAnalysis: start");
  const promptEl = document.getElementById("prompt");
  const statusEl = document.getElementById("status");
  const finalEl = document.getElementById("final-response");
  const stepsEl = document.getElementById("steps-container");

  const prompt = promptEl.value.trim();
  if (!prompt) {
    statusEl.textContent = "Please paste your resume text (with GitHub URL).";
    console.log("[DEBUG] runAnalysis: empty prompt");
    return;
  }

  statusEl.textContent = "Running multi-agent analysis...";
  finalEl.textContent = "";
  stepsEl.innerHTML = "";

  try {
    const resp = await fetch("/api/execute", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt }),
    });

    const data = await resp.json();
    console.log("[DEBUG] runAnalysis: response received", data);

    if (data.status !== "ok") {
      statusEl.textContent = data.error || "Unexpected error from API.";
      return;
    }

    statusEl.textContent = "Analysis complete.";
    finalEl.textContent = data.final_analysis || "";

    if (Array.isArray(data.steps)) {
      data.steps.forEach((step, idx) => {
        const item = document.createElement("div");
        item.className = "step-item";

        const header = document.createElement("div");
        header.className = "step-header";
        header.innerHTML = `
          <span>${idx + 1}. ${step.module}</span>
          <span class="badge">step</span>
          <span class="chevron">▼</span>
        `;

        const body = document.createElement("div");
        body.className = "step-body";
        body.innerHTML = `
          <pre><strong>Prompt</strong>\n${step.prompt}</pre>
          <pre><strong>Response</strong>\n${step.response}</pre>
        `;

        header.addEventListener("click", () => {
          body.classList.toggle("open");
        });

        item.appendChild(header);
        item.appendChild(body);
        stepsEl.appendChild(item);
      });
    }
  } catch (err) {
    console.error("[DEBUG] runAnalysis: error", err);
    statusEl.textContent = "Failed to reach backend. Check console and server logs.";
  }

  console.log("[DEBUG] runAnalysis: end");
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("[DEBUG] DOMContentLoaded");
  const btn = document.getElementById("run-btn");
  btn.addEventListener("click", runAnalysis);
});

