(() => {
  const helperBase = window.__CODEX_MATE_HELPER__ || "http://127.0.0.1:57321";
  const buttonClass = "codex-delete-button";
  const styleId = "codex-delete-style";
  const codexDeleteStyleVersion = "6";
  const codexMateMenuId = "codex-mate-menu";
  const codexDeleteVersion = "5";
  const codexArchiveDeleteAllVersion = "2";
  const codexMateVersion = "1.1.4";
  const codexMateSettingsKey = "codexMateSettings";

  function installStyle() {
    const existingStyle = document.getElementById(styleId);
    if (existingStyle?.dataset.codexDeleteStyleVersion === codexDeleteStyleVersion) return;
    existingStyle?.remove();
    const style = document.createElement("style");
    style.id = styleId;
    style.dataset.codexDeleteStyleVersion = codexDeleteStyleVersion;
    style.textContent = `
      .${buttonClass} {
        position: absolute;
        right: 28px;
        top: 50%;
        transform: translateY(-50%);
        z-index: 20;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 38px;
        height: 22px;
        opacity: 0;
        border: 1px solid rgba(148, 163, 184, .28);
        border-radius: 6px;
        background: rgba(248, 250, 252, .74);
        color: #64748b;
        font: inherit;
        font-size: 12px;
        font-weight: 500;
        line-height: 18px;
        letter-spacing: 0;
        padding: 0 8px;
        cursor: pointer;
        box-shadow: none;
        transition: opacity .12s ease, color .12s ease, background .12s ease, border-color .12s ease;
        -webkit-app-region: no-drag;
      }
      .${buttonClass}:hover,
      .${buttonClass}:focus-visible {
        border-color: rgba(220, 38, 38, .42);
        background: rgba(254, 242, 242, .96);
        color: #dc2626;
        opacity: 1;
      }
      .${buttonClass}:focus-visible {
        outline: 2px solid rgba(220, 38, 38, .28);
        outline-offset: 2px;
      }
      [data-codex-delete-row="true"]:hover .${buttonClass} { opacity: 1; }
      [data-codex-delete-row="true"].codex-archive-confirm-visible .${buttonClass} { right: 66px; }
      .codex-archive-delete-all {
        border: 1px solid #ef4444;
        border-radius: 7px;
        background: #fee2e2;
        color: #991b1b;
        font: 12px system-ui, sans-serif;
        line-height: 16px;
        padding: 3px 8px;
        cursor: pointer;
      }
      .codex-archive-action-bar {
        position: fixed;
        right: 28px;
        top: 86px;
        z-index: 2147482999;
        box-shadow: 0 8px 24px rgba(0,0,0,.18);
      }
      .codex-delete-toast {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 2147483000;
        padding: 10px 12px;
        border-radius: 8px;
        background: #111827;
        color: white;
        font: 13px system-ui, sans-serif;
        box-shadow: 0 8px 30px rgba(0,0,0,.25);
        pointer-events: none;
      }
      .codex-delete-toast button { margin-left: 10px; pointer-events: auto; }
      .codex-delete-confirm-overlay {
        position: fixed;
        inset: 0;
        z-index: 2147483200;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(15,23,42,.28);
      }
      .codex-delete-confirm-content {
        width: min(420px, calc(100vw - 48px));
        border: 1px solid rgba(15,23,42,.12);
        border-radius: 12px;
        background: #ffffff;
        color: #111827;
        font: 14px system-ui, sans-serif;
        box-shadow: 0 24px 80px rgba(15,23,42,.22);
        padding: 18px;
      }
      .codex-delete-confirm-title { font-size: 16px; font-weight: 650; }
      .codex-delete-confirm-message { margin-top: 8px; color: #4b5563; line-height: 1.45; }
      .codex-delete-confirm-actions {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        margin-top: 18px;
      }
      .codex-delete-confirm-actions button {
        border: 1px solid #d1d5db;
        border-radius: 7px;
        padding: 6px 12px;
        background: #ffffff;
        color: #111827;
        font: 13px system-ui, sans-serif;
      }
      .codex-delete-confirm-actions [data-codex-delete-confirm="true"] {
        border-color: #ef4444;
        background: #dc2626;
      }
      #${codexMateMenuId}.codex-mate-menu-floating {
        position: fixed;
        top: 0;
        right: 140px;
        left: auto;
        z-index: 2147483645;
        height: 30px;
        color: #d1d5db;
        font: 13px system-ui, sans-serif;
        text-align: right;
        pointer-events: auto;
        -webkit-app-region: no-drag;
      }
      #${codexMateMenuId} {
        display: inline-flex;
        align-items: center;
        height: 100%;
        flex: 0 0 auto;
        pointer-events: auto;
        -webkit-app-region: no-drag;
      }
      .codex-mate-trigger {
        border: 0;
        background: transparent;
        color: inherit;
        font: inherit;
        height: 100%;
        padding: 0 8px;
        cursor: pointer;
        pointer-events: auto;
        -webkit-app-region: no-drag;
      }
      .codex-mate-modal-overlay {
        position: fixed;
        inset: 0;
        z-index: 2147483646;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0,0,0,.45);
      }
      .codex-mate-modal-content {
        width: min(520px, calc(100vw - 48px));
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 18px;
        background: #2b2b2b;
        color: #f3f4f6;
        font: 14px system-ui, sans-serif;
        box-shadow: 0 24px 80px rgba(0,0,0,.45);
      }
      .codex-mate-modal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 18px 20px 10px;
      }
      .codex-mate-modal-title { font-size: 18px; font-weight: 650; }
      .codex-mate-modal-close {
        border: 0;
        background: transparent;
        color: #d1d5db;
        font-size: 20px;
        cursor: default;
      }
      .codex-mate-modal-body { padding: 8px 20px 20px; }
      .codex-mate-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 12px 0;
        border-top: 1px solid rgba(255,255,255,.1);
      }
      .codex-mate-row:first-child { border-top: 0; }
      .codex-mate-row-title { font-weight: 550; }
      .codex-mate-row-description { margin-top: 3px; color: #a1a1aa; font-size: 12px; }
      .codex-mate-toggle {
        width: 42px;
        height: 24px;
        border: 0;
        border-radius: 999px;
        background: #52525b;
        padding: 2px;
      }
      .codex-mate-toggle span {
        display: block;
        width: 20px;
        height: 20px;
        border-radius: 999px;
        background: white;
        transition: transform .12s ease;
      }
      .codex-mate-toggle[data-enabled="true"] { background: #10a37f; }
      .codex-mate-toggle[data-enabled="true"] span { transform: translateX(18px); }
      .codex-mate-about { color: #a1a1aa; line-height: 1.5; }
    `;
    document.documentElement.appendChild(style);
  }

  function defaultCodexMateSettings() {
    return { pluginEntryUnlock: true, forcePluginInstall: true, sessionDelete: true, nativeMenuPlacement: true };
  }

  function codexMateSettings() {
    try {
      return { ...defaultCodexMateSettings(), ...JSON.parse(localStorage.getItem(codexMateSettingsKey) || "{}") };
    } catch {
      return defaultCodexMateSettings();
    }
  }

  function setCodexMateSetting(key, value) {
    const next = { ...codexMateSettings(), [key]: value };
    localStorage.setItem(codexMateSettingsKey, JSON.stringify(next));
    renderCodexMateMenu();
    scan();
  }

  function renderCodexMateMenu() {
    document.querySelectorAll(".codex-mate-toggle[data-codex-mate-setting]").forEach((button) => {
      const key = button.getAttribute("data-codex-mate-setting");
      button.dataset.enabled = String(!!codexMateSettings()[key]);
    });
  }

  function openCodexMateModal() {
    document.querySelectorAll(".codex-mate-modal-overlay").forEach((node) => node.remove());
    document.querySelectorAll('[data-codex-mate-dialog="true"]').forEach((node) => node.remove());
    const overlay = document.createElement("div");
    overlay.className = "codex-mate-modal-overlay";
    overlay.innerHTML = `
      <div class="codex-mate-modal-content" role="dialog" aria-modal="true" aria-label="Codex Mate">
        <div class="codex-mate-modal-header">
          <div class="codex-mate-modal-title">Codex Mate ${codexMateVersion}</div>
          <button type="button" class="codex-mate-modal-close" aria-label="关闭">×</button>
        </div>
        <div class="codex-mate-modal-body">
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">插件选项解锁</div><div class="codex-mate-row-description">让 API Key 模式显示并启用插件入口。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="pluginEntryUnlock"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">特殊插件强制安装</div><div class="codex-mate-row-description">解除 App unavailable / 应用不可用导致的前端安装禁用。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="forcePluginInstall"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">会话删除</div><div class="codex-mate-row-description">在会话列表悬停显示删除按钮，并支持撤销。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="sessionDelete"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">原生菜单栏位置</div><div class="codex-mate-row-description">把 Codex Mate 菜单插入顶部原生菜单栏；默认关闭以避免页面重渲染冲突。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="nativeMenuPlacement"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">关于 Codex Mate</div><div class="codex-mate-about">Codex Mate 是通过外部 launcher 注入的增强菜单，不修改 Codex App 原始安装文件。<br>GitHub: <a href="https://github.com/serein431/Codex-Mate" target="_blank" rel="noreferrer">https://github.com/serein431/Codex-Mate</a></div></div>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">提出问题</div><div class="codex-mate-row-description">打开 GitHub Issues 反馈问题或建议。</div></div>
            <button type="button" class="codex-mate-issue-button" data-codex-mate-issue="true">提出问题</button>
          </div>
        </div>
      </div>
    `;
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.closest(".codex-mate-modal-close")) {
        overlay.remove();
        return;
      }
      const issueButton = event.target.closest("[data-codex-mate-issue]");
      if (issueButton) {
        const issueUrl = "https://github.com/serein431/Codex-Mate/issues";
        window.open(issueUrl, "_blank");
        return;
      }
      const toggle = event.target.closest("[data-codex-mate-setting]");
      if (!toggle) return;
      const key = toggle.getAttribute("data-codex-mate-setting");
      setCodexMateSetting(key, !codexMateSettings()[key]);
    }, true);
    document.body.appendChild(overlay);
    renderCodexMateMenu();
  }

  function findNativeMenuInsertionPoint() {
    if (!codexMateSettings().nativeMenuPlacement) return null;
    const header = document.querySelector(".app-header-tint");
    const menuBar = header?.querySelector(".flex.items-center.gap-0\\.5") || header?.querySelector('[class*="flex items-center gap-0.5"]');
    if (!menuBar) return null;
    const buttons = Array.from(menuBar.querySelectorAll("button")).filter((button) => !button.closest(`#${codexMateMenuId}`));
    return { parent: menuBar, before: buttons[buttons.length - 1]?.nextSibling || null, nativeButtonClass: buttons[buttons.length - 1]?.className || "" };
  }

  function removeDuplicateCodexMateMenus(keep) {
    const legacyMenuId = "codex-" + "plus-menu";
    const legacyMenuAttribute = "data-codex-" + "plus-menu";
    const legacyMenuName = "Codex" + "++";
    document.querySelectorAll(`#${codexMateMenuId}, [data-codex-mate-menu="true"], #${legacyMenuId}, [${legacyMenuAttribute}="true"]`).forEach((node) => {
      if (node !== keep) node.remove();
    });
    Array.from(document.querySelectorAll("button")).forEach((button) => {
      const label = (button.textContent || "").trim();
      if ((label === `Codex Mate ${codexMateVersion}` || label.startsWith(legacyMenuName)) && !button.closest(`#${codexMateMenuId}`)) {
        button.remove();
      }
    });
  }

  function configureCodexMateTrigger(menu, trigger, nativeButtonClass) {
    if (!trigger) return;
    if (nativeButtonClass) trigger.className = nativeButtonClass;
    if (trigger.dataset.codexMateTriggerInstalled === "5") return;
    trigger.dataset.codexMateTriggerInstalled = "5";
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openCodexMateModal();
    }, true);
  }

  function installCodexMateMenu() {
    const existing = document.getElementById(codexMateMenuId);
    removeDuplicateCodexMateMenus(existing);
    let insertionPoint = findNativeMenuInsertionPoint();
    if (existing && existing.dataset.codexMateMenuVersion !== "5") {
      existing.remove();
      insertionPoint = findNativeMenuInsertionPoint();
    } else if (existing && insertionPoint && existing.parentElement === insertionPoint.parent) {
      configureCodexMateTrigger(existing, existing.querySelector("button"), insertionPoint.nativeButtonClass);
      removeDuplicateCodexMateMenus(existing);
      return;
    }
    const menu = document.createElement("div");
    menu.id = codexMateMenuId;
    menu.dataset.codexMateMenu = "true";
    menu.dataset.codexMateMenuVersion = "5";
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.textContent = `Codex Mate ${codexMateVersion}`;
    const nativeButtonClass = insertionPoint?.nativeButtonClass || "codex-mate-trigger";
    configureCodexMateTrigger(menu, trigger, nativeButtonClass);
    menu.appendChild(trigger);
    if (insertionPoint) {
      menu.className = "";
      const safeBefore = insertionPoint.before?.parentElement === insertionPoint.parent ? insertionPoint.before : null;
      insertionPoint.parent.insertBefore(menu, safeBefore);
    } else {
      menu.className = "codex-mate-menu-floating";
      document.documentElement.appendChild(menu);
    }
    removeDuplicateCodexMateMenus(menu);
  }

  function reactFiberFrom(element) {
    const fiberKey = Object.keys(element).find((key) => key.startsWith("__reactFiber"));
    return fiberKey ? element[fiberKey] : null;
  }

  function authContextValueFrom(element) {
    for (let fiber = reactFiberFrom(element); fiber; fiber = fiber.return) {
      for (const value of [fiber.memoizedProps?.value, fiber.pendingProps?.value]) {
        if (value && typeof value === "object" && typeof value.setAuthMethod === "function" && "authMethod" in value) {
          return value;
        }
      }
    }
    return null;
  }

  function spoofChatGPTAuthMethod(element) {
    const auth = authContextValueFrom(element);
    if (!auth || auth.authMethod === "chatgpt") return false;
    auth.setAuthMethod("chatgpt");
    return true;
  }

  function pluginEntryButton() {
    return document.querySelector('nav[role="navigation"] button.h-token-nav-row.w-full svg path[d^="M7.94562 14.0277"]')?.closest("button");
  }

  function labelUnlockedPluginEntry(button) {
    const labelTextNode = Array.from(button.querySelectorAll("span, div")).reverse()
      .flatMap((node) => Array.from(node.childNodes))
      .find((node) => node.nodeType === 3 && /^(插件|Plugins)( - 已解锁| - Unlocked)?$/i.test((node.nodeValue || "").trim()));
    if (!labelTextNode) return;
    const current = (labelTextNode.nodeValue || "").trim();
    labelTextNode.nodeValue = /^Plugins/i.test(current) ? "Plugins - Unlocked" : "插件 - 已解锁";
  }

  function enablePluginEntry() {
    if (!codexMateSettings().pluginEntryUnlock) return;
    const pluginButton = pluginEntryButton();
    if (!pluginButton) return;
    spoofChatGPTAuthMethod(pluginButton);
    pluginButton.disabled = false;
    pluginButton.removeAttribute("disabled");
    pluginButton.style.display = "";
    pluginButton.querySelectorAll("*").forEach((node) => {
      node.style.display = "";
    });
    labelUnlockedPluginEntry(pluginButton);
    const reactPropsKey = Object.keys(pluginButton).find((key) => key.startsWith("__reactProps"));
    if (reactPropsKey) {
      pluginButton[reactPropsKey].disabled = false;
    }
    if (pluginButton.dataset.codexPluginEnabled === "true") return;
    pluginButton.dataset.codexPluginEnabled = "true";
    pluginButton.addEventListener("click", () => {
      spoofChatGPTAuthMethod(pluginButton);
    }, true);
  }

  function pluginInstallCandidates() {
    return Array.from(document.querySelectorAll('button:disabled.w-full.justify-center, [role="button"][aria-disabled="true"].cursor-not-allowed'));
  }

  function installButtonLabel(element) {
    return (element.textContent || "").trim();
  }

  function unblockButtonElement(button) {
    button.disabled = false;
    button.removeAttribute("disabled");
    button.removeAttribute("aria-disabled");
    button.classList.remove("disabled", "opacity-50", "cursor-not-allowed", "pointer-events-none");
    button.style.pointerEvents = "auto";
    button.tabIndex = 0;
    const reactPropsKey = Object.keys(button).find((key) => key.startsWith("__reactProps"));
    if (reactPropsKey) {
      button[reactPropsKey].disabled = false;
      button[reactPropsKey]["aria-disabled"] = false;
    }
  }

  function labelForcedInstallButton(button) {
    const textNode = Array.from(button.childNodes).find((node) => node.nodeType === 3 && (/^安装\s/.test((node.nodeValue || "").trim()) || /^Install\s/.test((node.nodeValue || "").trim()) || (node.nodeValue || "").trim() === "强制安装"));
    if (textNode) {
      textNode.nodeValue = "强制安装";
    }
  }

  function unblockPluginInstallButtons() {
    if (!codexMateSettings().forcePluginInstall) return;
    pluginInstallCandidates().forEach((button) => {
      const text = installButtonLabel(button);
      if (!/^安装\s/.test(text) && !/^Install\s/.test(text) && text !== "强制安装") return;
      unblockButtonElement(button);
      labelForcedInstallButton(button);
    });
  }

  let cachedSessionRows = [];
  let cachedSessionRowsAt = 0;

  function sessionRows(forceRefresh = false) {
    const now = Date.now();
    if (!forceRefresh && now - cachedSessionRowsAt < 150) {
      cachedSessionRows = cachedSessionRows.filter((row) => row.isConnected);
      if (cachedSessionRows.length > 0) return cachedSessionRows;
    }

    cachedSessionRows = Array.from(document.querySelectorAll('[data-app-action-sidebar-thread-id]'));
    cachedSessionRowsAt = now;
    return cachedSessionRows;
  }

  function archivePageHintVisible() {
    if (window.location.href.includes("archive")) return true;
    if (document.querySelector('[data-codex-archive-page-row="true"], [data-codex-archive-delete-all]')) return true;
    const archiveNav = document.querySelector('button[aria-label="已归档对话"], button[aria-label="Archived conversations"]');
    if (archiveNav?.className?.includes?.("bg-token-list-hover-background")) return true;
    return !!Array.from(document.querySelectorAll("h1, h2, h3")).find((element) => (element.textContent || "").trim() === "已归档对话");
  }

  function archivedPageRows() {
    if (!archivePageHintVisible()) return [];
    const rows = Array.from(document.querySelectorAll("button")).filter((button) => (button.textContent || "").trim() === "取消归档").map((button) => button.closest(".flex.w-full.items-center.justify-between") || button.parentElement).filter(Boolean);
    rows.forEach((row) => {
      row.dataset.codexArchivePageRow = "true";
      row.setAttribute("data-codex-archive-page-row", "true");
    });
    return rows;
  }

  function archivedSessionRows() {
    if (!archivePageHintVisible()) return [];
    return sessionRows().filter((row) => row.querySelector('button[aria-label="取消归档对话"]') || row.outerHTML.includes("取消归档") || row.outerHTML.includes("unarchive"));
  }

  function archivedRows() {
    if (!archivePageHintVisible()) return [];
    return [...archivedSessionRows(), ...archivedPageRows()];
  }

  function archivedPageVisible() {
    return archivePageHintVisible() && archivedRows().length > 0;
  }

  function sessionRefFromRow(row) {
    const href = row.getAttribute("href") || row.querySelector("a")?.getAttribute("href") || "";
    const idMatch = href.match(/(?:session|conversation|thread)[=/:-]([A-Za-z0-9_.-]+)/i) || href.match(/([A-Za-z0-9_-]{8,})$/);
    const codexThreadId = row.getAttribute("data-app-action-sidebar-thread-id") || "";
    const fallbackId = row.getAttribute("data-session-id") || row.getAttribute("data-testid") || "";
    const sessionId = codexThreadId || (idMatch && idMatch[1]) || fallbackId;
    const titleNode = row.querySelector('[data-thread-title]');
    const title = ((titleNode || row).textContent || "Untitled session").replace("删除", "").trim().slice(0, 160);
    return { session_id: sessionId, title };
  }

  async function postJson(path, payload) {
    if (!window.__codexMateBridge) {
      return { status: "failed", message: "删除桥接不可用，请重启启动器" };
    }
    return await window.__codexMateBridge(path, payload);
  }

  function showToast(message, undoToken) {
    document.querySelectorAll(".codex-delete-toast").forEach((node) => node.remove());
    const toast = document.createElement("div");
    toast.className = "codex-delete-toast";
    toast.textContent = message;
    if (undoToken) {
      const undo = document.createElement("button");
      undo.textContent = "撤销";
      undo.addEventListener("click", async () => {
        const result = await postJson("/undo", { undo_token: undoToken });
        toast.textContent = result.message || "撤销完成";
        setTimeout(() => toast.remove(), 5000);
      });
      toast.appendChild(undo);
    }
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 10000);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function confirmDelete(title) {
    document.querySelectorAll(".codex-delete-confirm-overlay").forEach((node) => node.remove());
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "codex-delete-confirm-overlay";
      overlay.innerHTML = `
        <div class="codex-delete-confirm-content" role="dialog" aria-modal="true" aria-label="删除会话">
          <div class="codex-delete-confirm-title">删除会话</div>
          <div class="codex-delete-confirm-message">删除“${escapeHtml(title)}”？</div>
          <div class="codex-delete-confirm-actions">
            <button type="button" data-codex-delete-cancel="true">取消</button>
            <button type="button" data-codex-delete-confirm="true">删除</button>
          </div>
        </div>
      `;
      const finish = (value, event) => {
        event?.preventDefault();
        event?.stopPropagation();
        event?.target?.blur?.();
        overlay.remove();
        resolve(value);
      };
      overlay.addEventListener("click", (event) => {
        if (event.target === overlay || event.target.closest("[data-codex-delete-cancel]")) {
          finish(false, event);
          return;
        }
        if (event.target.closest("[data-codex-delete-confirm]")) {
          finish(true, event);
        }
      }, true);
      overlay.addEventListener("keydown", (event) => {
        if (event.key === "Escape") finish(false, event);
      }, true);
      document.body.appendChild(overlay);
      overlay.querySelector("[data-codex-delete-cancel]")?.focus();
    });
  }

  function rowHref(row) {
    return row.getAttribute("href") || row.querySelector("a")?.getAttribute("href") || "";
  }

  function isCurrentSessionRow(row, ref) {
    if (row.getAttribute("aria-current") === "page" || row.getAttribute("aria-current") === "true") return true;
    const href = rowHref(row);
    if (href) {
      try {
        const url = new URL(href, window.location.href);
        if (url.href === window.location.href || url.pathname === window.location.pathname) return true;
      } catch {
        if (window.location.href.includes(href)) return true;
      }
    }
    return !!ref.session_id && window.location.href.includes(ref.session_id);
  }

  function releaseDeleteFocus(row, button) {
    button.blur();
    if (row.contains(document.activeElement)) {
      document.activeElement.blur();
    }
  }

  function removeDeletedRow(row, button, ref) {
    releaseDeleteFocus(row, button);
    const shouldReload = isCurrentSessionRow(row, ref);
    row.remove();
    if (shouldReload) {
      window.location.reload();
    }
  }

  function updateDeleteButtonOffsets() {
    sessionRows().forEach((row) => {
      const hasArchiveConfirm = Array.from(row.querySelectorAll("button")).some((button) => {
        const rect = button.getBoundingClientRect();
        const label = button.getAttribute("aria-label") || "";
        const text = (button.textContent || "").trim();
        if (button.classList.contains(buttonClass) || label === "归档对话" || label === "置顶对话") return false;
        return text === "确认" || (text.length > 0 && rect.width > 0 && rect.width <= 36 && rect.x > row.getBoundingClientRect().right - 50);
      });
      row.classList.toggle("codex-archive-confirm-visible", hasArchiveConfirm);
    });
  }

  function openDeleteConfirmForRow(row, button, ref, event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation?.();
    releaseDeleteFocus(row, button);
    confirmDelete(ref.title).then(async (confirmed) => {
      if (!confirmed) return;
      releaseDeleteFocus(row, button);
      const result = await postJson("/delete", ref);
      if (result.status === "server_deleted" || result.status === "local_deleted") {
        removeDeletedRow(row, button, ref);
        showToast(result.message || "删除成功", result.undo_token);
      } else {
        showToast(result.message || "删除失败", null);
      }
    });
  }

  function installDeleteButtonEventDelegation() {
    document.removeEventListener("pointerup", window.__codexMateDocumentDeleteHandler, true);
    document.removeEventListener("click", window.__codexMateDocumentDeleteHandler, true);
    const handler = (event) => {
      const button = event.target?.closest?.(`.${buttonClass}`);
      const row = button?.closest?.("[data-app-action-sidebar-thread-id]");
      if (!button || !row) return;
      const ref = sessionRefFromRow(row);
      if (!ref.session_id) return;
      openDeleteConfirmForRow(row, button, ref, event);
    };
    window.__codexMateDocumentDeleteHandler = handler;
    document.addEventListener("pointerup", handler, true);
    document.addEventListener("click", handler, true);
  }

  function attachButton(row) {
    if (!codexMateSettings().sessionDelete) return;
    const existingDeleteButtons = Array.from(row.querySelectorAll(`.${buttonClass}`));
    if (existingDeleteButtons.length === 1 && existingDeleteButtons[0].dataset.codexDeleteVersion === codexDeleteVersion) return;
    existingDeleteButtons.forEach((button) => button.remove());
    row.dataset.codexDeleteRow = "false";
    const ref = sessionRefFromRow(row);
    if (!ref.session_id) return;
    row.dataset.codexDeleteRow = "true";
    const button = document.createElement("button");
    button.type = "button";
    button.className = buttonClass;
    button.dataset.codexDeleteVersion = codexDeleteVersion;
    button.setAttribute("aria-label", "删除会话");
    button.title = "删除会话";
    button.textContent = "删除";
    const stopDeleteButtonEvent = (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      releaseDeleteFocus(row, button);
    };
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      button.addEventListener(eventName, stopDeleteButtonEvent, true);
    });
    const openDeleteConfirm = (event) => openDeleteConfirmForRow(row, button, ref, event);
    button.addEventListener("pointerup", openDeleteConfirm, true);
    button.addEventListener("click", openDeleteConfirm, true);
    row.appendChild(button);
    const refreshDeleteButton = (originalButton) => {
      if (!originalButton.isConnected) return;
      const replacement = originalButton.cloneNode(true);
      ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
        replacement.addEventListener(eventName, stopDeleteButtonEvent, true);
      });
      replacement.addEventListener("pointerup", openDeleteConfirm, true);
      replacement.addEventListener("click", openDeleteConfirm, true);
      originalButton.replaceWith(replacement);
    };
    setTimeout(() => refreshDeleteButton(button), 0);
  }

  function tryAttachButton(row) {
    try {
      attachButton(row);
    } catch (error) {
      window.__codexMateAttachButtonFailures = window.__codexMateAttachButtonFailures || [];
      window.__codexMateAttachButtonFailures.push(String(error?.stack || error));
    }
  }

  function reactArchivedThreadFromNode(node) {
    const reactKey = Object.keys(node).find((key) => key.startsWith("__reactFiber$") || key.startsWith("__reactInternalInstance$"));
    let fiber = reactKey ? node[reactKey] : null;
    for (let depth = 0; fiber && depth < 20; depth += 1, fiber = fiber.return) {
      const props = fiber.memoizedProps || fiber.pendingProps || {};
      if (props.archivedThread?.id) return props.archivedThread;
      const childThread = props.children?.props?.archivedThread;
      if (childThread?.id) return childThread;
    }
    return null;
  }

  function archivedThreadFromRow(row) {
    for (const node of [row, ...row.querySelectorAll("*")]) {
      const thread = reactArchivedThreadFromNode(node);
      if (thread?.id || thread?.sessionId) return thread;
    }
    return null;
  }

  function archivedRefFromRow(row) {
    const archivedThread = archivedThreadFromRow(row);
    if (archivedThread?.id || archivedThread?.sessionId) {
      return { session_id: archivedThread.id || archivedThread.sessionId, title: archivedThread.title || row.querySelector(".truncate.text-base")?.textContent?.trim() || "Untitled session" };
    }
    const sidebarRef = sessionRefFromRow(row);
    if (sidebarRef.session_id) return sidebarRef;
    const titleNode = row.querySelector(".truncate.text-base, [data-thread-title], a, div");
    const title = ((titleNode || row).textContent || "Untitled session")
      .replace("取消归档", "")
      .replace("删除", "")
      .replace(/\d{4}年\d{1,2}月\d{1,2}日.*$/, "")
      .replace(/\s+·\s+.*$/, "")
      .trim()
      .slice(0, 160);
    return { session_id: "", title };
  }

  async function resolveArchivedThread(row) {
    const ref = archivedRefFromRow(row);
    if (ref.session_id) return ref;
    const resolved = await postJson("/archived-thread", { title: ref.title });
    return resolved?.session_id ? resolved : ref;
  }

  function stopArchivedButtonEvent(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation?.();
  }

  function archiveTitleContainer() {
    return Array.from(document.querySelectorAll("h1, h2, h3, div, span"))
      .find((element) => (element.textContent || "").trim() === "已归档对话" && element.getBoundingClientRect().x > 350);
  }

  async function deleteArchivedSessions(rows) {
    let deleted = 0;
    for (const row of rows) {
      const ref = await resolveArchivedThread(row);
      if (!ref.session_id) continue;
      const result = await postJson("/delete", ref);
      if (result.status === "server_deleted" || result.status === "local_deleted") {
        row.remove();
        deleted += 1;
      }
    }
    showToast(`已删除 ${deleted} 个归档会话`, null);
  }

  function attachArchivedPageDeleteButton(row) {
    if (!codexMateSettings().sessionDelete) return;
    if (row.dataset.codexArchiveDeleteRow === "true") return;
    row.dataset.codexArchiveDeleteRow = "true";
    const unarchiveButton = Array.from(row.querySelectorAll("button")).find((button) => (button.textContent || "").trim() === "取消归档");
    if (!unarchiveButton) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "codex-archive-delete-all";
    button.textContent = "删除";
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      button.addEventListener(eventName, stopArchivedButtonEvent, true);
    });
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      const ref = await resolveArchivedThread(row);
      if (!ref.session_id) {
        showToast("删除失败：未找到归档会话 ID", null);
        return;
      }
      if (!(await confirmDelete(ref.title))) return;
      const result = await postJson("/delete", ref);
      if (result.status === "server_deleted" || result.status === "local_deleted") {
        row.remove();
        showToast(result.message || "删除成功", result.undo_token);
      } else {
        showToast(result.message || "删除失败", null);
      }
    }, true);
    unarchiveButton.insertAdjacentElement("afterend", button);
  }

  function installArchivedDeleteAllButton() {
    const existingButton = document.querySelector("[data-codex-archive-delete-all]");
    if (!codexMateSettings().sessionDelete || !archivedPageVisible()) {
      existingButton?.remove();
      return;
    }
    const rows = archivedRows();
    if (rows.length === 0) {
      existingButton?.remove();
      return;
    }
    if (existingButton?.dataset.codexArchiveDeleteAllVersion === codexArchiveDeleteAllVersion) return;
    existingButton?.remove();
    const button = document.createElement("button");
    button.type = "button";
    button.className = "codex-archive-delete-all codex-archive-action-bar";
    Object.assign(button.style, {
      position: "static",
      marginLeft: "12px",
      verticalAlign: "middle",
      zIndex: "2147482999",
      cursor: "pointer",
      pointerEvents: "auto",
      maxWidth: "fit-content",
      alignSelf: "flex-start",
    });
    button.dataset.codexArchiveDeleteAll = "true";
    button.dataset.codexArchiveDeleteAllVersion = codexArchiveDeleteAllVersion;
    button.textContent = "删除全部归档";
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      button.addEventListener(eventName, stopArchivedButtonEvent, true);
    });
    const openArchivedDeleteAllConfirm = async (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      const currentRows = archivedRows();
      if (currentRows.length === 0) return;
      if (!(await confirmDelete(`全部 ${currentRows.length} 个归档会话`))) return;
      await deleteArchivedSessions(currentRows);
    };
    button.addEventListener("pointerup", openArchivedDeleteAllConfirm, true);
    button.addEventListener("click", openArchivedDeleteAllConfirm, true);
    const title = archiveTitleContainer();
    if (title) {
      title.insertAdjacentElement("afterend", button);
    } else {
      document.body.appendChild(button);
    }
  }

  function scanLightweight() {
    installStyle();
    installCodexMateMenu();
    installDeleteButtonEventDelegation();
  }

  function scanDeferred() {
    enablePluginEntry();
    unblockPluginInstallButtons();
    sessionRows().forEach(tryAttachButton);
    updateDeleteButtonOffsets();
    archivedPageRows().forEach(attachArchivedPageDeleteButton);
    installArchivedDeleteAllButton();
  }

  function runScanStep(step) {
    try {
      step();
    } catch (error) {
      window.__codexMateScanFailures = window.__codexMateScanFailures || [];
      window.__codexMateScanFailures.push(String(error?.stack || error));
    }
  }

  function scan() {
    runScanStep(scanLightweight);
    requestAnimationFrame(() => runScanStep(scanDeferred));
  }

  function isExtensionUiNode(node) {
    return !!node?.closest?.(".codex-delete-toast, .codex-delete-confirm-overlay, .codex-mate-modal-overlay, #codex-mate-menu");
  }

  const scanRelevantSelector = '[data-app-action-sidebar-thread-id], [data-codex-archive-page-row="true"], [data-codex-archive-delete-all], .app-header-tint, button[aria-label="已归档对话"], button[aria-label="Archived conversations"], button:disabled.w-full.justify-center, [role="button"][aria-disabled="true"].cursor-not-allowed';

  function isScanRelevantNode(node) {
    if (node.nodeType !== 1) return false;
    if (isExtensionUiNode(node)) return false;
    return !!node.matches?.(scanRelevantSelector) || !!node.closest?.(scanRelevantSelector) || !!node.querySelector?.(scanRelevantSelector);
  }

  function isChatContentMutation(mutation) {
    const target = mutation.target;
    if (target?.closest?.('[data-message-author-role], [data-testid="conversation-turn"], main .prose')) {
      return !Array.from(mutation.addedNodes).some(isScanRelevantNode) && !Array.from(mutation.removedNodes).some(isScanRelevantNode);
    }
    return false;
  }

  function shouldScheduleScan(mutations) {
    if (!mutations) return true;
    return mutations.some((mutation) => {
      if (isChatContentMutation(mutation)) return false;
      const target = mutation.target;
      if (isExtensionUiNode(target)) return false;
      return Array.from(mutation.addedNodes).some((node) => node.nodeType === 1 && !isExtensionUiNode(node)) || Array.from(mutation.removedNodes).some((node) => node.nodeType === 1);
    });
  }

  function runScheduledScan() {
    window.__codexMateScanPending = false;
    clearTimeout(window.__codexMateScanTimer);
    window.__codexMateScanTimer = null;
    scan();
  }

  function scheduleScan(mutations) {
    if (!shouldScheduleScan(mutations)) return;
    if (window.__codexMateScanPending) return;
    window.__codexMateScanPending = true;
    window.__codexMateScanTimer = setTimeout(runScheduledScan, 200);
  }

  scan();
  window.__codexMateObserver?.disconnect();
  window.__codexMateObserver = new MutationObserver(scheduleScan);
  window.__codexMateObserver.observe(document.body || document.documentElement, { childList: true, subtree: true });
})();
