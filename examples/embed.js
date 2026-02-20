(function () {
  const LOCALES = {
    en: {
      placeholder: "Ask anything...",
      send: "Send",
      ready: "Chat ready.",
      tokenError: "Failed to obtain embed token",
      requestError: "Request failed",
      unexpectedError: "Unexpected error",
      networkError: "Network error. Please try again.",
      error401: "Session expired or unauthorized. Please retry.",
      error403: "This site is not allowed to use the chatbot.",
      error429: "Too many requests. Please wait a moment and try again.",
      loading: "Sending...",
      typing: "Assistant is typing...",
      openChatAria: "Open chat",
      closeChatAria: "Minimize chat",
      dialogAria: "Chat window",
      inputAria: "Chat input",
      defaultLauncherIcon: "💬",
      launcherImageAlt: "Chat launcher icon",
    },
    "zh-TW": {
      placeholder: "請輸入想問的內容...",
      send: "送出",
      ready: "聊天室已準備就緒。",
      tokenError: "無法取得嵌入式存取權杖",
      requestError: "請求失敗",
      unexpectedError: "發生未預期的錯誤",
      networkError: "網路異常，請稍後再試。",
      error401: "授權已過期或無效，請重試。",
      error403: "此網站目前不允許使用聊天機器人。",
      error429: "請求過於頻繁，請稍候再試。",
      loading: "傳送中...",
      typing: "助手輸入中...",
      openChatAria: "開啟聊天",
      closeChatAria: "最小化聊天",
      dialogAria: "聊天視窗",
      inputAria: "聊天輸入框",
      defaultLauncherIcon: "💬",
      launcherImageAlt: "聊天啟動圖示",
    },
  };

  const script = document.currentScript;
  if (!script) {
    return;
  }

  const config = {
    apiBaseUrl: script.dataset.apiBaseUrl || "http://127.0.0.1:8000",
    chatbotId: script.dataset.chatbotId || "default-chatbot",
    title: script.dataset.title || "Assistant",
    targetSelector: script.dataset.target || "",
    maxHistoryItems: Number(script.dataset.maxHistoryItems || "20"),
    locale: script.dataset.locale || "",
    localeQueryParam: script.dataset.localeQueryParam || "locale",
    startOpen: script.dataset.startOpen === "true",
    draggable: script.dataset.draggable !== "false",
    launcherIcon: script.dataset.launcherIcon || "",
  };

  const normalizeLocale = function (value) {
    if (!value) {
      return null;
    }
    const lowered = String(value).trim().toLowerCase();
    if (lowered === "zh-tw" || lowered.startsWith("zh-hant")) {
      return "zh-TW";
    }
    if (lowered === "en" || lowered.startsWith("en-")) {
      return "en";
    }
    return null;
  };

  const resolveLocale = function () {
    const candidates = [];
    if (config.locale) {
      candidates.push(config.locale);
    }
    if (config.localeQueryParam) {
      const queryValue = new URLSearchParams(window.location.search).get(config.localeQueryParam);
      if (queryValue) {
        candidates.push(queryValue);
      }
    }
    if (Array.isArray(navigator.languages)) {
      candidates.push.apply(candidates, navigator.languages);
    }
    if (navigator.language) {
      candidates.push(navigator.language);
    }
    if (document.documentElement && document.documentElement.lang) {
      candidates.push(document.documentElement.lang);
    }

    for (const candidate of candidates) {
      const normalized = normalizeLocale(candidate);
      if (normalized) {
        return normalized;
      }
    }
    return "en";
  };

  const locale = resolveLocale();
  const t = LOCALES[locale] || LOCALES.en;

  const styleId = "ocb-embed-style";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = ""
      + ".ocb-widget{position:fixed;right:20px;bottom:20px;z-index:2147483000;font-family:'IBM Plex Sans','Segoe UI',sans-serif;color:#1f2a37;}"
      + ".ocb-launcher{width:58px;height:58px;border-radius:999px;border:0;background:linear-gradient(145deg,#0e7490 0%,#0f766e 100%);color:#fff;box-shadow:0 12px 28px rgba(15,23,42,.25);cursor:pointer;display:grid;place-items:center;font-size:26px;line-height:1;padding:0;font-family:'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji','IBM Plex Sans','Segoe UI',sans-serif;}"
      + ".ocb-launcher:focus-visible,.ocb-chat-form textarea:focus-visible,.ocb-chat-form button:focus-visible,.ocb-minimize:focus-visible{outline:2px solid #0e7490;outline-offset:2px;}"
      + ".ocb-launcher img{width:100%;height:100%;border-radius:999px;object-fit:cover;display:block;}"
      + ".ocb-panel{position:fixed;right:20px;bottom:88px;width:min(94vw,380px);background:#fff;border:1px solid #d6e0ea;border-radius:14px;box-shadow:0 16px 40px rgba(15,23,42,.20);overflow:hidden;display:none;}"
      + ".ocb-widget.ocb-open .ocb-panel{display:block;}"
      + ".ocb-widget.ocb-open .ocb-launcher{display:none;}"
      + ".ocb-chat-header{padding:12px 14px;background:linear-gradient(145deg,#f4f7fb 0%,#eef6f2 100%);border-bottom:1px solid #d6e0ea;display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:grab;}"
      + ".ocb-chat-title{font-weight:600;letter-spacing:.01em;font-size:14px;}"
      + ".ocb-minimize{border:1px solid #c8d5e4;background:#fff;color:#38516b;border-radius:8px;padding:4px 10px;cursor:pointer;font-size:14px;line-height:1;}"
      + ".ocb-chat-log{height:320px;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;background:#fff;}"
      + ".ocb-bubble{padding:10px 12px;border-radius:12px;line-height:1.45;max-width:90%;white-space:pre-wrap;border:1px solid #d6e0ea;font-size:14px;}"
      + ".ocb-bubble.user{align-self:flex-end;background:#dff1ff;}"
      + ".ocb-bubble.assistant{align-self:flex-start;background:#f2f6fb;}"
      + ".ocb-note{color:#5f6b7a;font-size:12px;}"
      + ".ocb-note.ocb-typing{font-style:italic;}"
      + ".ocb-chat-form{border-top:1px solid #d6e0ea;padding:10px;display:grid;grid-template-columns:1fr auto;gap:8px;background:#fff;}"
      + ".ocb-chat-form textarea{resize:vertical;min-height:44px;max-height:140px;border:1px solid #d6e0ea;border-radius:10px;padding:10px;font:inherit;color:#1f2a37;}"
      + ".ocb-chat-form button{border:0;border-radius:10px;background:#0e7490;color:#fff;font-weight:600;padding:0 16px;cursor:pointer;min-width:82px;}"
      + ".ocb-chat-form button:disabled{opacity:.65;cursor:not-allowed;}"
      + "@media (max-width:640px){.ocb-widget{right:8px;bottom:8px;}.ocb-panel{right:8px;left:8px;bottom:76px;width:auto;max-height:70vh;}.ocb-chat-log{height:260px;}.ocb-chat-header{cursor:default;}}";
    document.head.appendChild(style);
  }

  const target = config.targetSelector ? document.querySelector(config.targetSelector) : null;
  const mount = target || document.createElement("div");

  if (!target && script.parentNode) {
    script.parentNode.insertBefore(mount, script.nextSibling);
  }

  mount.innerHTML = ""
    + '<div class="ocb-widget">'
    + `  <button type="button" class="ocb-launcher" aria-label="${t.openChatAria}" aria-expanded="false"></button>`
    + `  <section class="ocb-panel" role="dialog" aria-label="${t.dialogAria}">`
    + '    <div class="ocb-chat-header">'
    + '      <div class="ocb-chat-title"></div>'
    + `      <button type="button" class="ocb-minimize" aria-label="${t.closeChatAria}">−</button>`
    + '    </div>'
    + '    <div class="ocb-chat-log" aria-live="polite"></div>'
    + '    <form class="ocb-chat-form">'
    + `      <textarea rows="2" placeholder="${t.placeholder}" aria-label="${t.inputAria}" required></textarea>`
    + `      <button type="submit">${t.send}</button>`
    + '    </form>'
    + '  </section>'
    + '</div>';

  const rootEl = mount.querySelector(".ocb-widget");
  const launcherEl = mount.querySelector(".ocb-launcher");
  const panelEl = mount.querySelector(".ocb-panel");
  const headerEl = mount.querySelector(".ocb-chat-header");
  const titleEl = mount.querySelector(".ocb-chat-title");
  const minimizeEl = mount.querySelector(".ocb-minimize");
  const logEl = mount.querySelector(".ocb-chat-log");
  const formEl = mount.querySelector(".ocb-chat-form");
  const inputEl = formEl.querySelector("textarea");
  const sendEl = formEl.querySelector("button");

  const history = [];
  const tokenState = { value: "", expiresAt: 0 };
  const dragState = { active: false, dx: 0, dy: 0, width: 0, height: 0 };
  const panelPosition = { x: null, y: null };
  let typingEl = null;
  let isOpen = config.startOpen;

  titleEl.textContent = config.title;

  const isImageIcon = function (value) {
    return /^https?:\/\//i.test(value) || value.startsWith("/");
  };

  const applyLauncherIcon = function () {
    const configured = (config.launcherIcon || "").trim();
    const value = configured || t.defaultLauncherIcon;
    launcherEl.innerHTML = "";
    if (isImageIcon(value)) {
      const image = document.createElement("img");
      image.src = value;
      image.alt = t.launcherImageAlt;
      image.referrerPolicy = "no-referrer";
      launcherEl.appendChild(image);
      return;
    }
    launcherEl.textContent = value;
  };

  const addBubble = function (role, text) {
    const bubble = document.createElement("div");
    bubble.className = "ocb-bubble " + role;
    bubble.textContent = text;
    logEl.appendChild(bubble);
    logEl.scrollTop = logEl.scrollHeight;
  };

  const addNote = function (text, className) {
    const note = document.createElement("div");
    note.className = className ? "ocb-note " + className : "ocb-note";
    note.textContent = text;
    logEl.appendChild(note);
    logEl.scrollTop = logEl.scrollHeight;
    return note;
  };

  const showTyping = function () {
    if (!typingEl) {
      typingEl = addNote(t.typing, "ocb-typing");
    }
  };

  const hideTyping = function () {
    if (typingEl && typingEl.parentNode) {
      typingEl.parentNode.removeChild(typingEl);
    }
    typingEl = null;
  };

  const trimHistory = function () {
    if (history.length > config.maxHistoryItems) {
      history.splice(0, history.length - config.maxHistoryItems);
    }
  };

  const setPending = function (pending) {
    sendEl.disabled = pending;
    sendEl.textContent = pending ? t.loading : t.send;
  };

  const statusErrorMessage = function (status) {
    if (status === 401) {
      return t.error401;
    }
    if (status === 403) {
      return t.error403;
    }
    if (status === 429) {
      return t.error429;
    }
    return null;
  };

  const getErrorMessage = function (error) {
    if (error && error.status) {
      return statusErrorMessage(error.status) || error.detail || t.requestError;
    }
    if (error && error.message) {
      return error.message;
    }
    return t.unexpectedError;
  };

  const getEmbedToken = async function () {
    const now = Date.now();
    if (tokenState.value && tokenState.expiresAt > now + 10000) {
      return tokenState.value;
    }

    let response;
    try {
      response = await fetch(config.apiBaseUrl + "/api/embed/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chatbot_id: config.chatbotId }),
      });
    } catch (_error) {
      throw new Error(t.networkError);
    }

    let payload = {};
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }

    if (!response.ok) {
      const friendly = statusErrorMessage(response.status);
      throw {
        status: response.status,
        detail: friendly || payload.detail || t.tokenError,
      };
    }

    tokenState.value = payload.token || "";
    tokenState.expiresAt = now + Number(payload.expires_in || 0) * 1000;
    if (!tokenState.value) {
      throw new Error(t.tokenError);
    }
    return tokenState.value;
  };

  const isMobileLayout = function () {
    return window.matchMedia("(max-width: 640px), (pointer: coarse)").matches;
  };

  const canDrag = function () {
    return config.draggable && !isMobileLayout();
  };

  const clampPosition = function (left, top) {
    const margin = 8;
    const maxLeft = Math.max(margin, window.innerWidth - dragState.width - margin);
    const maxTop = Math.max(margin, window.innerHeight - dragState.height - margin);
    return {
      left: Math.min(Math.max(left, margin), maxLeft),
      top: Math.min(Math.max(top, margin), maxTop),
    };
  };

  const applyPosition = function () {
    if (panelPosition.x === null || panelPosition.y === null) {
      panelEl.style.left = "";
      panelEl.style.top = "";
      panelEl.style.right = "";
      panelEl.style.bottom = "";
      return;
    }

    panelEl.style.right = "auto";
    panelEl.style.bottom = "auto";
    panelEl.style.left = panelPosition.x + "px";
    panelEl.style.top = panelPosition.y + "px";
  };

  const clearPositionForMobile = function () {
    panelPosition.x = null;
    panelPosition.y = null;
    applyPosition();
  };

  const syncOpenState = function (restoreFocus) {
    rootEl.classList.toggle("ocb-open", isOpen);
    launcherEl.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) {
      setTimeout(function () {
        inputEl.focus();
      }, 0);
    } else if (restoreFocus) {
      launcherEl.focus();
    }
  };

  const openPanel = function () {
    isOpen = true;
    syncOpenState(false);
  };

  const minimizePanel = function (restoreFocus) {
    isOpen = false;
    syncOpenState(restoreFocus);
  };

  applyLauncherIcon();
  addNote(t.ready);
  syncOpenState(false);

  launcherEl.addEventListener("click", openPanel);
  minimizeEl.addEventListener("click", function () {
    minimizePanel(true);
  });

  panelEl.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      event.preventDefault();
      minimizePanel(true);
    }
  });

  inputEl.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      formEl.requestSubmit();
    }
  });

  formEl.addEventListener("submit", async function (event) {
    event.preventDefault();
    const message = inputEl.value.trim();
    if (!message || sendEl.disabled) {
      return;
    }

    addBubble("user", message);
    history.push({ role: "user", content: message });
    trimHistory();
    inputEl.value = "";
    setPending(true);
    showTyping();

    try {
      const embedToken = await getEmbedToken();
      let response;
      try {
        response = await fetch(config.apiBaseUrl + "/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Embed-Token": embedToken,
          },
          body: JSON.stringify({
            message: message,
            history: history.slice(0, -1),
          }),
        });
      } catch (_error) {
        throw new Error(t.networkError);
      }

      let payload = {};
      try {
        payload = await response.json();
      } catch (_error) {
        payload = {};
      }

      if (!response.ok) {
        const friendly = statusErrorMessage(response.status);
        throw {
          status: response.status,
          detail: friendly || payload.detail || t.requestError,
        };
      }

      addBubble("assistant", payload.reply);
      history.push({ role: "assistant", content: payload.reply });
      trimHistory();
    } catch (error) {
      addNote(getErrorMessage(error));
    } finally {
      hideTyping();
      setPending(false);
    }
  });

  headerEl.addEventListener("pointerdown", function (event) {
    if (!canDrag() || event.target.closest("button")) {
      return;
    }
    dragState.active = true;
    const rect = panelEl.getBoundingClientRect();
    dragState.width = rect.width;
    dragState.height = rect.height;
    dragState.dx = event.clientX - rect.left;
    dragState.dy = event.clientY - rect.top;
    headerEl.style.cursor = "grabbing";
    headerEl.setPointerCapture(event.pointerId);
  });

  headerEl.addEventListener("pointermove", function (event) {
    if (!dragState.active) {
      return;
    }
    const next = clampPosition(event.clientX - dragState.dx, event.clientY - dragState.dy);
    panelPosition.x = next.left;
    panelPosition.y = next.top;
    applyPosition();
  });

  headerEl.addEventListener("pointerup", function (event) {
    if (!dragState.active) {
      return;
    }
    dragState.active = false;
    headerEl.style.cursor = canDrag() ? "grab" : "default";
    headerEl.releasePointerCapture(event.pointerId);
    // TODO(v0.1.2): persist panelPosition in localStorage and restore on init.
  });

  headerEl.addEventListener("pointercancel", function (event) {
    if (!dragState.active) {
      return;
    }
    dragState.active = false;
    headerEl.style.cursor = canDrag() ? "grab" : "default";
    headerEl.releasePointerCapture(event.pointerId);
  });

  window.addEventListener("resize", function () {
    if (isMobileLayout()) {
      clearPositionForMobile();
      headerEl.style.cursor = "default";
      return;
    }
    headerEl.style.cursor = canDrag() ? "grab" : "default";
    if (panelPosition.x !== null && panelPosition.y !== null) {
      const rect = panelEl.getBoundingClientRect();
      dragState.width = rect.width;
      dragState.height = rect.height;
      const next = clampPosition(panelPosition.x, panelPosition.y);
      panelPosition.x = next.left;
      panelPosition.y = next.top;
      applyPosition();
    }
  });

  if (isMobileLayout()) {
    clearPositionForMobile();
    headerEl.style.cursor = "default";
  } else {
    headerEl.style.cursor = canDrag() ? "grab" : "default";
  }
})();
