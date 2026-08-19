// Owns the WebSocket. Runs in an offscreen document, not the service
// worker, so it isn't killed by the SW idle timer. Just relays raw
// messages to/from background.js.

const WS_URL = "ws://localhost:8100/ws/extension/";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

let socket = null;
let reconnectDelay = RECONNECT_BASE_MS;

function connect() {
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    reconnectDelay = RECONNECT_BASE_MS;
    chrome.runtime.sendMessage({ type: "ws_open" }).catch(() => {});
    socket.send(JSON.stringify({ type: "hello", source: "extension" }));
  };

  socket.onmessage = (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      payload = { raw: event.data };
    }
    chrome.runtime.sendMessage({ type: "ws_event", payload }).catch(() => {});
  };

  socket.onclose = () => {
    chrome.runtime.sendMessage({ type: "ws_close" }).catch(() => {});
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_MS);
  };

  socket.onerror = () => socket.close();
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "ws_send" && socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message.payload));
  }
});

connect();
