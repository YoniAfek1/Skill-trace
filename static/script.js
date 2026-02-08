console.log("[DEBUG] loaded: script.js v3.0 (Diagnostic Mode)");

async function runAnalysis() {
  const statusEl = document.getElementById("status");
  const finalEl = document.getElementById("final-response");
  const stepsEl = document.getElementById("steps-container");
  const promptEl = document.getElementById("prompt");

  // בדיקת תקינות בסיסית - האם האלמנט קיים?
  if (!finalEl) {
    alert("CRITICAL ERROR: Could not find element with id 'final-response' in HTML!");
    return;
  }

  const prompt = promptEl.value.trim();
  if (!prompt) {
    statusEl.textContent = "Please paste resume text.";
    return;
  }

  // איפוס וכתיבת הודעת בדיקה
  statusEl.textContent = "Running...";
  finalEl.style.color = "yellow"; // צבע בולט לבדיקה
  finalEl.innerText = "Waiting for server response..."; 
  stepsEl.innerHTML = "";

  try {
    const resp = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });

    const data = await resp.json();
    console.log("[DEBUG] Raw Data:", data);

    // 1. האם השרת החזיר שגיאה?
    if (data.status === "error") {
      statusEl.textContent = "Error from server.";
      finalEl.innerText = "SERVER ERROR:\n" + data.error;
      return;
    }

    statusEl.textContent = "Analysis complete.";

    // 2. ניסיון אגרסיבי לחלץ את הטקסט
    let finalText = data.response;
    let source = "Direct Response";

    // אם ריק, נחפש בשלבים (Fail-Safe)
    if (!finalText || finalText.trim().length === 0) {
        if (data.steps && data.steps.length > 0) {
            const lastStep = data.steps[data.steps.length - 1];
            finalText = lastStep.response;
            source = "Recovered from Step " + data.steps.length;
        }
    }

    // 3. הצגה במסך (או הודעת שגיאה אם עדיין ריק)
    finalEl.style.color = "#e4e9f5"; // החזרת צבע רגיל
    
    if (finalText) {
        finalEl.innerText = finalText;
        console.log(`[SUCCESS] Text rendered from: ${source}`);
    } else {
        finalEl.style.color = "red";
        finalEl.innerText = "DEBUG FAILURE: Server returned success, but text is empty!\n" + 
                            "Check 'Agent Steps' below to see if the AI generated output.";
    }

    // הצגת השלבים
    if (data.steps) {
      renderSteps(data.steps, stepsEl);
    }

  } catch (err) {
    console.error(err);
    statusEl.textContent = "Communication Error";
    finalEl.innerText = "JS ERROR:\n" + err.toString();
  }
}

function renderSteps(steps, container) {
  steps.forEach((step, idx) => {
    const item = document.createElement("div");
    item.className = "step-item";
    item.innerHTML = `
      <div class="step-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none'">
        <strong>${idx + 1}. ${step.module}</strong> <span style="font-size:0.8em">▼</span>
      </div>
      <div class="step-body" style="display:none; padding:10px; background:#222; margin-top:5px;">
        <div><strong>Input:</strong></div><pre style="white-space:pre-wrap; color:#aaa">${step.prompt}</pre>
        <div style="margin-top:10px"><strong>Output:</strong></div><pre style="white-space:pre-wrap; color:#fff">${step.response}</pre>
      </div>
    `;
    container.appendChild(item);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("run-btn");
  if (btn) btn.addEventListener("click", runAnalysis);
});