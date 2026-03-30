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
      clearLabel: "Clear",
      clearAria: "Clear chat history",
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
      clearLabel: "清除",
      clearAria: "清除聊天紀錄",
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
    persistHistory: script.dataset.persistHistory !== "false",
    historyTtlSeconds: Number(script.dataset.historyTtlSeconds || "86400"),
    historyStorageKey: script.dataset.historyStorageKey || "",
  };

  if (!Number.isFinite(config.historyTtlSeconds) || config.historyTtlSeconds <= 0) {
    config.historyTtlSeconds = 86400;
  }

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

  const widgetCss = ""
    + ":host,:host *,:host *::before,:host *::after{box-sizing:border-box;}"
    + ".ocb-widget{position:fixed;right:20px;bottom:20px;z-index:2147483000;font-family:'IBM Plex Sans','Segoe UI',sans-serif;color:#1f2a37;}"
    + ".ocb-launcher{width:58px;height:58px;border-radius:999px;border:0;background:linear-gradient(145deg,#0e7490 0%,#0f766e 100%);color:#fff;box-shadow:0 12px 28px rgba(15,23,42,.25);cursor:pointer;display:grid;place-items:center;font-size:26px;line-height:1;padding:0;font-family:'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji','IBM Plex Sans','Segoe UI',sans-serif;}"
    + ".ocb-launcher:focus-visible,.ocb-chat-form textarea:focus-visible,.ocb-chat-form button:focus-visible,.ocb-clear:focus-visible,.ocb-minimize:focus-visible{outline:2px solid #0e7490;outline-offset:2px;}"
    + ".ocb-launcher img{width:100%;height:100%;border-radius:999px;object-fit:cover;display:block;}"
    + ".ocb-panel{position:fixed;right:20px;bottom:88px;width:min(94vw,380px);background:#fff;border:1px solid #d6e0ea;border-radius:14px;box-shadow:0 16px 40px rgba(15,23,42,.20);overflow:hidden;display:none;}"
    + ".ocb-widget.ocb-open .ocb-panel{display:block;}"
    + ".ocb-widget.ocb-open .ocb-launcher{display:none;}"
    + ".ocb-chat-header{padding:12px 14px;background:linear-gradient(145deg,#f4f7fb 0%,#eef6f2 100%);border-bottom:1px solid #d6e0ea;display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:grab;}"
    + ".ocb-chat-title{font-weight:600;letter-spacing:.01em;font-size:14px;}"
    + ".ocb-header-actions{display:flex;align-items:center;gap:6px;}"
    + ".ocb-clear{border:1px solid #d5e0ea;background:#fff;color:#4a6077;border-radius:8px;padding:4px 10px;cursor:pointer;font-size:12px;line-height:1.2;}"
    + ".ocb-minimize{border:1px solid #c8d5e4;background:#fff;color:#38516b;border-radius:8px;padding:4px 10px;cursor:pointer;font-size:14px;line-height:1;}"
    + ".ocb-chat-log{height:320px;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;background:#fff;}"
    + ".ocb-bubble{padding:10px 12px;border-radius:12px;line-height:1.45;max-width:90%;white-space:pre-wrap;border:1px solid #d6e0ea;font-size:14px;}"
    + ".ocb-bubble.user{align-self:flex-end;background:#dff1ff;}"
    + ".ocb-bubble.assistant{align-self:flex-start;background:#f2f6fb;}"
    + ".ocb-bubble.assistant p{margin:0 0 10px;}"
    + ".ocb-bubble.assistant p:last-child{margin-bottom:0;}"
    + ".ocb-bubble.assistant ul,.ocb-bubble.assistant ol{margin:0 0 10px 20px;padding:0;}"
    + ".ocb-bubble.assistant li{margin:2px 0;}"
    + ".ocb-bubble.assistant pre{margin:0 0 10px;padding:10px;border-radius:8px;background:#0f172a;color:#e2e8f0;overflow:auto;white-space:pre;}"
    + ".ocb-bubble.assistant code{font-family:'IBM Plex Mono','SFMono-Regular',Menlo,monospace;font-size:12px;background:#e6edf5;border-radius:6px;padding:1px 4px;white-space:break-spaces;}"
    + ".ocb-bubble.assistant pre code{background:transparent;padding:0;color:inherit;white-space:pre;}"
    + ".ocb-bubble.assistant blockquote{margin:0 0 10px;padding:6px 10px;border-left:3px solid #7ea3c2;background:#eaf2f8;color:#2f455a;}"
    + ".ocb-bubble.assistant a{color:#0b5f7a;text-decoration:underline;word-break:break-word;}"
    + ".ocb-note{color:#5f6b7a;font-size:12px;}"
    + ".ocb-note.ocb-typing{font-style:italic;}"
    + ".ocb-chat-form{border-top:1px solid #d6e0ea;padding:10px;display:grid;grid-template-columns:1fr auto;gap:8px;background:#fff;}"
    + ".ocb-chat-form textarea{resize:vertical;min-height:44px;max-height:140px;border:1px solid #d6e0ea;border-radius:10px;padding:10px;font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:14px;color:#1f2a37;}"
    + ".ocb-chat-form button{border:0;border-radius:10px;background:#0e7490;color:#fff;font-weight:600;font-size:13px;padding:0 16px;cursor:pointer;min-width:82px;}"
    + ".ocb-chat-form button:disabled{opacity:.65;cursor:not-allowed;}"
    + "@media (max-width:640px){.ocb-widget{right:8px;bottom:8px;}.ocb-panel{right:8px;left:8px;bottom:76px;width:auto;max-height:70vh;}.ocb-chat-log{height:260px;}.ocb-chat-form textarea{font-size:16px;}.ocb-chat-header{cursor:default;}}";

  const target = config.targetSelector ? document.querySelector(config.targetSelector) : null;
  const mount = target || document.createElement("div");

  if (!target && script.parentNode) {
    script.parentNode.insertBefore(mount, script.nextSibling);
  }

  const shadow = mount.shadowRoot || mount.attachShadow({ mode: "open" });

  shadow.innerHTML = ""
    + `<style>${widgetCss}</style>`
    + '<div class="ocb-widget">'
    + `  <button type="button" class="ocb-launcher" aria-label="${t.openChatAria}" aria-expanded="false"></button>`
    + `  <section class="ocb-panel" role="dialog" aria-label="${t.dialogAria}">`
    + '    <div class="ocb-chat-header">'
    + '      <div class="ocb-chat-title"></div>'
    + '      <div class="ocb-header-actions">'
    + `        <button type="button" class="ocb-clear" aria-label="${t.clearAria}">${t.clearLabel}</button>`
    + `        <button type="button" class="ocb-minimize" aria-label="${t.closeChatAria}">−</button>`
    + '      </div>'
    + '    </div>'
    + '    <div class="ocb-chat-log" aria-live="polite"></div>'
    + '    <form class="ocb-chat-form">'
    + `      <textarea rows="2" placeholder="${t.placeholder}" aria-label="${t.inputAria}" required></textarea>`
    + `      <button type="submit">${t.send}</button>`
    + '    </form>'
    + '  </section>'
    + '</div>';

  const rootEl = shadow.querySelector(".ocb-widget");
  const launcherEl = shadow.querySelector(".ocb-launcher");
  const panelEl = shadow.querySelector(".ocb-panel");
  const headerEl = shadow.querySelector(".ocb-chat-header");
  const titleEl = shadow.querySelector(".ocb-chat-title");
  const clearEl = shadow.querySelector(".ocb-clear");
  const minimizeEl = shadow.querySelector(".ocb-minimize");
  const logEl = shadow.querySelector(".ocb-chat-log");
  const formEl = shadow.querySelector(".ocb-chat-form");
  const inputEl = formEl.querySelector("textarea");
  const sendEl = formEl.querySelector("button");

  const history = [];
  const inputHistory = [];
  let inputHistoryIndex = -1;
  const tokenState = { value: "", expiresAt: 0 };
  const dragState = { active: false, dx: 0, dy: 0, width: 0, height: 0 };
  const panelPosition = { x: null, y: null };
  const markdownLibState = { ready: null };
  let typingEl = null;
  let isOpen = config.startOpen;
  let isComposing = false;

  titleEl.textContent = config.title;

  const isImageIcon = function (value) {
    return /^https?:\/\//i.test(value) || value.startsWith("/");
  };

  const historyStorageKey = function () {
    if (config.historyStorageKey) {
      return config.historyStorageKey;
    }
    return ["ocb", "history", window.location.origin, config.apiBaseUrl, config.chatbotId].join(":");
  };

  const isValidHistoryItem = function (item) {
    return Boolean(
      item
      && (item.role === "user" || item.role === "assistant" || item.role === "system")
      && typeof item.content === "string"
    );
  };

  const readPersistedHistory = function () {
    if (!config.persistHistory) {
      return [];
    }
    try {
      const raw = window.localStorage.getItem(historyStorageKey());
      if (!raw) {
        return [];
      }
      const payload = JSON.parse(raw);
      if (!payload || !Array.isArray(payload.history)) {
        return [];
      }

      const savedAt = Number(payload.saved_at || 0);
      const ttlSeconds = Number(payload.ttl_seconds || config.historyTtlSeconds);
      if (!savedAt || !Number.isFinite(ttlSeconds) || ttlSeconds <= 0) {
        return [];
      }

      if (Date.now() - savedAt > ttlSeconds * 1000) {
        window.localStorage.removeItem(historyStorageKey());
        return [];
      }

      const valid = payload.history.filter(isValidHistoryItem);
      if (valid.length === 0) {
        return [];
      }
      return valid;
    } catch (_error) {
      return [];
    }
  };

  const writePersistedHistory = function () {
    if (!config.persistHistory) {
      return;
    }
    try {
      const payload = {
        v: 1,
        saved_at: Date.now(),
        ttl_seconds: config.historyTtlSeconds,
        history: history,
      };
      window.localStorage.setItem(historyStorageKey(), JSON.stringify(payload));
    } catch (_error) {
      // Best effort persistence only.
    }
  };

  const clearPersistedHistory = function () {
    if (!config.persistHistory) {
      return;
    }
    try {
      window.localStorage.removeItem(historyStorageKey());
    } catch (_error) {
      // Ignore storage errors.
    }
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

  const loadScript = function (src) {
    return new Promise(function (resolve, reject) {
      const scriptEl = document.createElement("script");
      scriptEl.src = src;
      scriptEl.async = true;
      scriptEl.onload = function () {
        resolve();
      };
      scriptEl.onerror = function () {
        reject(new Error("failed to load " + src));
      };
      document.head.appendChild(scriptEl);
    });
  };

  const ensureMarkdownLibraries = async function () {
    if (window.marked && window.DOMPurify) {
      return true;
    }
    if (!markdownLibState.ready) {
      markdownLibState.ready = (async function () {
        if (!window.marked) {
          await loadScript("https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js");
        }
        if (!window.DOMPurify) {
          await loadScript("https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js");
        }
      })();
    }

    try {
      await markdownLibState.ready;
      return Boolean(window.marked && window.DOMPurify);
    } catch (_error) {
      return false;
    }
  };

  const renderMarkdownHtml = function (text) {
    if (!window.marked || !window.DOMPurify) {
      return null;
    }

    window.marked.setOptions({
      gfm: true,
      breaks: true,
      headerIds: false,
      mangle: false,
    });

    const rawHtml = window.marked.parse(String(text || ""));
    return window.DOMPurify.sanitize(rawHtml, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ["style", "script", "iframe", "object", "embed", "link", "meta"],
      FORBID_ATTR: ["onerror", "onclick", "onload", "style"],
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
    });
  };

  const addBubble = function (role, text) {
    const bubble = document.createElement("div");
    bubble.className = "ocb-bubble " + role;
    bubble.textContent = text;
    logEl.appendChild(bubble);
    logEl.scrollTop = logEl.scrollHeight;
  };

  const addAssistantBubble = async function (text) {
    const bubble = document.createElement("div");
    bubble.className = "ocb-bubble assistant";

    const ready = await ensureMarkdownLibraries();
    if (ready) {
      const safeHtml = renderMarkdownHtml(text);
      if (safeHtml) {
        bubble.innerHTML = safeHtml;
      } else {
        bubble.textContent = text;
      }
    } else {
      bubble.textContent = text;
    }

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

  const clearChat = function () {
    history.length = 0;
    clearPersistedHistory();
    hideTyping();
    logEl.innerHTML = "";
    addNote(t.ready);
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
  readPersistedHistory().forEach(function (item) {
    history.push({ role: item.role, content: item.content });
  });
  trimHistory();

  const renderInitialHistory = async function () {
    for (const item of history) {
      if (item.role === "assistant") {
        await addAssistantBubble(item.content);
      } else {
        addBubble(item.role, item.content);
      }
    }
    addNote(t.ready);
  };

  renderInitialHistory();
  syncOpenState(false);

  launcherEl.addEventListener("click", openPanel);
  clearEl.addEventListener("click", function () {
    clearChat();
  });
  minimizeEl.addEventListener("click", function () {
    minimizePanel(true);
  });

  panelEl.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      event.preventDefault();
      minimizePanel(true);
    }
  });

  inputEl.addEventListener("compositionstart", function () {
    isComposing = true;
  });

  inputEl.addEventListener("compositionend", function () {
    isComposing = false;
  });

  inputEl.addEventListener("keydown", function (event) {
    if (event.key === "ArrowUp" && !inputEl.value) {
      if (!inputHistory.length) return;
      event.preventDefault();
      if (inputHistoryIndex === -1) {
        inputHistoryIndex = inputHistory.length - 1;
      } else if (inputHistoryIndex > 0) {
        inputHistoryIndex -= 1;
      }
      inputEl.value = inputHistory[inputHistoryIndex];
      inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
      return;
    }
    if (event.key === "ArrowDown" && inputHistoryIndex !== -1) {
      event.preventDefault();
      if (inputHistoryIndex < inputHistory.length - 1) {
        inputHistoryIndex += 1;
        inputEl.value = inputHistory[inputHistoryIndex];
      } else {
        inputHistoryIndex = -1;
        inputEl.value = "";
      }
      inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
      return;
    }
    if (event.key === "Escape" && inputEl.value) {
      event.preventDefault();
      inputEl.value = "";
      inputHistoryIndex = -1;
      return;
    }
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") {
      inputHistoryIndex = -1;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      if (isComposing || event.isComposing || event.keyCode === 229) {
        return;
      }
      event.preventDefault();
      formEl.requestSubmit();
    }
  });

  formEl.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (isComposing) {
      return;
    }
    const message = inputEl.value.trim();
    if (!message || sendEl.disabled) {
      return;
    }

    if (inputHistory[inputHistory.length - 1] !== message) {
      inputHistory.push(message);
    }
    inputHistoryIndex = -1;
    addBubble("user", message);
    history.push({ role: "user", content: message });
    trimHistory();
    writePersistedHistory();
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

      await addAssistantBubble(payload.reply);
      history.push({ role: "assistant", content: payload.reply });
      trimHistory();
      writePersistedHistory();
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
