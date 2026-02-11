console.log("[DEBUG] static.script: loaded v6.0 (Streaming & Typewriter)");

function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function typeFinalResponse(text, container) {
    container.innerText = "";
    let i = 0;
    const interval = setInterval(() => {
        container.innerText += text.charAt(i);
        i++;
        container.scrollTop = container.scrollHeight;
        
        if (i >= text.length) {
            clearInterval(interval);
        }
    }, 15); 
}

function renderSingleStep(step, container, idx) {
    const item = document.createElement("div");
    item.className = "step-item";
    item.style.border = "1px solid #374151";
    item.style.marginBottom = "10px";
    item.style.borderRadius = "8px";
    item.style.overflow = "hidden";

    const header = document.createElement("div");
    header.className = "step-header";
    header.style.background = "#1f2937";
    header.style.padding = "10px";
    header.style.cursor = "pointer";
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    
    header.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px; color: #e5e7eb;">
        <span class="chevron">▶</span> 
        <strong>${idx}. ${escapeHtml(step.module)}</strong>
        </div>
        <span class="badge" style="font-size: 0.8em; background: #2563eb; color: white; padding: 2px 8px; border-radius: 12px;">View Log</span>
    `;

    const body = document.createElement("div");
    body.className = "step-body";
    body.style.display = "none";
    body.style.padding = "15px";
    body.style.background = "#111827";
    body.style.borderTop = "1px solid #374151";
    
    body.innerHTML = `
        <div style="margin-bottom: 5px; color: #9ca3af; font-size: 0.9em;"><strong>Input:</strong></div>
        <pre style="white-space: pre-wrap; background: #1f2937; color: #d1d5db; padding: 10px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #374151;">${escapeHtml(step.prompt)}</pre>
        
        <div style="margin-bottom: 5px; color: #9ca3af; font-size: 0.9em;"><strong>Output:</strong></div>
        <pre style="white-space: pre-wrap; background: #020617; color: #e5e7eb; padding: 10px; border-radius: 6px; border: 1px solid #374151;">${escapeHtml(step.response)}</pre>
    `;

    header.addEventListener("click", () => {
        const isOpen = body.style.display !== "none";
        body.style.display = isOpen ? "none" : "block";
        header.querySelector(".chevron").innerText = isOpen ? "▶" : "▼";
    });

    item.appendChild(header);
    item.appendChild(body);
    container.appendChild(item);
}

async function runAnalysis() {
    console.log("[DEBUG] runAnalysis: start streaming");
    
    const promptEl = document.getElementById("prompt");
    const statusEl = document.getElementById("status");
    const finalEl = document.getElementById("final-response");
    const stepsEl = document.getElementById("steps-container");

    const prompt = promptEl.value.trim();
    if (!prompt) {
        statusEl.textContent = "Please paste your resume text (with GitHub URL).";
        return;
    }

    statusEl.textContent = "Starting multi-agent analysis...";
    finalEl.innerText = ""; 
    stepsEl.innerHTML = "";

    try {
        const resp = await fetch("/api/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt }),
        });

        if (!resp.ok) {
            statusEl.textContent = "Server error: " + resp.status;
            return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let stepCount = 0;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.substring(6);
                    try {
                        const data = JSON.parse(dataStr);
                        
                        if (data.type === "step") {
                            stepCount++;
                            renderSingleStep(data.step, stepsEl, stepCount);
                            statusEl.textContent = `Running... (Step ${stepCount} completed)`;
                            stepsEl.scrollTop = stepsEl.scrollHeight;
                        } else if (data.type === "done") {
                            statusEl.textContent = "Analysis complete.";
                            typeFinalResponse(data.response, finalEl);
                        } else if (data.type === "error") {
                            statusEl.textContent = "Error: " + data.message;
                        }
                    } catch (e) {
                        console.error("[DEBUG] Parse error on stream chunk:", e);
                    }
                }
            }
        }
    } catch (err) {
        console.error("[DEBUG] Error:", err);
        statusEl.textContent = "Failed to communicate with server.";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("run-btn");
    if (btn) btn.addEventListener("click", runAnalysis);
});