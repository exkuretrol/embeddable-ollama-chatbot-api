(function () {
  const script = document.currentScript;
  if (!script) {
    return;
  }

  const config = {
    apiBaseUrl: script.dataset.apiBaseUrl || "http://127.0.0.1:8000",
    apiKey: script.dataset.apiKey || "replace-with-your-api-key",
    title: script.dataset.title || "Assistant",
    targetSelector: script.dataset.target || "",
    maxHistoryItems: Number(script.dataset.maxHistoryItems || "20"),
  };

  const styleId = "ocb-embed-style";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = ""
      + ".ocb-chat-root{--ocb-bg:linear-gradient(145deg,#f4f7fb 0%,#eef6f2 100%);--ocb-card:#fff;--ocb-text:#1f2a37;--ocb-muted:#5f6b7a;--ocb-border:#d6e0ea;--ocb-user:#dff1ff;--ocb-assistant:#f2f6fb;--ocb-accent:#0e7490;max-width:640px;margin:0 auto;font-family:'IBM Plex Sans','Segoe UI',sans-serif;color:var(--ocb-text);background:var(--ocb-bg);border-radius:16px;padding:12px;}"
      + ".ocb-chat-card{background:var(--ocb-card);border:1px solid var(--ocb-border);border-radius:14px;overflow:hidden;}"
      + ".ocb-chat-header{padding:12px 14px;border-bottom:1px solid var(--ocb-border);font-weight:600;letter-spacing:.02em;}"
      + ".ocb-chat-log{height:320px;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;}"
      + ".ocb-bubble{padding:10px 12px;border-radius:12px;line-height:1.45;max-width:90%;white-space:pre-wrap;border:1px solid var(--ocb-border);font-size:14px;}"
      + ".ocb-bubble.user{align-self:flex-end;background:var(--ocb-user);}"
      + ".ocb-bubble.assistant{align-self:flex-start;background:var(--ocb-assistant);}"
      + ".ocb-chat-form{border-top:1px solid var(--ocb-border);padding:10px;display:grid;grid-template-columns:1fr auto;gap:8px;}"
      + ".ocb-chat-form textarea{resize:vertical;min-height:44px;max-height:120px;border:1px solid var(--ocb-border);border-radius:10px;padding:10px;font:inherit;color:var(--ocb-text);}"
      + ".ocb-chat-form button{border:0;border-radius:10px;background:var(--ocb-accent);color:#fff;font-weight:600;padding:0 16px;cursor:pointer;}"
      + ".ocb-chat-form button:disabled{opacity:.6;cursor:not-allowed;}"
      + ".ocb-note{color:var(--ocb-muted);font-size:12px;}"
      + "@media (max-width:640px){.ocb-chat-root{border-radius:12px;padding:8px;}.ocb-chat-log{height:280px;}}";
    document.head.appendChild(style);
  }

  const target = config.targetSelector
    ? document.querySelector(config.targetSelector)
    : null;
  const mount = target || document.createElement("div");

  if (!target && script.parentNode) {
    script.parentNode.insertBefore(mount, script.nextSibling);
  }

  mount.innerHTML = ""
    + '<div class="ocb-chat-root">'
    + '  <div class="ocb-chat-card">'
    + '    <div class="ocb-chat-header"></div>'
    + '    <div class="ocb-chat-log"></div>'
    + '    <form class="ocb-chat-form">'
    + '      <textarea rows="2" placeholder="Ask anything..." required></textarea>'
    + '      <button type="submit">Send</button>'
    + '    </form>'
    + '  </div>'
    + '</div>';

  const root = mount.querySelector(".ocb-chat-root");
  const titleEl = mount.querySelector(".ocb-chat-header");
  const logEl = mount.querySelector(".ocb-chat-log");
  const formEl = mount.querySelector(".ocb-chat-form");
  const inputEl = formEl.querySelector("textarea");
  const sendEl = formEl.querySelector("button");
  const history = [];

  titleEl.textContent = config.title;

  const addBubble = function (role, text) {
    const bubble = document.createElement("div");
    bubble.className = "ocb-bubble " + role;
    bubble.textContent = text;
    logEl.appendChild(bubble);
    logEl.scrollTop = logEl.scrollHeight;
  };

  const addNote = function (text) {
    const note = document.createElement("div");
    note.className = "ocb-note";
    note.textContent = text;
    logEl.appendChild(note);
    logEl.scrollTop = logEl.scrollHeight;
  };

  const trimHistory = function () {
    if (history.length > config.maxHistoryItems) {
      history.splice(0, history.length - config.maxHistoryItems);
    }
  };

  addNote("Chat ready.");

  formEl.addEventListener("submit", async function (event) {
    event.preventDefault();
    const message = inputEl.value.trim();
    if (!message) {
      return;
    }

    addBubble("user", message);
    history.push({ role: "user", content: message });
    trimHistory();
    inputEl.value = "";
    sendEl.disabled = true;

    try {
      const response = await fetch(config.apiBaseUrl + "/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": config.apiKey,
        },
        body: JSON.stringify({
          message: message,
          history: history.slice(0, -1),
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Request failed");
      }

      addBubble("assistant", payload.reply);
      history.push({ role: "assistant", content: payload.reply });
      trimHistory();
    } catch (error) {
      const messageText = error && error.message ? error.message : "Unexpected error";
      addNote(messageText);
    } finally {
      sendEl.disabled = false;
    }
  });
})();
