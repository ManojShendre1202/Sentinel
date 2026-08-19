// Thin relay + DOM driver. The WebSocket lives in offscreen.js — this
// worker just reacts to messages and can be killed/respawned freely.

const PAGE_SCRIPT_FILE = "page_scripts.js";
const CAPTURE_SETTLE_MS = 1200;

let state = { connected: false, lastMessage: null, lastCapture: null };

async function ensureOffscreenDocument() {
  if (await chrome.offscreen.hasDocument()) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["WORKERS"],
    justification: "Persistent WebSocket connection to backend",
  });
}

async function getActiveTaskTabId() {
  const { activeTaskTabId } = await chrome.storage.session.get("activeTaskTabId");
  return activeTaskTabId ?? null;
}

async function setActiveTaskTabId(tabId) {
  await chrome.storage.session.set({ activeTaskTabId: tabId });
}

function broadcastState() {
  chrome.runtime.sendMessage({ type: "sentinel_state", state }).catch(() => {});
}

function wsSend(payload) {
  chrome.runtime.sendMessage({ type: "ws_send", payload }).catch(() => {});
}

async function capturePage(tabId) {
  await chrome.scripting.executeScript({ target: { tabId, allFrames: true }, files: [PAGE_SCRIPT_FILE] });
  // let modals/popups actually render before reading the DOM
  await new Promise((resolve) => setTimeout(resolve, CAPTURE_SETTLE_MS));
  const results = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    func: () => summarizePage(),
  });
  return { frames: results.map((r) => ({ frameId: r.frameId, summary: r.result })) };
}

async function runAction(tabId, frameId, action) {
  await chrome.scripting.executeScript({ target: { tabId, frameIds: [frameId] }, files: [PAGE_SCRIPT_FILE] });
  const results = await chrome.scripting.executeScript({
    target: { tabId, frameIds: [frameId] },
    func: (a) => executeAction(a),
    args: [action],
  });
  return results[0] ? results[0].result : { ok: false, error: "no_result" };
}

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? tab.id : null;
}

async function handleWsEvent(data) {
  if (data.type === "capture_page") {
    const tabId = (await getActiveTaskTabId()) || (await getActiveTabId());
    try {
      const capture = await capturePage(tabId);
      wsSend({ type: "page_structure", task_id: data.task_id, tab_id: tabId, ...capture });
    } catch (err) {
      wsSend({ type: "capture_error", task_id: data.task_id, error: String(err) });
    }
  }

  if (data.type === "navigate") {
    try {
      const tab = await chrome.tabs.create({ url: data.url, active: true });
      await setActiveTaskTabId(tab.id);
      await new Promise((resolve) => {
        function onUpdated(tabId, changeInfo) {
          if (tabId === tab.id && changeInfo.status === "complete") {
            chrome.tabs.onUpdated.removeListener(onUpdated);
            resolve();
          }
        }
        chrome.tabs.onUpdated.addListener(onUpdated);
      });
      wsSend({ type: "navigated", task_id: data.task_id, tab_id: tab.id, url: data.url });
    } catch (err) {
      wsSend({ type: "navigate_error", task_id: data.task_id, error: String(err) });
    }
  }

  if (data.type === "action") {
    const tabId = (await getActiveTaskTabId()) || (await getActiveTabId());
    try {
      const result = await runAction(tabId, data.frame_id || 0, data.action);
      wsSend({ type: "action_result", task_id: data.task_id, result });
    } catch (err) {
      wsSend({ type: "action_error", task_id: data.task_id, error: String(err) });
    }
  }
}

// A new tab opening (e.g. off-site Apply) takes over as the active task tab.
chrome.tabs.onCreated.addListener(async (tab) => {
  if ((await getActiveTaskTabId()) !== null) {
    await setActiveTaskTabId(tab.id);
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "ws_open") {
    state.connected = true;
    broadcastState();
    return false;
  }

  if (message.type === "ws_close") {
    state.connected = false;
    broadcastState();
    return false;
  }

  if (message.type === "ws_event") {
    state.lastMessage = message.payload;
    broadcastState();
    handleWsEvent(message.payload);
    return false;
  }

  if (message.type === "get_state") {
    sendResponse(state);
    return true;
  }

  if (message.type === "send_test_ping") {
    wsSend({ type: "ping", ts: Date.now() });
    return false;
  }

  if (message.type === "capture_active_tab") {
    (async () => {
      const tabId = await getActiveTabId();
      await setActiveTaskTabId(tabId);
      try {
        const capture = await capturePage(tabId);
        state.lastCapture = capture;
        broadcastState();
        wsSend({ type: "page_structure", task_id: "manual_test", tab_id: tabId, ...capture });
        sendResponse({ ok: true, capture });
      } catch (err) {
        sendResponse({ ok: false, error: String(err) });
      }
    })();
    return true;
  }

  return false;
});

chrome.runtime.onStartup.addListener(ensureOffscreenDocument);
chrome.runtime.onInstalled.addListener(ensureOffscreenDocument);
ensureOffscreenDocument();
