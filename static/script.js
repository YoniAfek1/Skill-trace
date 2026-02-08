console.log("[DEBUG] static.script: loaded");

async function runAnalysis() {
  console.log("[DEBUG] runAnalysis: start");
  const promptEl = document.getElementById("prompt");
  const statusEl = document.getElementById("status");
  const finalEl = document.getElementById("final-response"); // ודא שב-HTML יש אלמנט עם ID כזה
  const stepsEl = document.getElementById("steps-container");

  const prompt = promptEl.value.trim();
  if (!prompt) {
    statusEl.textContent = "Please paste your resume text (with GitHub URL).";
    console.log("[DEBUG] runAnalysis: empty prompt");
    return;
  }

  // איפוס התצוגה לפני הריצה
  statusEl.textContent = "Running multi-agent analysis...";
  finalEl.innerText = ""; // שימוש ב-innerText שומר על שורות ריקות
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

    // תיקון בדיקת הסטטוס: בודקים אם יש שגיאה במפורש
    if (data.status === "error") {
      statusEl.textContent = data.error || "Unexpected error from API.";
      return;
    }

    statusEl.textContent = "Analysis complete.";

    // --- התיקון המרכזי כאן ---
    // השרת מחזיר את הטקסט בתוך 'response', לא 'final_analysis'
    if (data.response) {
        finalEl.innerText = data.response; 
    } else {
        finalEl.innerText = "No final response text returned from server.";
    }
    // ------------------------

    if (Array.isArray(data.steps)) {
      data.steps.forEach((step, idx) => {
        const item = document.createElement("div");
        item.className = "step-item";

        // יצירת הכותרת של השלב
        const header = document.createElement("div");
        header.className = "step-header";
        
        // הוספת חץ קטן וסמל
        header.innerHTML = `
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="chevron">▶</span> 
            <strong>${idx + 1}. ${step.module}</strong>
          </div>
          <span class="badge" style="font-size: 0.8em; opacity: 0.7;">View Log</span>
        `;

        const body = document.createElement("div");
        body.className = "step-body";
        // הסתרת הגוף כברירת מחדל
        body.style.display = "none";
        body.style.padding = "10px";
        body.style.background = "#f4f4f4";
        body.style.marginTop = "5px";
        
        body.innerHTML = `
          <div style="margin-bottom: 5px;"><strong>Input Prompt:</strong></div>
          <pre style="white-space: pre-wrap; background: #e0e0e0; padding: 5px; margin-bottom: 10px;">${step.prompt}</pre>
          <div style="margin-bottom: 5px;"><strong>AI Response:</strong></div>
          <pre style="white-space: pre-wrap; background: #fff; border: 1px solid #ccc; padding: 5px;">${step.response}</pre>
        `;

        // לוגיקה לפתיחה/סגירה של השלב
        header.style.cursor = "pointer";
        header.addEventListener("click", () => {
          const isOpen = body.style.display !== "none";
          body.style.display = isOpen ? "none" : "block";
          const chevron = header.querySelector(".chevron");
          if (chevron) chevron.innerText = isOpen ? "▶" : "▼";
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
  if (btn) {
      btn.addEventListener("click", runAnalysis);
  }
});