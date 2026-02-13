console.log("[DEBUG] static.script: loaded v9.0 (Live Stream + JSON API)");

function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatTracePayload(value) {
    if (value === null || value === undefined) return "";
    if (typeof value === "string") return value;
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
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

function setReportLoading(isLoading) {
    const loadingEl = document.getElementById("report-loading");
    if (!loadingEl) return;
    loadingEl.classList.toggle("is-visible", isLoading);
    loadingEl.setAttribute("aria-hidden", String(!isLoading));
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
        <span class="chevron">></span>
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

    const promptText = formatTracePayload(step.prompt);
    const responseText = formatTracePayload(step.response);

    body.innerHTML = `
        <div style="margin-bottom: 5px; color: #9ca3af; font-size: 0.9em;"><strong>Prompt:</strong></div>
        <pre style="white-space: pre-wrap; background: #1f2937; color: #d1d5db; padding: 10px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #374151;">${escapeHtml(promptText)}</pre>

        <div style="margin-bottom: 5px; color: #9ca3af; font-size: 0.9em;"><strong>Response:</strong></div>
        <pre style="white-space: pre-wrap; background: #020617; color: #e5e7eb; padding: 10px; border-radius: 6px; border: 1px solid #374151;">${escapeHtml(responseText)}</pre>
    `;

    header.addEventListener("click", () => {
        const isOpen = body.style.display !== "none";
        body.style.display = isOpen ? "none" : "block";
        header.querySelector(".chevron").innerText = isOpen ? ">" : "v";
    });

    item.appendChild(header);
    item.appendChild(body);
    container.appendChild(item);
}

async function runAnalysis() {
    console.log("[DEBUG] runAnalysis: start request");

    const promptEl = document.getElementById("prompt");
    const statusEl = document.getElementById("status");
    const finalEl = document.getElementById("final-response");
    const stepsEl = document.getElementById("steps-container");

    const prompt = promptEl.value.trim();
    if (!prompt) {
        statusEl.textContent = "Paste the candidate’s resume text here, including a GitHub URL.";
        setReportLoading(false);
        return;
    }

    statusEl.textContent = "Starting multi-agent analysis...";
    setReportLoading(true);
    finalEl.classList.remove("report-ready");
    finalEl.classList.add("report-pending");
    finalEl.innerText = "";
    stepsEl.innerHTML = "";

    try {
        const resp = await fetch("/api/execute/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt }),
        });

        if (!resp.ok) {
            let errorMsg = "Server error: " + resp.status;
            try {
                const errData = await resp.json();
                if (errData && typeof errData.error === "string" && errData.error.trim()) {
                    errorMsg = "Error: " + errData.error;
                }
            } catch (_) {
                // Keep fallback status message if body is not JSON.
            }
            statusEl.textContent = errorMsg;
            setReportLoading(false);
            finalEl.classList.remove("report-pending");
            return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let stepCount = 0;
        let hasTerminalEvent = false;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const dataStr = line.substring(6);
                try {
                    const data = JSON.parse(dataStr);

                    if (data.type === "step") {
                        stepCount++;
                        renderSingleStep(data.step, stepsEl, stepCount);
                        statusEl.textContent = `Running... (Step ${stepCount} completed)`;
                        stepsEl.scrollTop = stepsEl.scrollHeight;
                    } else if (data.type === "done") {
                        hasTerminalEvent = true;
                        statusEl.textContent = `Analysis complete. (${stepCount} steps)`;
                        setReportLoading(false);
                        finalEl.classList.remove("report-pending");
                        finalEl.classList.add("report-ready");
                        typeFinalResponse(data.response || "", finalEl);
                    } else if (data.type === "error") {
                        hasTerminalEvent = true;
                        statusEl.textContent = "Error: " + (data.message || "Unknown error");
                        setReportLoading(false);
                        finalEl.classList.remove("report-pending");
                    }
                } catch (e) {
                    console.error("[DEBUG] Parse error on stream chunk:", e);
                }
            }
        }

        if (!hasTerminalEvent) {
            statusEl.textContent = "Stream ended unexpectedly.";
            setReportLoading(false);
            finalEl.classList.remove("report-pending");
        }
    } catch (err) {
        console.error("[DEBUG] Error:", err);
        statusEl.textContent = "Failed to communicate with server.";
        setReportLoading(false);
        finalEl.classList.remove("report-pending");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("run-btn");
    if (btn) btn.addEventListener("click", runAnalysis);

    const logo = document.getElementById("brand-logo");
    if (!logo) return;

    logo.addEventListener("mousemove", (event) => {
        const rect = logo.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        const rx = y * -10;
        const ry = x * 10;
        logo.style.transform = `perspective(500px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`;
    });

    logo.addEventListener("mouseleave", () => {
        logo.style.transform = "";
    });
});
