console.log("[DEBUG] static.script: loaded v4.0 (Fail-Safe Mode)");

async function runAnalysis() {
  console.log("[DEBUG] runAnalysis: start");
  
  // DOM Elements
  const promptEl = document.getElementById("prompt");
  const statusEl = document.getElementById("status");
  const finalEl = document.getElementById("final-response");
  const stepsEl = document.getElementById("steps-container");

  // Input Validation
  const prompt = promptEl.value.trim();
  if (!prompt) {
    statusEl.textContent = "Please paste your resume text (with GitHub URL).";
    return;
  }

  // Reset UI
  statusEl.textContent = "Running multi-agent analysis...";
  finalEl.innerText = ""; 
  stepsEl.innerHTML = "";

  try {
    // API Call
    const resp = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });

    const data = await resp.json();
    console.log("[DEBUG] response data:", data);

    if (data.status === "error") {
      statusEl.textContent = data.error || "Unexpected error from API.";
      return;
    }

    statusEl.textContent = "Analysis complete.";

    // --- המנגנון החדש (Fail-Safe Logic) ---
    // 1. ניסיון ראשון: קריאה ישירה מהשרת
    let finalText = data.response;

    // 2. ניסיון שני: אם הראשי ריק, חפש את השלב האחרון
    if (!finalText || finalText.trim().length === 0) {
        console.warn("[DEBUG] Main response empty, checking steps...");
        
        if (Array.isArray(data.steps) && data.steps.length > 0) {
            // רץ על השלבים מהסוף להתחלה כדי למצוא את הסיכום
            for (let i = data.steps.length - 1; i >= 0; i--) {
                const step = data.steps[i];
                if (step.module === "Final Analysis" && step.response && step.response.length > 10) {
                    console.log("[DEBUG] Recovered text from Final Analysis step");
                    finalText = step.response;
                    break;
                }
            }
        }
    }

    // 3. הצגת הטקסט הסופי
    if (finalText) {
        finalEl.innerText = finalText;
    } else {
        finalEl.innerText = "Error: Analysis finished but no text could be extracted.";
    }
    // ---------------------------------------

    // Render Steps
    if (Array.isArray(data.steps)) {
      renderSteps(data.steps, stepsEl);
    }

  } catch (err) {
    console.error("[DEBUG] Error:", err);
    statusEl.textContent = "Failed to communicate with server.";
  }
}

function renderSteps(steps, container) {
    steps.forEach((step, idx) => {
      const item = document.createElement("div");
      item.className = "step-item";

      const header = document.createElement("div");
      header.className = "step-header";
      header.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
          <span class="chevron">▶</span> 
          <strong>${idx + 1}. ${step.module}</strong>
        </div>
        <span class="badge" style="font-size: 0.8em; opacity: 0.7;">View Log</span>
      `;

      const body = document.createElement("div");
      body.className = "step-body";
      body.style.display = "none";
      body.style.padding = "10px";
      body.style.background = "#f4f4f4";
      body.style.marginTop = "5px";
      body.innerHTML = `
        <div style="margin-bottom: 5px;"><strong>Input:</strong></div>
        <pre style="white-space: pre-wrap; background: #e0e0e0; padding: 5px; margin-bottom: 10px;">${step.prompt}</pre>
        <div style="margin-bottom: 5px;"><strong>Output:</strong></div>
        <pre style="white-space: pre-wrap; background: #fff; border: 1px solid #ccc; padding: 5px;">${step.response}</pre>
      `;

      header.addEventListener("click", () => {
        const isOpen = body.style.display !== "none";
        body.style.display = isOpen ? "none" : "block";
        header.querySelector(".chevron").innerText = isOpen ? "▶" : "▼";
      });

      item.appendChild(header);
      item.appendChild(body);
      container.appendChild(item);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("run-btn");
  if (btn) btn.addEventListener("click", runAnalysis);
});