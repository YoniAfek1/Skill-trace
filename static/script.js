console.log("[DEBUG] static.script: loaded v5.0 (Dark Mode Fixed)");

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

    // --- Fail-Safe Logic for Final Response ---
    let finalText = data.response;

    if (!finalText || finalText.trim().length === 0) {
        console.warn("[DEBUG] Main response empty, checking steps...");
        if (Array.isArray(data.steps) && data.steps.length > 0) {
            for (let i = data.steps.length - 1; i >= 0; i--) {
                const step = data.steps[i];
                if (step.module === "Final Analysis" && step.response && step.response.length > 10) {
                    finalText = step.response;
                    break;
                }
            }
        }
    }

    if (finalText) {
        finalEl.innerText = finalText;
    } else {
        finalEl.innerText = "Error: Analysis finished but no text could be extracted.";
    }

    // --- Render Steps (Dark Mode) ---
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
      // ensure item has dark background via style or css class
      item.style.border = "1px solid #374151";
      item.style.marginBottom = "10px";
      item.style.borderRadius = "8px";
      item.style.overflow = "hidden";

      const header = document.createElement("div");
      header.className = "step-header";
      // Header styling
      header.style.background = "#1f2937";
      header.style.padding = "10px";
      header.style.cursor = "pointer";
      header.style.display = "flex";
      header.style.justifyContent = "space-between";
      header.style.alignItems = "center";
      
      header.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px; color: #e5e7eb;">
          <span class="chevron">▶</span> 
          <strong>${idx + 1}. ${step.module}</strong>
        </div>
        <span class="badge" style="font-size: 0.8em; background: #2563eb; color: white; padding: 2px 8px; border-radius: 12px;">View Log</span>
      `;

      const body = document.createElement("div");
      body.className = "step-body";
      body.style.display = "none";
      // Body styling - DARK MODE COLORS
      body.style.padding = "15px";
      body.style.background = "#111827"; // Dark background
      body.style.borderTop = "1px solid #374151";
      
      // Using pre-wrap and specific colors for the code blocks
      body.innerHTML = `
        <div style="margin-bottom: 5px; color: #9ca3af; font-size: 0.9em;"><strong>Input:</strong></div>
        <pre style="white-space: pre-wrap; background: #1f2937; color: #d1d5db; padding: 10px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #374151;">${step.prompt}</pre>
        
        <div style="margin-bottom: 5px; color: #9ca3af; font-size: 0.9em;"><strong>Output:</strong></div>
        <pre style="white-space: pre-wrap; background: #020617; color: #e5e7eb; padding: 10px; border-radius: 6px; border: 1px solid #374151;">${step.response}</pre>
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