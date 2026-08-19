function summarizeCapture(capture) {
  if (!capture || !capture.frames) return "(none)";
  return capture.frames
    .map((f) => {
      const s = f.summary || {};
      return `frame ${f.frameId} — ${s.url}\n  forms: ${(s.forms || []).length}, loose_fields: ${(s.loose_fields || []).length}, buttons: ${(s.buttons || []).length}, links: ${(s.links || []).length}`;
    })
    .join("\n");
}

function render(state) {
  const statusEl = document.getElementById("status");
  statusEl.textContent = state.connected ? "Connected" : "Disconnected";
  statusEl.className = state.connected ? "connected" : "disconnected";
  document.getElementById("lastMessage").textContent =
    state.lastMessage ? JSON.stringify(state.lastMessage, null, 2) : "(none)";
  document.getElementById("lastCapture").textContent = summarizeCapture(state.lastCapture);
}

chrome.runtime.sendMessage({ type: "get_state" }, (state) => {
  if (state) render(state);
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "sentinel_state") render(message.state);
});

document.getElementById("pingBtn").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "send_test_ping" });
});

document.getElementById("captureBtn").addEventListener("click", () => {
  document.getElementById("lastCapture").textContent = "capturing...";
  chrome.runtime.sendMessage({ type: "capture_active_tab" }, (response) => {
    if (response && response.ok) {
      document.getElementById("lastCapture").textContent = summarizeCapture(response.capture);
    } else {
      document.getElementById("lastCapture").textContent =
        "error: " + (response ? response.error : "no response");
    }
  });
});
