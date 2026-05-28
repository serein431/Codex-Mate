(() => {
  const helperBase = window.__CODEX_MATE_HELPER__ || "http://127.0.0.1:57321";
  const buttonClass = "codex-delete-button";
  const exportButtonClass = "codex-export-button";
  const projectMoveButtonClass = "codex-project-move-button";
  const projectMoveOverlayClass = "codex-project-move-overlay";
  const actionButtonClass = "codex-session-action-button";
  const actionGroupClass = "codex-session-actions";
  const actionTooltipClass = "codex-session-action-tooltip";
  const timelineClass = "codex-conversation-timeline";
  const timelineTrackClass = "codex-conversation-timeline-track";
  const timelineMarkerClass = "codex-conversation-timeline-marker";
  const timelineTooltipClass = "codex-conversation-timeline-tooltip";
  const timelineTargetClass = "codex-conversation-timeline-target";
  const timelineQuestionLimit = 40;
  const timelineMinTopPercent = 2;
  const timelineMaxTopPercent = 98;
  const timelineMaxMarkerGapPercent = 3.5;
  const styleId = "codex-delete-style";
  const codexDeleteStyleVersion = "13";
  const codexMateMenuId = "codex-mate-menu";
  const codexDeleteVersion = "6";
  const codexExportVersion = "1";
  const codexProjectMoveVersion = "1";
  const codexActionGroupVersion = "2";
  const codexArchiveDeleteAllVersion = "2";
  const projectMoveProjectionKey = "codexMateProjectMoveProjection";
  const projectMoveProjectionTtlMs = 7 * 24 * 60 * 60 * 1000;
  const projectMoveProjectionSettleMs = 2500;
  const projectMoveRefreshDelaysMs = [80, 250, 700, 1500, 3000];
  const chatsSortRefreshIntervalMs = 5000;
  const chatsSortDbRefreshIntervalMs = 20000;
  const codexMateVersion = window.__CODEX_MATE_VERSION__ || "dev";
  const codexMateSettingsKey = "codexMateSettings";
  const codexMateMenuVersion = "23";
  const codexMateTriggerInstalled = "23";
  const codexConversationTimelineVersion = "1";
  const codexThreadScrollVersion = "1";
  const codexThreadScrollKey = "codexMateThreadScroll";
  const codexThreadScrollMaxEntries = 120;
  const codexThreadScrollSaveThrottleMs = 120;
  const codexThreadScrollRestoreDelaysMs = [0, 80, 220, 500, 1000, 1800];
  const codexThreadScrollUserIntentWindowMs = 1200;
  const codexThreadScrollListenerVersion = "1";
  const codexThreadScrollRouteHooksVersion = "1";
  const codexThreadScrollUserIntentVersion = "1";
  const codexProjectMoveRuntimeId = `${Date.now()}-${Math.random()}`;
  window.__codexProjectMoveRuntimeId = codexProjectMoveRuntimeId;
  clearTimeout(window.__codexProjectMoveProjectionTimer);
  window.__codexProjectMoveProjectionTimer = null;
  clearTimeout(window.__codexProjectMoveChatsSortTimer);
  window.__codexProjectMoveChatsSortTimer = null;
  let chatsSortInFlight = false;
  let chatsSortSignature = "";
  let chatsSortLastFetchAt = 0;
  clearTimeout(window.__codexMateThreadScrollSaveTimer);
  window.__codexMateThreadScrollSaveTimer = null;
  (window.__codexMateThreadScrollRestoreTimers || []).forEach((timer) => clearTimeout(timer));
  window.__codexMateThreadScrollRestoreTimers = [];
  window.__codexConversationTimelineNodeCounter = window.__codexConversationTimelineNodeCounter || 0;

  function closestElement(target, selector) {
    const element = target?.nodeType === 1 ? target : target?.parentElement;
    return element?.closest?.(selector) || null;
  }

  function installStyle() {
    const existingStyle = document.getElementById(styleId);
    if (existingStyle?.dataset.codexDeleteStyleVersion === codexDeleteStyleVersion) return;
    existingStyle?.remove();
    const style = document.createElement("style");
    style.id = styleId;
    style.dataset.codexDeleteStyleVersion = codexDeleteStyleVersion;
    style.textContent = `
      :root {
        --codex-mate-action-color: hsl(240 3.8% 46.1%);
        --codex-mate-action-hover-color: hsl(240 10% 3.9%);
        --codex-mate-action-hover-bg: hsl(240 4.8% 95.9%);
        --codex-mate-popover-bg: hsl(0 0% 100%);
        --codex-mate-popover-fg: hsl(240 10% 3.9%);
        --codex-mate-popover-muted: hsl(240 3.8% 46.1%);
        --codex-mate-popover-border: hsl(240 5.9% 88%);
        --codex-mate-popover-shadow: hsl(240 10% 3.9% / .16);
        --codex-mate-overlay-bg: hsl(240 10% 3.9% / .24);
        --codex-mate-card-bg: hsl(240 4.8% 96.8%);
        --codex-mate-control-bg: hsl(240 4.8% 95.9%);
        --codex-mate-control-hover-bg: hsl(240 5.9% 90%);
        --codex-mate-input-bg: hsl(0 0% 100%);
        --codex-mate-input-fg: hsl(240 10% 3.9%);
        --codex-mate-input-border: hsl(240 5.9% 82%);
        --codex-mate-toggle-bg: hsl(240 5.9% 84%);
        --codex-mate-success: hsl(166 72% 36%);
        --codex-mate-success-soft: hsl(166 72% 36% / .12);
        --codex-mate-success-border: hsl(166 72% 36% / .55);
        --codex-mate-status-ok: hsl(166 72% 36%);
        --codex-mate-status-failed: hsl(0 72% 50%);
        --codex-mate-status-checking: hsl(38 92% 42%);
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --codex-mate-action-color: hsl(240 5% 64.9%);
          --codex-mate-action-hover-color: hsl(0 0% 98%);
          --codex-mate-action-hover-bg: hsl(240 3.7% 15.9%);
          --codex-mate-popover-bg: hsl(240 10% 3.9%);
          --codex-mate-popover-fg: hsl(0 0% 98%);
          --codex-mate-popover-muted: hsl(240 5% 64.9%);
          --codex-mate-popover-border: hsl(240 3.7% 18%);
          --codex-mate-popover-shadow: hsl(0 0% 0% / .45);
          --codex-mate-overlay-bg: hsl(0 0% 0% / .45);
          --codex-mate-card-bg: hsl(240 3.7% 13%);
          --codex-mate-control-bg: hsl(240 3.7% 15.9%);
          --codex-mate-control-hover-bg: hsl(240 3.7% 20%);
          --codex-mate-input-bg: hsl(240 3.7% 15.9%);
          --codex-mate-input-fg: hsl(0 0% 98%);
          --codex-mate-input-border: hsl(240 3.7% 23%);
          --codex-mate-toggle-bg: hsl(240 3.7% 24%);
          --codex-mate-success: hsl(158 64% 52%);
          --codex-mate-success-soft: hsl(158 64% 52% / .16);
          --codex-mate-success-border: hsl(158 64% 52% / .55);
          --codex-mate-status-ok: hsl(158 64% 52%);
          --codex-mate-status-failed: hsl(0 91% 71%);
          --codex-mate-status-checking: hsl(43 96% 56%);
        }
      }
      :where(html.electron-light, body.electron-light, html.light, body.light, html[data-theme="light"], body[data-theme="light"], html[data-color-mode="light"], body[data-color-mode="light"]) {
        --codex-mate-action-color: hsl(240 3.8% 46.1%);
        --codex-mate-action-hover-color: hsl(240 10% 3.9%);
        --codex-mate-action-hover-bg: hsl(240 4.8% 95.9%);
        --codex-mate-popover-bg: hsl(0 0% 100%);
        --codex-mate-popover-fg: hsl(240 10% 3.9%);
        --codex-mate-popover-muted: hsl(240 3.8% 46.1%);
        --codex-mate-popover-border: hsl(240 5.9% 88%);
        --codex-mate-popover-shadow: hsl(240 10% 3.9% / .16);
        --codex-mate-overlay-bg: hsl(240 10% 3.9% / .24);
        --codex-mate-card-bg: hsl(240 4.8% 96.8%);
        --codex-mate-control-bg: hsl(240 4.8% 95.9%);
        --codex-mate-control-hover-bg: hsl(240 5.9% 90%);
        --codex-mate-input-bg: hsl(0 0% 100%);
        --codex-mate-input-fg: hsl(240 10% 3.9%);
        --codex-mate-input-border: hsl(240 5.9% 82%);
        --codex-mate-toggle-bg: hsl(240 5.9% 84%);
        --codex-mate-success: hsl(166 72% 36%);
        --codex-mate-success-soft: hsl(166 72% 36% / .12);
        --codex-mate-success-border: hsl(166 72% 36% / .55);
        --codex-mate-status-ok: hsl(166 72% 36%);
        --codex-mate-status-failed: hsl(0 72% 50%);
        --codex-mate-status-checking: hsl(38 92% 42%);
      }
      :where(html.electron-dark, body.electron-dark, html.dark, body.dark, html[data-theme="dark"], body[data-theme="dark"], html[data-color-mode="dark"], body[data-color-mode="dark"]) {
        --codex-mate-action-color: hsl(240 5% 64.9%);
        --codex-mate-action-hover-color: hsl(0 0% 98%);
        --codex-mate-action-hover-bg: hsl(240 3.7% 15.9%);
        --codex-mate-popover-bg: hsl(240 10% 3.9%);
        --codex-mate-popover-fg: hsl(0 0% 98%);
        --codex-mate-popover-muted: hsl(240 5% 64.9%);
        --codex-mate-popover-border: hsl(240 3.7% 18%);
        --codex-mate-popover-shadow: hsl(0 0% 0% / .45);
        --codex-mate-overlay-bg: hsl(0 0% 0% / .45);
        --codex-mate-card-bg: hsl(240 3.7% 13%);
        --codex-mate-control-bg: hsl(240 3.7% 15.9%);
        --codex-mate-control-hover-bg: hsl(240 3.7% 20%);
        --codex-mate-input-bg: hsl(240 3.7% 15.9%);
        --codex-mate-input-fg: hsl(0 0% 98%);
        --codex-mate-input-border: hsl(240 3.7% 23%);
        --codex-mate-toggle-bg: hsl(240 3.7% 24%);
        --codex-mate-success: hsl(158 64% 52%);
        --codex-mate-success-soft: hsl(158 64% 52% / .16);
        --codex-mate-success-border: hsl(158 64% 52% / .55);
        --codex-mate-status-ok: hsl(158 64% 52%);
        --codex-mate-status-failed: hsl(0 91% 71%);
        --codex-mate-status-checking: hsl(43 96% 56%);
      }
      .${actionGroupClass} {
        position: absolute;
        right: var(--codex-session-actions-right, 28px);
        top: 50%;
        transform: translateY(-50%);
        z-index: 20;
        opacity: 0;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: transparent;
        transition: opacity .12s ease;
        -webkit-app-region: no-drag;
      }
      .${actionButtonClass} {
        width: 26px;
        height: 26px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 6px;
        background: transparent;
        color: var(--codex-mate-action-color);
        font: 14px/1 system-ui, sans-serif;
        letter-spacing: 0;
        padding: 0;
        cursor: default;
        text-align: center;
        pointer-events: auto;
        -webkit-app-region: no-drag;
      }
      .${actionButtonClass} svg {
        display: block;
        width: 16px;
        height: 16px;
      }
      .${actionButtonClass}:hover,
      .${actionButtonClass}:focus-visible {
        background: var(--codex-mate-action-hover-bg);
        color: var(--codex-mate-action-hover-color);
        outline: none;
      }
      [data-codex-delete-row="true"]:hover .${actionGroupClass} { opacity: 1; }
      [data-codex-delete-row="true"]:hover [data-thread-title] {
        -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - var(--codex-session-title-mask, 86px)), transparent calc(100% - max(0px, var(--codex-session-title-mask, 86px) - 6px)));
        mask-image: linear-gradient(90deg, #000 calc(100% - var(--codex-session-title-mask, 86px)), transparent calc(100% - max(0px, var(--codex-session-title-mask, 86px) - 6px)));
      }
      [data-codex-delete-row="true"].codex-archive-confirm-visible .${actionGroupClass} {
        right: max(66px, var(--codex-session-actions-right, 28px));
      }
      .${actionTooltipClass} {
        position: fixed;
        z-index: 2147483201;
        max-width: min(220px, calc(100vw - 32px));
        border: 1px solid var(--codex-mate-popover-border);
        border-radius: 12px;
        background: var(--codex-mate-popover-bg);
        color: var(--codex-mate-popover-fg);
        font: 14px/20px system-ui, sans-serif;
        padding: 9px 12px;
        box-shadow: 0 14px 40px var(--codex-mate-popover-shadow);
        pointer-events: none;
        white-space: nowrap;
      }
      .${projectMoveOverlayClass} {
        position: fixed;
        inset: 0;
        z-index: 2147483200;
        background: transparent;
        pointer-events: auto;
        -webkit-app-region: no-drag;
      }
      .codex-project-move-panel {
        position: fixed;
        min-width: 260px;
        max-width: min(360px, calc(100vw - 24px));
        max-height: min(420px, calc(100vh - 24px));
        overflow: auto;
        border: 1px solid var(--codex-mate-popover-border);
        border-radius: 10px;
        background: var(--codex-mate-popover-bg);
        color: var(--codex-mate-popover-fg);
        box-shadow: 0 20px 50px var(--codex-mate-popover-shadow);
        padding: 8px;
        font: 13px/18px system-ui, sans-serif;
        letter-spacing: 0;
      }
      .codex-project-move-title {
        padding: 8px 9px 7px;
        color: var(--codex-mate-popover-fg);
        font-weight: 600;
      }
      .codex-project-move-item {
        width: 100%;
        min-height: 42px;
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 10px;
        border: 0;
        border-radius: 7px;
        background: transparent;
        color: inherit;
        padding: 8px 9px;
        text-align: left;
        cursor: default;
        letter-spacing: 0;
      }
      .codex-project-move-item:hover,
      .codex-project-move-item:focus-visible {
        background: var(--codex-mate-action-hover-bg);
        outline: none;
      }
      .codex-project-move-label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .codex-project-move-path {
        grid-column: 1 / -1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--codex-mate-popover-muted);
        font-size: 12px;
      }
      .codex-project-move-current {
        color: var(--codex-mate-success);
        font-size: 12px;
      }
      .codex-project-move-empty {
        padding: 8px 9px;
        color: var(--codex-mate-popover-muted);
      }
      .codex-project-move-hidden {
        display: none !important;
      }
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
      .codex-archive-export {
        border-color: #93c5fd;
        background: #dbeafe;
        color: #1d4ed8;
        margin-left: 6px;
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
        top: 8px;
        right: 196px;
        left: auto;
        z-index: 2147483645;
        height: 30px;
        color: var(--codex-mate-action-color);
        font: 13px system-ui, sans-serif;
        text-align: right;
        pointer-events: auto;
        -webkit-app-region: no-drag;
      }
      #${codexMateMenuId} {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        height: 100%;
        flex: 0 0 auto;
        pointer-events: auto;
        position: relative;
        z-index: 2147483645;
        isolation: isolate;
        -webkit-app-region: no-drag;
      }
      .codex-mate-toolbar-button {
        border: 1px solid transparent;
        background: transparent;
        color: inherit;
        font: inherit;
        width: 28px;
        min-width: 28px;
        height: 28px;
        padding: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        letter-spacing: 0;
        box-shadow: none;
        cursor: pointer;
        pointer-events: auto;
        position: relative;
        z-index: 1;
        -webkit-app-region: no-drag;
      }
      .codex-mate-toolbar-button:hover,
      .codex-mate-toolbar-button:focus-visible {
        background: var(--codex-mate-action-hover-bg);
        border-color: var(--codex-mate-popover-border);
      }
      .codex-mate-toolbar-button:focus-visible {
        outline: none;
      }
      .codex-mate-trigger {
        font-size: 11px;
        font-weight: 650;
        line-height: 1;
      }
      .codex-mate-trigger[data-codex-mate-compact="true"] {
        letter-spacing: 0;
      }
      .codex-mate-modal-overlay {
        position: fixed;
        inset: 0;
        z-index: 2147483646;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--codex-mate-overlay-bg);
      }
              .codex-mate-modal-content {
                width: min(520px, calc(100vw - 48px));
                max-height: min(760px, calc(100vh - 32px));
                display: flex;
                flex-direction: column;
                overflow: hidden;
                border: 1px solid var(--codex-mate-popover-border);
                border-radius: 18px;
                background: var(--codex-mate-popover-bg);
                color: var(--codex-mate-popover-fg);
                color-scheme: light;
                font: 14px system-ui, sans-serif;
                box-shadow: 0 24px 80px var(--codex-mate-popover-shadow);
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
        color: var(--codex-mate-popover-muted);
        font-size: 20px;
        cursor: pointer;
        -webkit-app-region: no-drag;
      }
      .codex-mate-modal-close:hover,
      .codex-mate-modal-close:focus-visible {
        color: var(--codex-mate-popover-fg);
        outline: none;
      }
      .codex-mate-modal-body {
        padding: 8px 20px 20px;
        overflow-y: auto;
      }
      .codex-mate-mode-row {
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
        padding: 0 0 14px;
      }
      .codex-mate-mode-header {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
      }
      .codex-mate-mode-title { font-weight: 650; }
              .codex-mate-mode-description { color: var(--codex-mate-popover-muted); font-size: 12px; line-height: 1.45; }
              .codex-mate-mode-status { color: var(--codex-mate-popover-muted); font-size: 12px; line-height: 1.45; }
      .codex-mate-mode-status[data-status="ok"] { color: var(--codex-mate-status-ok); }
      .codex-mate-mode-status[data-status="failed"] { color: var(--codex-mate-status-failed); }
      .codex-mate-mode-status[data-status="checking"],
      .codex-mate-mode-status[data-status="saving"] { color: var(--codex-mate-status-checking); }
      .codex-mate-auth-card {
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 12px;
                border: 1px solid var(--codex-mate-popover-border);
                border-radius: 10px;
                background: var(--codex-mate-card-bg);
                padding: 11px 12px;
              }
              .codex-mate-auth-summary {
                color: var(--codex-mate-popover-fg);
                font-size: 13px;
                font-weight: 650;
                line-height: 18px;
              }
              .codex-mate-auth-detail {
                margin-top: 3px;
                color: var(--codex-mate-popover-muted);
                font-size: 12px;
                line-height: 1.45;
              }
      .codex-mate-mode-switch {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px;
        padding: 4px;
                border: 1px solid var(--codex-mate-popover-border);
                border-radius: 10px;
                background: var(--codex-mate-control-bg);
              }
              .codex-mate-mode-option {
                min-height: 58px;
                border: 1px solid var(--codex-mate-popover-border);
                border-radius: 7px;
                background: var(--codex-mate-popover-bg);
                color: var(--codex-mate-popover-muted);
                font: 12px system-ui, sans-serif;
                letter-spacing: 0;
                cursor: pointer;
                text-align: left;
                padding: 8px 10px;
              }
              .codex-mate-mode-option strong { display: block; color: var(--codex-mate-popover-fg); font-size: 13px; line-height: 18px; }
              .codex-mate-mode-option span { display: block; margin-top: 2px; color: var(--codex-mate-popover-muted); line-height: 16px; }
      .codex-mate-mode-option[data-active="true"] {
        border-color: var(--codex-mate-success-border);
        background: var(--codex-mate-success-soft);
      }
      .codex-mate-mode-option:disabled {
        opacity: .62;
        cursor: default;
      }
      .codex-mate-provider-form {
        display: grid;
        gap: 12px;
      }
      .codex-mate-provider-modes {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
      }
      .codex-mate-provider-mode {
        min-height: 50px;
        border: 1px solid var(--codex-mate-popover-border);
        border-radius: 8px;
        background: transparent;
        color: var(--codex-mate-popover-fg);
        padding: 8px;
        font: 12px/16px system-ui, sans-serif;
        text-align: left;
        cursor: pointer;
        letter-spacing: 0;
      }
      .codex-mate-provider-mode[data-active="true"] {
        border-color: var(--codex-mate-success);
        background: var(--codex-mate-success-soft);
      }
      .codex-mate-provider-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
      .codex-mate-provider-field {
        display: grid;
        gap: 5px;
      }
      .codex-mate-provider-field span {
        color: var(--codex-mate-popover-muted);
        font-size: 12px;
      }
      .codex-mate-provider-field input,
      .codex-mate-provider-field select {
        width: 100%;
        min-height: 34px;
        border: 1px solid var(--codex-mate-input-border);
        border-radius: 7px;
        background: var(--codex-mate-input-bg);
        color: var(--codex-mate-input-fg);
        color-scheme: light;
        padding: 6px 8px;
        font: 13px/18px system-ui, sans-serif;
        letter-spacing: 0;
      }
      .codex-mate-provider-field[data-disabled="true"] {
        opacity: .55;
      }
      .codex-mate-provider-field[data-disabled="true"] input,
      .codex-mate-provider-field[data-disabled="true"] select {
        pointer-events: none;
      }
      .codex-mate-provider-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .codex-mate-provider-status {
        color: var(--codex-mate-popover-muted);
        font-size: 12px;
        line-height: 1.45;
      }
      .codex-mate-provider-status[data-status="ok"] { color: var(--codex-mate-status-ok); }
      .codex-mate-provider-status[data-status="failed"] { color: var(--codex-mate-status-failed); }
      .codex-mate-provider-status[data-status="checking"],
      .codex-mate-provider-status[data-status="saving"] { color: var(--codex-mate-status-checking); }
      @media (max-width: 560px) {
        .codex-mate-provider-modes,
        .codex-mate-provider-grid {
          grid-template-columns: 1fr;
        }
      }
              .codex-mate-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                padding: 12px 0;
                border-top: 1px solid var(--codex-mate-popover-border);
              }
              .codex-mate-row:first-child { border-top: 0; }
              .codex-mate-row-title { font-weight: 550; }
              .codex-mate-row-description { margin-top: 3px; color: var(--codex-mate-popover-muted); font-size: 12px; }
              .codex-mate-toggle {
                width: 42px;
                height: 24px;
                border: 0;
                border-radius: 999px;
                background: var(--codex-mate-toggle-bg);
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
      .codex-mate-toggle[data-enabled="true"] { background: var(--codex-mate-success); }
      .codex-mate-toggle[data-enabled="true"] span { transform: translateX(18px); }
              .codex-mate-about { color: var(--codex-mate-popover-muted); line-height: 1.5; }
      .codex-mate-actions {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        flex: 0 0 auto;
      }
      .codex-mate-action-button {
                border: 1px solid var(--codex-mate-popover-border);
                border-radius: 7px;
                background: var(--codex-mate-control-bg);
                color: var(--codex-mate-popover-fg);
        font: 13px system-ui, sans-serif;
        line-height: 18px;
        padding: 6px 10px;
        cursor: pointer;
        white-space: nowrap;
      }
      .codex-mate-action-button:hover,
      .codex-mate-action-button:focus-visible {
        border-color: var(--codex-mate-success-border);
        background: var(--codex-mate-success-soft);
      }
      .codex-mate-action-button:disabled {
        opacity: .5;
        cursor: default;
      }
      .codex-mate-backend-indicator {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: #a1a1aa;
        display: inline-block;
        margin-right: 8px;
      }
      .codex-mate-backend-indicator[data-status="ok"] {
        background: var(--codex-mate-status-ok);
        box-shadow: 0 0 8px rgba(52,211,153,.75);
      }
      .codex-mate-backend-indicator[data-status="failed"] {
        background: var(--codex-mate-status-failed);
        box-shadow: 0 0 8px rgba(239,68,68,.75);
      }
      .codex-mate-backend-indicator[data-status="checking"] { background: var(--codex-mate-status-checking); }
              .codex-mate-backend-label { color: var(--codex-mate-popover-muted); font-size: 12px; }
      .codex-mate-backend-label[data-status="ok"] { color: var(--codex-mate-status-ok); }
      .codex-mate-backend-label[data-status="failed"] { color: var(--codex-mate-status-failed); }
      :where(html.electron-dark, body.electron-dark, html.dark, body.dark, html[data-theme="dark"], body[data-theme="dark"], html[data-color-mode="dark"], body[data-color-mode="dark"]) .codex-mate-modal-content,
      :where(html.electron-dark, body.electron-dark, html.dark, body.dark, html[data-theme="dark"], body[data-theme="dark"], html[data-color-mode="dark"], body[data-color-mode="dark"]) .codex-mate-provider-field input,
      :where(html.electron-dark, body.electron-dark, html.dark, body.dark, html[data-theme="dark"], body[data-theme="dark"], html[data-color-mode="dark"], body[data-color-mode="dark"]) .codex-mate-provider-field select {
        color-scheme: dark;
      }
      .${timelineClass} {
        position: fixed;
        top: calc(72px + 12px);
        right: 12px;
        bottom: calc(28px + 12px);
        width: 24px;
        z-index: 2147482500;
        pointer-events: none;
      }
      .${timelineTrackClass} {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 50%;
        width: 2px;
        transform: translateX(-50%);
        border-radius: 999px;
        background: rgba(209, 213, 219, .55);
      }
      .${timelineMarkerClass} {
        position: absolute;
        left: 50%;
        width: 12px;
        height: 12px;
        border: 0;
        border-radius: 999px;
        transform: translate(-50%, -50%);
        background: #d1d5db;
        cursor: pointer;
        pointer-events: auto;
        box-shadow: 0 0 0 2px rgba(255,255,255,.92);
      }
      .${timelineMarkerClass}:hover,
      .${timelineMarkerClass}:focus-visible,
      .${timelineMarkerClass}.codex-conversation-timeline-marker-active {
        background: #8b8b8b;
        outline: none;
      }
      .${timelineTooltipClass} {
        position: absolute;
        top: 50%;
        right: 18px;
        transform: translateY(-50%);
        max-width: min(280px, calc(100vw - 72px));
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 10px;
        background: var(--codex-mate-popover-bg);
        color: var(--codex-mate-popover-fg);
        font: 12px/16px system-ui, sans-serif;
        padding: 7px 9px;
        box-shadow: 0 14px 40px rgba(0,0,0,.28);
        opacity: 0;
        pointer-events: none;
        white-space: nowrap;
        transition: opacity .12s ease;
      }
      .${timelineMarkerClass}:hover .${timelineTooltipClass},
      .${timelineMarkerClass}:focus-visible .${timelineTooltipClass} { opacity: 1; }
      .${timelineTargetClass} {
        animation: codex-conversation-timeline-pulse 1.2s ease-out;
      }
      @keyframes codex-conversation-timeline-pulse {
        0% { box-shadow: 0 0 0 0 rgba(16,163,127,.42); }
        100% { box-shadow: 0 0 0 16px rgba(16,163,127,0); }
      }
    `;
    document.documentElement.appendChild(style);
  }

  function defaultCodexMateSettings() {
    return {
      authEnhancementMode: "forceInject",
      pluginEntryUnlock: true,
      forcePluginInstall: true,
      sessionDelete: true,
      markdownExport: true,
      projectMove: true,
      conversationTimeline: true,
      threadScrollRestore: true,
      nativeMenuPlacement: true,
    };
  }

  function normalizeCodexMateSettings(settings) {
    const hasExplicitMode = Object.prototype.hasOwnProperty.call(settings || {}, "authEnhancementMode");
    const mode = hasExplicitMode
      ? (settings?.authEnhancementMode === "loginPreserving" ? "loginPreserving" : "forceInject")
      : (settings?.pluginEntryUnlock === false && settings?.forcePluginInstall === false ? "loginPreserving" : "forceInject");
    const next = { ...defaultCodexMateSettings(), ...(settings || {}), authEnhancementMode: mode };
    if (mode === "loginPreserving") {
      next.pluginEntryUnlock = false;
      next.forcePluginInstall = false;
    } else {
      next.pluginEntryUnlock = true;
      next.forcePluginInstall = true;
    }
    return next;
  }

  function codexMateSettings() {
    try {
      return normalizeCodexMateSettings(JSON.parse(localStorage.getItem(codexMateSettingsKey) || "{}"));
    } catch {
      return defaultCodexMateSettings();
    }
  }

  function setCodexMateSetting(key, value) {
    const next = normalizeCodexMateSettings({ ...codexMateSettings(), [key]: value });
    localStorage.setItem(codexMateSettingsKey, JSON.stringify(next));
    if (key === "threadScrollRestore" && !value) {
      clearTimeout(window.__codexMateThreadScrollSaveTimer);
      window.__codexMateThreadScrollSaveTimer = null;
      (window.__codexMateThreadScrollRestoreTimers || []).forEach((timer) => clearTimeout(timer));
      window.__codexMateThreadScrollRestoreTimers = [];
      window.__codexMateThreadScrollRuntime = null;
    }
    renderCodexMateMenu();
    scan();
  }

  function applyCodexMateAuthMode(mode) {
    const normalized = mode === "loginPreserving" ? "loginPreserving" : mode === "forceInject" ? "forceInject" : "";
    if (!normalized) return false;
    const next = normalizeCodexMateSettings({ ...codexMateSettings(), authEnhancementMode: normalized });
    localStorage.setItem(codexMateSettingsKey, JSON.stringify(next));
    return true;
  }

  function applyCodexMateAuthModePayload(payload) {
    return applyCodexMateAuthMode(payload?.auth_enhancement_mode || payload?.authEnhancementMode);
  }

  let codexMateAuthModeStatus = { status: "checking", message: "正在读取增强模式…" };
  let codexMateAuthModePayload = null;

  function renderAuthModeStatus() {
    const status = codexMateAuthModeStatus.status || "ok";
    const payload = codexMateAuthModePayload || {};
    const loginReady = payload.login_preserving_available === true || payload.provider_mode?.chatgpt_login_token_present === true;
    const currentMode = codexMateSettings().authEnhancementMode;
    document.querySelectorAll("[data-codex-mate-auth-mode-status]").forEach((node) => {
      node.dataset.status = status;
      node.textContent = codexMateAuthModeStatus.message || (status === "ok" ? "增强模式已同步" : "增强模式未同步");
    });
    document.querySelectorAll("[data-codex-mate-auth-summary]").forEach((node) => {
      node.textContent = payload.summary || (status === "checking" ? "正在检测 ChatGPT 登录" : "未检测到 ChatGPT 登录");
    });
    document.querySelectorAll("[data-codex-mate-auth-detail]").forEach((node) => {
      node.textContent = payload.detail || "Codex Mate 会先确认本机是否有 ChatGPT 登录态，再决定是否可以启用保留登录态。";
    });
    document.querySelectorAll("[data-codex-mate-auth-mode]").forEach((button) => {
      const mode = button.getAttribute("data-codex-mate-auth-mode");
      const waiting = status === "checking" || status === "saving";
      button.disabled = waiting || (mode === "loginPreserving" && !loginReady);
      button.dataset.active = String(mode === currentMode);
      button.setAttribute(
        "title",
        mode === "loginPreserving" && !loginReady
          ? "请先在 Codex 中登录 ChatGPT，然后重新检测。"
          : mode === "loginPreserving"
            ? "启用保留登录态的推荐模式。"
            : "临时启用前端强制注入。"
      );
    });
    document.querySelectorAll("[data-codex-mate-refresh-auth]").forEach((button) => {
      const waiting = status === "checking" || status === "saving";
      button.disabled = waiting;
      button.textContent = waiting ? "正在检测…" : loginReady ? "重新检测" : "我已登录，重新检测";
      button.setAttribute("title", loginReady ? "重新检测 ChatGPT 登录状态。" : "登录 ChatGPT 后重新检测。");
    });
  }

  async function checkCodexMateAuthModeStatus() {
    codexMateAuthModeStatus = { status: "checking", message: "正在读取增强模式…" };
    renderAuthModeStatus();
    try {
      const result = await withTimeout(postJson("/auth-enhancement-mode/status", {}), 2500, "增强模式读取超时");
      codexMateAuthModePayload = result || null;
      if (result?.status === "failed" || !applyCodexMateAuthModePayload(result)) {
        throw new Error(result?.message || "增强模式读取失败");
      }
      codexMateAuthModeStatus = { status: "ok", message: result.message || "增强模式已同步" };
    } catch (error) {
      codexMateAuthModeStatus = { status: "failed", message: bridgeErrorMessage(error, "增强模式读取失败") };
    }
    renderCodexMateMenu();
    renderAuthModeStatus();
  }

  async function setCodexMateAuthMode(mode) {
    if (mode !== "loginPreserving" && mode !== "forceInject") return;
    codexMateAuthModeStatus = { status: "saving", message: "正在切换增强模式…" };
    renderAuthModeStatus();
    try {
      const result = await withTimeout(postJson("/auth-enhancement-mode/set", { mode }), 8000, "增强模式切换超时");
      codexMateAuthModePayload = result || null;
      if (result?.status === "failed" || !applyCodexMateAuthModePayload(result)) {
        throw new Error(result?.message || "增强模式切换失败");
      }
      codexMateAuthModeStatus = { status: "ok", message: result.message || "增强模式已切换" };
      showToast(result.message || "增强模式已切换", null);
    } catch (error) {
      codexMateAuthModeStatus = { status: "failed", message: bridgeErrorMessage(error, "增强模式切换失败") };
      showToast(codexMateAuthModeStatus.message, null);
    }
    renderCodexMateMenu();
    renderAuthModeStatus();
    scan();
  }

  let codexMateProviderProfileStatus = { status: "checking", message: "正在读取供应商配置…" };
  let codexMateProviderProfilePayload = null;
  let codexMateProviderProfileDirty = false;

  function providerProfileDefaults() {
    return {
      mode: "mixed-api",
      provider: "codex-mate",
      base_url: "",
      model: "",
      wire_api: "responses",
      api_key_present: false,
    };
  }

  function currentProviderProfile() {
    return { ...providerProfileDefaults(), ...(codexMateProviderProfilePayload?.profile || {}) };
  }

  function activeProviderMode() {
    const active = document.querySelector("[data-codex-mate-provider-mode][data-active='true']");
    return active?.getAttribute("data-codex-mate-provider-mode") || currentProviderProfile().mode || "mixed-api";
  }

  function providerFieldValue(field) {
    const input = document.querySelector(`[data-codex-mate-provider-field="${field}"]`);
    return input?.value?.trim?.() || "";
  }

  function setProviderFieldValue(field, value) {
    const input = document.querySelector(`[data-codex-mate-provider-field="${field}"]`);
    if (input && document.activeElement !== input) input.value = value || "";
  }

  function fillProviderProfileForm(profile) {
    const next = { ...providerProfileDefaults(), ...(profile || {}) };
    document.querySelectorAll("[data-codex-mate-provider-mode]").forEach((button) => {
      button.dataset.active = String(button.getAttribute("data-codex-mate-provider-mode") === next.mode);
    });
    setProviderFieldValue("provider", next.provider);
    setProviderFieldValue("base_url", next.base_url);
    setProviderFieldValue("model", next.model);
    setProviderFieldValue("wire_api", next.wire_api || "responses");
    const keyInput = document.querySelector('[data-codex-mate-provider-field="api_key"]');
    if (keyInput && document.activeElement !== keyInput) {
      keyInput.value = "";
      keyInput.placeholder = next.api_key_present ? "已保存，留空继续使用" : "粘贴 API Key";
    }
  }

  function renderProviderProfileStatus() {
    const status = codexMateProviderProfileStatus.status || "ok";
    const mode = activeProviderMode();
    document.querySelectorAll("[data-codex-mate-provider-status]").forEach((node) => {
      node.dataset.status = status;
      node.textContent = codexMateProviderProfileStatus.message || "供应商配置已同步";
    });
    document.querySelectorAll("[data-codex-mate-provider-mode]").forEach((button) => {
      button.disabled = status === "checking" || status === "saving";
      button.dataset.active = String(button.getAttribute("data-codex-mate-provider-mode") === mode);
    });
    document.querySelectorAll("[data-codex-mate-provider-apply]").forEach((button) => {
      button.disabled = status === "checking" || status === "saving";
    });
    document.querySelectorAll(".codex-mate-provider-field").forEach((field) => {
      const input = field.querySelector("[data-codex-mate-provider-field]");
      const disabled = mode === "official" && !!input;
      field.dataset.disabled = String(disabled);
      if (input) input.disabled = disabled || status === "checking" || status === "saving";
    });
  }

  function readProviderProfileForm() {
    return {
      mode: activeProviderMode(),
      provider: providerFieldValue("provider"),
      base_url: providerFieldValue("base_url"),
      api_key: providerFieldValue("api_key"),
      model: providerFieldValue("model"),
      wire_api: providerFieldValue("wire_api") || "responses",
    };
  }

  async function checkCodexMateProviderProfileStatus() {
    codexMateProviderProfileStatus = { status: "checking", message: "正在读取供应商配置…" };
    renderProviderProfileStatus();
    try {
      const result = await withTimeout(postJson("/provider-profile/status", {}), 2500, "供应商配置读取超时");
      if (result?.status === "failed") throw new Error(result.message || "供应商配置读取失败");
      codexMateProviderProfilePayload = result || null;
      codexMateProviderProfileStatus = { status: "ok", message: result?.message || "供应商配置已同步" };
      if (!codexMateProviderProfileDirty) fillProviderProfileForm(result?.profile);
    } catch (error) {
      codexMateProviderProfileStatus = { status: "failed", message: bridgeErrorMessage(error, "供应商配置读取失败") };
    }
    renderProviderProfileStatus();
  }

  async function applyCodexMateProviderProfile() {
    const profile = readProviderProfileForm();
    codexMateProviderProfileStatus = { status: "saving", message: "正在切换供应商…" };
    renderProviderProfileStatus();
    try {
      const result = await withTimeout(postJson("/provider-profile/apply", { profile }), 10000, "供应商切换超时");
      codexMateProviderProfilePayload = result || null;
      if (result?.status === "failed") throw new Error(result?.message || "供应商切换失败");
      codexMateProviderProfileDirty = false;
      applyCodexMateAuthModePayload(result);
      codexMateAuthModePayload = result || codexMateAuthModePayload;
      codexMateAuthModeStatus = { status: "ok", message: result?.message || "增强模式已同步" };
      codexMateProviderProfileStatus = { status: "ok", message: result?.message || "供应商已切换" };
      fillProviderProfileForm(result?.profile);
      showToast(result?.message || "供应商已切换", null);
    } catch (error) {
      codexMateProviderProfileStatus = { status: "failed", message: bridgeErrorMessage(error, "供应商切换失败") };
      showToast(codexMateProviderProfileStatus.message, null);
    }
    renderCodexMateMenu();
    renderAuthModeStatus();
    renderProviderProfileStatus();
    scan();
  }

  let codexMateBackendStatus = { status: "checking", message: "正在检查后端…" };

  function renderBackendStatus() {
    const status = codexMateBackendStatus.status || "failed";
    document.querySelectorAll("[data-codex-mate-backend-status]").forEach((node) => {
      node.dataset.status = status;
      node.textContent = codexMateBackendStatus.message || (status === "ok" ? "后端已连接" : "未连接");
    });
    document.querySelectorAll("[data-codex-mate-backend-indicator]").forEach((node) => {
      node.dataset.status = status;
      node.setAttribute("title", status === "ok" ? "后端已连接" : status === "checking" ? "正在检查后端" : "未连接");
    });
  }

  async function checkBackendStatus() {
    codexMateBackendStatus = { status: "checking", message: "正在检查后端…" };
    renderBackendStatus();
    try {
      const result = await withTimeout(postJson("/backend/status", {}), 2500, "后端检查超时");
      codexMateBackendStatus = result?.status === "ok"
        ? { status: "ok", message: result.message || "后端已连接" }
        : { status: "failed", message: result?.message || "未连接" };
    } catch (error) {
      codexMateBackendStatus = { status: "failed", message: bridgeErrorMessage(error, "未连接") };
    }
    renderBackendStatus();
  }

  function updateStatusText(payload, fallback) {
    const message = payload?.message || fallback;
    const latest = payload?.latest_version && payload.latest_version !== codexMateVersion ? `（${payload.latest_version}）` : "";
    return `${message || ""}${latest}`.trim();
  }

  function renderUpdateState(payload) {
    const status = document.querySelector("[data-codex-mate-update-status]");
    const updateButton = document.querySelector("[data-codex-mate-run-update]");
    if (!status || !updateButton) return;
    const canUpdate = !!payload?.can_update;
    status.textContent = updateStatusText(payload, "点击检查更新。");
    updateButton.hidden = !canUpdate;
    updateButton.disabled = false;
  }

  function bridgeErrorMessage(error, fallback) {
    const message = error?.message || String(error || "");
    return message || fallback;
  }

  function withTimeout(promise, timeoutMs, timeoutMessage) {
    let timeoutId = null;
    const timeout = new Promise((_, reject) => {
      timeoutId = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
    });
    return Promise.race([promise, timeout]).finally(() => clearTimeout(timeoutId));
  }

  function bridgeFallbackTimeoutMs(path) {
    if (path === "/backend/status") return 700;
    if (path === "/provider-profile/status" || path === "/auth-enhancement-mode/status") return 1200;
    return 2500;
  }

  function retryableUpdateResult(result) {
    if (result?.status === "failed" && !("can_update" in result)) {
      return { ...result, can_update: true };
    }
    return result;
  }

  async function checkCodexMateUpdate(button) {
    button.disabled = true;
    renderUpdateState({ message: "正在检查更新...", can_update: false });
    try {
      const result = await withTimeout(postJson("/check-update", {}), 15000, "检查更新超时，请稍后重试。");
      renderUpdateState(result);
    } catch (error) {
      renderUpdateState({ status: "failed", message: bridgeErrorMessage(error, "检查更新失败，请稍后重试。"), can_update: false });
    } finally {
      button.disabled = false;
    }
  }

  async function runCodexMateUpdate(button) {
    button.disabled = true;
    renderUpdateState({ message: "正在更新，请稍候...", can_update: true });
    try {
      const result = await withTimeout(postJson("/update", {}), 180000, "更新超时，请稍后重试。");
      renderUpdateState(retryableUpdateResult(result));
      showToast(result.message || (result.status === "updated" ? "更新完成" : "更新失败"), null);
    } catch (error) {
      const message = bridgeErrorMessage(error, "更新失败，请稍后重试。");
      renderUpdateState({ status: "failed", message, can_update: true });
      showToast(message, null);
    } finally {
      button.disabled = false;
    }
  }

  function renderCodexMateMenu() {
    const settings = codexMateSettings();
    document.querySelectorAll(".codex-mate-toggle[data-codex-mate-setting]").forEach((button) => {
      const key = button.getAttribute("data-codex-mate-setting");
      button.dataset.enabled = String(!!settings[key]);
    });
    document.querySelectorAll("[data-codex-mate-auth-mode]").forEach((button) => {
      button.dataset.active = String(button.getAttribute("data-codex-mate-auth-mode") === settings.authEnhancementMode);
    });
  }

  function openCodexMateModal() {
    document.querySelectorAll(".codex-mate-modal-overlay").forEach((node) => node.remove());
    document.querySelectorAll('[data-codex-mate-dialog="true"]').forEach((node) => node.remove());
    codexMateProviderProfileDirty = false;
    const overlay = document.createElement("div");
    overlay.className = "codex-mate-modal-overlay";
    overlay.innerHTML = `
      <div class="codex-mate-modal-content" role="dialog" aria-modal="true" aria-label="Codex Mate">
        <div class="codex-mate-modal-header">
          <div class="codex-mate-modal-title"><span class="codex-mate-backend-indicator" data-codex-mate-backend-indicator="true" data-status="checking"></span>Codex Mate ${codexMateVersion}</div>
          <button type="button" class="codex-mate-modal-close" aria-label="关闭">×</button>
        </div>
        <div class="codex-mate-modal-body">
          <div class="codex-mate-mode-row">
            <div class="codex-mate-mode-header">
              <div class="codex-mate-mode-title">供应商配置</div>
              <div class="codex-mate-mode-description">在这里填 API，不需要手动改 config.toml 或 auth.json。</div>
            </div>
            <div class="codex-mate-provider-form">
              <div class="codex-mate-provider-modes" role="group" aria-label="供应商模式">
                <button type="button" class="codex-mate-provider-mode" data-codex-mate-provider-mode="official">官方登录<br><span>不写 API Key</span></button>
                <button type="button" class="codex-mate-provider-mode" data-codex-mate-provider-mode="mixed-api">保留登录态 + API<br><span>需要先登录 ChatGPT</span></button>
                <button type="button" class="codex-mate-provider-mode" data-codex-mate-provider-mode="pure-api">纯 API<br><span>写入 auth.json</span></button>
              </div>
              <div class="codex-mate-provider-grid">
                <label class="codex-mate-provider-field"><span>Provider 名称</span><input data-codex-mate-provider-field="provider" autocomplete="off" spellcheck="false" value="codex-mate"></label>
                <label class="codex-mate-provider-field"><span>Model</span><input data-codex-mate-provider-field="model" autocomplete="off" spellcheck="false" placeholder="例如 gpt-5.5"></label>
                <label class="codex-mate-provider-field"><span>Base URL</span><input data-codex-mate-provider-field="base_url" autocomplete="off" spellcheck="false" placeholder="https://example.com/v1"></label>
                <label class="codex-mate-provider-field"><span>API Key</span><input data-codex-mate-provider-field="api_key" type="password" autocomplete="off" spellcheck="false" placeholder="粘贴 API Key"></label>
                <label class="codex-mate-provider-field"><span>Wire API</span><select data-codex-mate-provider-field="wire_api"><option value="responses">responses</option><option value="chat">chat</option></select></label>
              </div>
              <div class="codex-mate-provider-footer">
                <div class="codex-mate-provider-status" data-codex-mate-provider-status="true" data-status="checking">正在读取供应商配置…</div>
                <button type="button" class="codex-mate-action-button" data-codex-mate-provider-apply="true">切换供应商</button>
              </div>
            </div>
          </div>
          <div class="codex-mate-mode-row">
            <div class="codex-mate-mode-header">
              <div class="codex-mate-mode-title">增强模式</div>
              <div class="codex-mate-mode-description">先检测 ChatGPT 登录态，再给出推荐操作。</div>
            </div>
            <div class="codex-mate-auth-card">
              <div>
                <div class="codex-mate-row-title">当前检测</div>
                <div class="codex-mate-auth-summary" data-codex-mate-auth-summary="true">正在检测 ChatGPT 登录</div>
                <div class="codex-mate-auth-detail" data-codex-mate-auth-detail="true">Codex Mate 会先确认本机是否有 ChatGPT 登录态，再决定是否可以启用保留登录态。</div>
              </div>
              <button type="button" class="codex-mate-action-button" data-codex-mate-refresh-auth="true">我已登录，重新检测</button>
            </div>
            <div class="codex-mate-mode-switch" role="group" aria-label="增强模式">
              <button type="button" class="codex-mate-mode-option" data-codex-mate-auth-mode="loginPreserving"><strong>启用推荐模式</strong><span>保持登录态，移动端、Remote 和原生入口优先可用。</span></button>
              <button type="button" class="codex-mate-mode-option" data-codex-mate-auth-mode="forceInject"><strong>临时启用强制注入</strong><span>不改登录文件，只由前端接管插件入口。</span></button>
            </div>
            <div class="codex-mate-mode-status" data-codex-mate-auth-mode-status="true" data-status="checking">正在读取增强模式…</div>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">会话删除</div><div class="codex-mate-row-description">在会话列表悬停显示删除按钮，并支持撤销。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="sessionDelete"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">Markdown 导出</div><div class="codex-mate-row-description">在会话列表悬停显示导出按钮，把本地 rollout 导出为 Markdown。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="markdownExport"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">会话移动</div><div class="codex-mate-row-description">在会话列表悬停显示移动按钮，可移到普通对话或其他项目。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="projectMove"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">对话时间线</div><div class="codex-mate-row-description">在右侧显示用户问题标记，点击即可跳到对应位置。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="conversationTimeline"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">滚动位置恢复</div><div class="codex-mate-row-description">切换会话时记住上次阅读位置。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="threadScrollRestore"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">原生菜单栏位置</div><div class="codex-mate-row-description">把 Codex Mate 菜单插入顶部原生菜单栏；默认关闭以避免页面重渲染冲突。</div></div>
            <button type="button" class="codex-mate-toggle" data-codex-mate-setting="nativeMenuPlacement"><span></span></button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">后端连接</div><div class="codex-mate-backend-label" data-codex-mate-backend-status="true" data-status="checking">正在检查后端…</div></div>
            <button type="button" class="codex-mate-action-button" data-codex-mate-check-backend="true">刷新</button>
          </div>
          <div class="codex-mate-row">
            <div><div class="codex-mate-row-title">检查更新</div><div class="codex-mate-row-description" data-codex-mate-update-status="true">点击检查更新。</div></div>
            <div class="codex-mate-actions">
              <button type="button" class="codex-mate-action-button" data-codex-mate-check-update="true">检查更新</button>
              <button type="button" class="codex-mate-action-button" data-codex-mate-run-update="true" hidden>一键更新</button>
            </div>
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
      if (event.target === overlay || closestElement(event.target, ".codex-mate-modal-close")) {
        overlay.remove();
        return;
      }
      const issueButton = closestElement(event.target, "[data-codex-mate-issue]");
      if (issueButton) {
        const issueUrl = "https://github.com/serein431/Codex-Mate/issues";
        window.open(issueUrl, "_blank");
        return;
      }
      const checkUpdateButton = closestElement(event.target, "[data-codex-mate-check-update]");
      if (checkUpdateButton) {
        checkCodexMateUpdate(checkUpdateButton);
        return;
      }
      const runUpdateButton = closestElement(event.target, "[data-codex-mate-run-update]");
      if (runUpdateButton) {
        runCodexMateUpdate(runUpdateButton);
        return;
      }
      const checkBackendButton = closestElement(event.target, "[data-codex-mate-check-backend]");
      if (checkBackendButton) {
        void checkBackendStatus();
        return;
      }
      const providerModeButton = closestElement(event.target, "[data-codex-mate-provider-mode]");
      if (providerModeButton) {
        codexMateProviderProfileDirty = true;
        document.querySelectorAll("[data-codex-mate-provider-mode]").forEach((button) => {
          button.dataset.active = String(button === providerModeButton);
        });
        renderProviderProfileStatus();
        return;
      }
      const providerApplyButton = closestElement(event.target, "[data-codex-mate-provider-apply]");
      if (providerApplyButton) {
        void applyCodexMateProviderProfile();
        return;
      }
      const refreshAuthButton = closestElement(event.target, "[data-codex-mate-refresh-auth]");
      if (refreshAuthButton) {
        void checkCodexMateAuthModeStatus();
        return;
      }
      const authModeButton = closestElement(event.target, "[data-codex-mate-auth-mode]");
      if (authModeButton) {
        void setCodexMateAuthMode(authModeButton.getAttribute("data-codex-mate-auth-mode"));
        return;
      }
      const toggle = closestElement(event.target, "[data-codex-mate-setting]");
      if (!toggle) return;
      const key = toggle.getAttribute("data-codex-mate-setting");
      setCodexMateSetting(key, !codexMateSettings()[key]);
    }, true);
    overlay.addEventListener("input", (event) => {
      if (!closestElement(event.target, "[data-codex-mate-provider-field]")) return;
      codexMateProviderProfileDirty = true;
    }, true);
    overlay.addEventListener("change", (event) => {
      if (!closestElement(event.target, "[data-codex-mate-provider-field]")) return;
      codexMateProviderProfileDirty = true;
    }, true);
    overlay.querySelector(".codex-mate-modal-close")?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      overlay.remove();
    }, true);
    overlay.addEventListener("keydown", (event) => {
      if (event.key === "Escape") overlay.remove();
    }, true);
    document.body.appendChild(overlay);
    overlay.querySelector(".codex-mate-modal-close")?.focus?.({ preventScroll: true });
    renderCodexMateMenu();
    renderAuthModeStatus();
    renderProviderProfileStatus();
    renderBackendStatus();
    void checkCodexMateProviderProfileStatus();
    void checkCodexMateAuthModeStatus();
    void checkBackendStatus();
  }

  function findNativeMenuInsertionPoint() {
    if (!codexMateSettings().nativeMenuPlacement) return null;
    const header = document.querySelector(".app-header-tint");
    const directGroup = header?.querySelector(".ms-auto.flex.shrink-0.items-center.gap-1\\.5");
    if (directGroup?.querySelectorAll("button").length >= 2) {
      const buttons = Array.from(directGroup.querySelectorAll("button")).filter((button) => !button.closest(`#${codexMateMenuId}`));
      return { parent: directGroup, before: buttons[0] || null, nativeButtonClass: buttons[buttons.length - 1]?.className || "" };
    }
    const rightGroups = Array.from(header?.querySelectorAll("div") || []).filter((group) => {
      const className = group.className?.toString() || "";
      if (!/\bms-auto\b/.test(className) || !/\bflex\b/.test(className) || !/\bitems-center\b/.test(className)) return false;
      const rect = group.getBoundingClientRect?.();
      if (!rect || rect.width <= 0 || rect.height <= 0 || rect.top < 4 || rect.top > 18 || rect.left < window.innerWidth * 0.55 || rect.right > window.innerWidth - 24) return false;
      const style = window.getComputedStyle?.(group);
      if (style?.visibility === "hidden" || style?.display === "none") return false;
      return group.querySelectorAll("button").length >= 2;
    });
    const menuBar = rightGroups.sort((left, right) => right.getBoundingClientRect().left - left.getBoundingClientRect().left)[0];
    if (!menuBar) return null;
    const buttons = Array.from(menuBar.querySelectorAll("button")).filter((button) => !button.closest(`#${codexMateMenuId}`));
    return { parent: menuBar, before: buttons[0] || null, nativeButtonClass: buttons[buttons.length - 1]?.className || "" };
  }

  function removeDuplicateCodexMateMenus(keep) {
    document.querySelectorAll(`#${codexMateMenuId}, [data-codex-mate-menu="true"]`).forEach((node) => {
      if (node !== keep) node.remove();
    });
    Array.from(document.querySelectorAll("button")).forEach((button) => {
      const label = (button.textContent || "").trim();
      if (label.startsWith("Codex Mate") && !button.closest(`#${codexMateMenuId}`)) {
        button.remove();
      }
    });
  }

  function configureCodexMateTrigger(menu, trigger, nativeButtonClass) {
    if (!trigger) return;
    trigger.className = "codex-mate-toolbar-button codex-mate-trigger";
    trigger.textContent = "CM";
    trigger.dataset.codexMateCompact = "true";
    trigger.setAttribute("aria-label", `Codex Mate ${codexMateVersion}`);
    trigger.setAttribute("title", `Codex Mate ${codexMateVersion}`);
    if (trigger.dataset.codexMateTriggerInstalled === codexMateTriggerInstalled) return;
    trigger.dataset.codexMateTriggerInstalled = codexMateTriggerInstalled;
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      trigger.addEventListener(eventName, (event) => {
        event.stopPropagation();
        event.stopImmediatePropagation?.();
      }, true);
    });
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      openCodexMateModal();
    }, true);
  }

  function visibleElements(selector) {
    return Array.from(document.querySelectorAll(selector)).filter((element) => {
      const rect = element.getBoundingClientRect?.();
      if (!rect || rect.width <= 0 || rect.height <= 0) return false;
      if (rect.bottom < 0 || rect.top > window.innerHeight || rect.right < 0 || rect.left > window.innerWidth) return false;
      const style = window.getComputedStyle?.(element);
      return style?.visibility !== "hidden" && style?.display !== "none";
    });
  }

  function visibleRightPanelLeft() {
    const panels = visibleElements("[role='tabpanel'], .absolute.top-0.bottom-0.left-0").filter((panel) => {
      const rect = panel.getBoundingClientRect?.();
      return rect
        && rect.left > window.innerWidth * 0.35
        && rect.top <= 90
        && rect.height > 160
        && rect.width > 180;
    });
    const rects = panels.map((panel) => panel.getBoundingClientRect());
    if (!rects.length) return null;
    return Math.min(...rects.map((rect) => rect.left));
  }

  function floatingMenuLeft(menu, panelLeft) {
    const menuWidth = Math.max(58, Math.ceil(menu.getBoundingClientRect?.().width || 58));
    const margin = 8;
    const lowerBound = Math.max(8, Math.round(panelLeft) + margin);
    const upperBound = Math.max(lowerBound + menuWidth, Math.round(window.innerWidth) - margin);
    const occupied = visibleElements("button, [role='button']")
      .filter((button) => !button.closest(`#${codexMateMenuId}`))
      .map((button) => button.getBoundingClientRect())
      .filter((rect) => rect.top < 44 && rect.bottom > 0 && rect.right > lowerBound && rect.left < upperBound)
      .map((rect) => ({
        left: Math.max(lowerBound, Math.floor(rect.left) - 4),
        right: Math.min(upperBound, Math.ceil(rect.right) + 4),
      }))
      .sort((left, right) => right.left - left.left);
    let cursor = upperBound;
    for (const rect of occupied) {
      if (cursor - rect.right >= menuWidth) return cursor - menuWidth;
      cursor = Math.min(cursor, rect.left - margin);
    }
    if (cursor - lowerBound >= menuWidth) return cursor - menuWidth;
    return lowerBound;
  }

  function placeCodexMateMenu(menu, insertionPoint) {
    const panelLeft = visibleRightPanelLeft();
    if (panelLeft !== null) {
      menu.className = "codex-mate-menu-floating";
      menu.style.left = `${floatingMenuLeft(menu, panelLeft)}px`;
      menu.style.right = "auto";
      if (menu.parentElement !== document.documentElement) document.documentElement.appendChild(menu);
      return;
    }
    menu.style.left = "";
    menu.style.right = "";
    if (insertionPoint) {
      menu.className = "";
      const safeBefore = insertionPoint.before?.parentElement === insertionPoint.parent ? insertionPoint.before : null;
      if (menu.parentElement !== insertionPoint.parent) {
        insertionPoint.parent.insertBefore(menu, safeBefore);
      }
    } else {
      menu.className = "codex-mate-menu-floating";
      if (menu.parentElement !== document.documentElement) document.documentElement.appendChild(menu);
    }
  }

  function installCodexMateMenu() {
    const existing = document.getElementById(codexMateMenuId);
    removeDuplicateCodexMateMenus(existing);
    let insertionPoint = findNativeMenuInsertionPoint();
    if (existing && existing.dataset.codexMateMenuVersion !== codexMateMenuVersion) {
      existing.remove();
      insertionPoint = findNativeMenuInsertionPoint();
    } else if (existing && existing.isConnected) {
      configureCodexMateTrigger(existing, existing.querySelector("button"), insertionPoint?.nativeButtonClass || "");
      placeCodexMateMenu(existing, insertionPoint);
      removeDuplicateCodexMateMenus(existing);
      return;
    }
    const menu = document.createElement("div");
    menu.id = codexMateMenuId;
    menu.dataset.codexMateMenu = "true";
    menu.dataset.codexMateMenuVersion = codexMateMenuVersion;
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      menu.addEventListener(eventName, (event) => {
        event.stopPropagation();
      }, true);
    });
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.textContent = "CM";
    const nativeButtonClass = insertionPoint?.nativeButtonClass || "codex-mate-trigger";
    configureCodexMateTrigger(menu, trigger, nativeButtonClass);
    menu.appendChild(trigger);
    placeCodexMateMenu(menu, insertionPoint);
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
    if (codexMateAuthModeStatus.status === "checking" || codexMateAuthModeStatus.status === "saving") return;
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
    if (codexMateAuthModeStatus.status === "checking" || codexMateAuthModeStatus.status === "saving") return;
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

  async function httpPostJson(path, payload) {
    try {
      const response = await fetch(`${helperBase}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        return { status: "failed", message: result?.message || result?.error || "请求失败" };
      }
      return result;
    } catch (_) {
      return { status: "failed", message: path === "/backend/status" ? "未连接" : "Codex Mate 后端未连接，请重启启动器" };
    }
  }

  async function postJson(path, payload) {
    if (!window.__codexMateBridge) {
      return await httpPostJson(path, payload);
    }
    try {
      const result = await withTimeout(window.__codexMateBridge(path, payload), bridgeFallbackTimeoutMs(path), "Codex Mate bridge timeout");
      if (result?.status !== "failed" || !/Unknown bridge path|bridge timeout/i.test(String(result?.message || ""))) {
        return result;
      }
    } catch (_) {
      // Fall through to the HTTP helper when the in-page bridge is stale or wedged.
    }
    return await httpPostJson(path, payload);
  }

  function downloadMarkdown(filename, markdown) {
    if (!filename || typeof markdown !== "string") throw new Error("导出结果不完整");
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportMarkdown(ref) {
    try {
      const result = await postJson("/export-markdown", ref);
      if (result.status === "exported" && result.filename && typeof result.markdown === "string") {
        downloadMarkdown(result.filename, result.markdown);
        showToast(result.message || "导出成功", null);
        return;
      }
      showToast(result.message || "导出失败", null);
    } catch (error) {
      showToast(`导出失败：${error?.message || error}`, null);
    }
  }

  function numericTimestamp(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric > 0 ? numeric : 0;
  }

  function timestampValueToMs(value) {
    const timestamp = numericTimestamp(value);
    if (!timestamp) return 0;
    return timestamp < 1000000000000 ? timestamp * 1000 : timestamp;
  }

  function timestampMsFromPayload(payload) {
    return numericTimestamp(payload?.updated_at_ms) || timestampValueToMs(payload?.updated_at) || numericTimestamp(payload?.created_at_ms);
  }

  function projectMoveSessionKey(sessionId) {
    const variants = threadIdVariants(sessionId);
    const bareId = variants.find((id) => !id.startsWith("local:"));
    return bareId || variants[0] || "";
  }

  function uuidV7TimestampMs(sessionId) {
    const id = projectMoveSessionKey(sessionId).replaceAll("-", "");
    if (!/^[0-9a-fA-F]{12}/.test(id)) return 0;
    const timestamp = Number.parseInt(id.slice(0, 12), 16);
    return Number.isFinite(timestamp) ? timestamp : 0;
  }

  function sortMsForSession(sessionId, preferredValue) {
    return numericTimestamp(preferredValue) || uuidV7TimestampMs(sessionId);
  }

  function normalizeWorkspacePath(path) {
    const normalized = String(path || "").trim().replace(/\\/g, "/").replace(/\/+$/, "");
    return normalized || String(path || "").trim();
  }

  function sameWorkspacePath(left, right) {
    const leftPath = normalizeWorkspacePath(left);
    const rightPath = normalizeWorkspacePath(right);
    return !!leftPath && !!rightPath && leftPath === rightPath;
  }

  function displayProjectName(path) {
    const trimmed = String(path || "").replace(/\/+$/, "");
    return trimmed.split(/[\\/]+/).filter(Boolean).pop() || trimmed || "未命名项目";
  }

  function projectsSection() {
    return document.querySelector('[data-app-action-sidebar-section-heading="Projects"]');
  }

  function chatsSection() {
    return document.querySelector('[data-app-action-sidebar-section-heading="Chats"]');
  }

  function projectRowListItem(projectRow) {
    return projectRow.closest?.('[role="listitem"][aria-label]') || projectRow.closest?.('[role="listitem"]') || projectRow;
  }

  function nativeProjectTargets() {
    const section = projectsSection();
    const seen = new Set();
    const targets = [];
    Array.from(document.querySelectorAll("[data-app-action-sidebar-project-row]")).forEach((row) => {
      if (section && !section.contains(row)) return;
      const path = row.getAttribute("data-app-action-sidebar-project-id") || "";
      const normalizedPath = normalizeWorkspacePath(path);
      if (!normalizedPath || seen.has(normalizedPath)) return;
      const label = row.getAttribute("data-app-action-sidebar-project-label") || row.getAttribute("aria-label") || displayProjectName(path);
      seen.add(normalizedPath);
      targets.push({ kind: "project", label: String(label || displayProjectName(path)), description: path, path, normalizedPath, row, listItem: projectRowListItem(row) });
    });
    return targets;
  }

  function projectMoveTargets() {
    return [
      { kind: "projectless", label: "普通对话", description: "不属于任何项目", path: "", normalizedPath: "" },
      ...nativeProjectTargets().map((target) => ({
        kind: "project",
        label: target.label,
        description: target.description,
        path: target.path,
        normalizedPath: target.normalizedPath,
      })),
    ];
  }

  function readProjectMoveProjection() {
    try {
      const parsed = JSON.parse(localStorage.getItem(projectMoveProjectionKey) || "{}");
      const raw = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
      const now = Date.now();
      const projection = {};
      Object.entries(raw).forEach(([key, value]) => {
        if (!value || typeof value !== "object") return;
        const sessionId = projectMoveSessionKey(value.sessionId || key);
        if (!sessionId) return;
        if (typeof value.at === "number" && now - value.at > projectMoveProjectionTtlMs) return;
        const kind = value.kind === "projectless" || value.targetKind === "projectless" ? "projectless" : "project";
        const path = String(value.path || value.targetCwd || "");
        if (kind === "project" && !path) return;
        projection[sessionId] = {
          sessionId,
          kind,
          label: String(value.label || value.targetLabel || (kind === "projectless" ? "普通对话" : displayProjectName(path))),
          description: String(value.description || path || "不属于任何项目"),
          path,
          normalizedPath: normalizeWorkspacePath(path),
          sortMs: sortMsForSession(sessionId, value.sortMs || value.updatedAtMs || value.updated_at_ms),
          sortMsTrusted: value.sortMsTrusted === true,
          at: typeof value.at === "number" ? value.at : now,
        };
      });
      return projection;
    } catch {
      return {};
    }
  }

  function writeProjectMoveProjection(projection) {
    try {
      localStorage.setItem(projectMoveProjectionKey, JSON.stringify(projection || {}));
    } catch (error) {
      window.__codexProjectMoveProjectionFailures = window.__codexProjectMoveProjectionFailures || [];
      window.__codexProjectMoveProjectionFailures.push(String(error?.stack || error));
    }
  }

  function saveProjectMoveProjection(ref, target, sortMs) {
    const sessionId = projectMoveSessionKey(ref.session_id);
    if (!sessionId || !target) return;
    const projection = readProjectMoveProjection();
    projection[sessionId] = {
      sessionId,
      kind: target.kind === "projectless" ? "projectless" : "project",
      label: target.label || (target.kind === "projectless" ? "普通对话" : displayProjectName(target.path)),
      description: target.description || target.path || "不属于任何项目",
      path: target.path || "",
      normalizedPath: normalizeWorkspacePath(target.path || ""),
      sortMs: sortMsForSession(ref.session_id, sortMs || target.sortMs),
      sortMsTrusted: target.sortMsTrusted === true,
      at: Date.now(),
    };
    writeProjectMoveProjection(projection);
  }

  function clearProjectMoveProjection(ref) {
    const projection = readProjectMoveProjection();
    const keys = threadIdVariants(ref.session_id).map(projectMoveSessionKey).filter(Boolean);
    let changed = false;
    keys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(projection, key)) {
        delete projection[key];
        changed = true;
      }
    });
    if (changed) writeProjectMoveProjection(projection);
  }

  function projectionForSessionId(sessionId, projection = readProjectMoveProjection()) {
    const key = projectMoveSessionKey(sessionId);
    return key ? projection[key] || null : null;
  }

  function rowListItem(row) {
    return row.closest?.('[role="listitem"]') || row;
  }

  function threadRowFromListItem(item) {
    if (!item) return null;
    if (item.matches?.("[data-app-action-sidebar-thread-id]")) return item;
    return item.querySelector?.("[data-app-action-sidebar-thread-id]") || null;
  }

  function rowIsInChats(row) {
    return !!row.closest?.('[data-app-action-sidebar-section-heading="Chats"]');
  }

  function chatsThreadList() {
    return chatsSection()?.querySelector?.('[role="list"][aria-label="对话"], [role="list"]') || null;
  }

  function projectRowFromListItem(item) {
    if (!item) return null;
    if (item.matches?.("[data-app-action-sidebar-project-row]")) return item;
    return item.querySelector?.("[data-app-action-sidebar-project-row]") || null;
  }

  function projectItemMatchesTarget(projectItem, target) {
    const projectRow = projectRowFromListItem(projectItem);
    const projectPath = projectRow?.getAttribute?.("data-app-action-sidebar-project-id") || "";
    if (projectPath && sameWorkspacePath(projectPath, target.path)) return true;
    const label = projectRow?.getAttribute?.("data-app-action-sidebar-project-label") || projectItem?.getAttribute?.("aria-label") || "";
    return String(label).replace(/\s+/g, " ").trim() === String(target.label || displayProjectName(target.path)).replace(/\s+/g, " ").trim();
  }

  function findProjectListItem(target) {
    const nativeTarget = nativeProjectTargets().find((project) => sameWorkspacePath(project.path, target.path));
    if (nativeTarget?.listItem) return nativeTarget.listItem;
    const section = projectsSection();
    if (!section) return null;
    return Array.from(section.querySelectorAll('[role="listitem"][aria-label]')).find((item) => projectItemMatchesTarget(item, target)) || null;
  }

  function closestProjectListItem(row) {
    let current = row?.parentElement || null;
    while (current) {
      if (current.matches?.('[role="listitem"][aria-label], [role="listitem"]') && projectRowFromListItem(current)) return current;
      current = current.parentElement;
    }
    return null;
  }

  function rowIsUnderTargetProject(row, target) {
    const item = closestProjectListItem(row);
    return !!item && projectItemMatchesTarget(item, target);
  }

  function rowIsUnderTarget(row, target) {
    return target?.kind === "projectless" ? rowIsInChats(row) : rowIsUnderTargetProject(row, target);
  }

  function projectMoveInjectedList(projectItem) {
    let list = projectItem.querySelector('[data-codex-project-move-injected-list="true"]');
    if (!list) {
      const body = Array.from(projectItem.children).find((child) => child.classList?.contains("overflow-hidden")) || projectItem;
      list = document.createElement("div");
      list.setAttribute("role", "list");
      list.setAttribute("data-codex-project-move-injected-list", "true");
      list.className = "flex flex-col";
      body.appendChild(list);
    }
    return list;
  }

  function projectThreadList(projectItem, target) {
    const projectLists = Array.from(projectItem.querySelectorAll("[data-app-action-sidebar-project-list-id]"));
    return projectLists.find((list) => sameWorkspacePath(list.getAttribute("data-app-action-sidebar-project-list-id"), target.path))
      || projectLists[0]
      || projectMoveInjectedList(projectItem);
  }

  function projectEmptyStateNodes(projectItem) {
    const emptyLabels = new Set(["暂无对话", "No conversations"]);
    return Array.from(projectItem?.querySelectorAll?.("div, span") || []).filter((node) => {
      if (node.closest?.("[data-app-action-sidebar-thread-id], [data-codex-project-move-injected-list='true']")) return false;
      return emptyLabels.has(String(node.textContent || "").replace(/\s+/g, " ").trim());
    });
  }

  function setProjectEmptyStateHidden(projectItem, hidden) {
    projectEmptyStateNodes(projectItem).forEach((node) => {
      if (hidden) {
        node.dataset.codexProjectMoveEmptyHidden = "true";
        node.classList.add("codex-project-move-hidden");
      } else if (node.dataset.codexProjectMoveEmptyHidden === "true") {
        delete node.dataset.codexProjectMoveEmptyHidden;
        node.classList.remove("codex-project-move-hidden");
      }
    });
  }

  function updateProjectMoveEmptyStates() {
    document.querySelectorAll('[data-codex-project-move-injected-list="true"]').forEach((list) => {
      const projectItem = list.closest('[role="listitem"][aria-label], [role="listitem"]');
      const hasRows = Array.from(list.children).some((child) => !!threadRowFromListItem(child));
      if (!hasRows) list.remove();
      if (projectItem) setProjectEmptyStateHidden(projectItem, hasRows || !!projectItem.querySelector("[data-app-action-sidebar-thread-id]"));
    });
    document.querySelectorAll('[data-codex-project-move-empty-hidden="true"]').forEach((node) => {
      const projectItem = node.closest('[role="listitem"][aria-label], [role="listitem"]');
      if (!projectItem || !projectItem.querySelector("[data-app-action-sidebar-thread-id]")) {
        delete node.dataset.codexProjectMoveEmptyHidden;
        node.classList.remove("codex-project-move-hidden");
      }
    });
  }

  function rowSortMs(row, ref = sessionRefFromRow(row), target = null) {
    return sortMsForSession(ref.session_id, target?.sortMs || row?.dataset?.codexProjectMoveSortMs || rowListItem(row)?.dataset?.codexProjectMoveSortMs);
  }

  function rowPinned(row) {
    return row?.getAttribute?.("data-app-action-sidebar-thread-pinned") === "true"
      || rowListItem(row)?.getAttribute?.("data-app-action-sidebar-thread-pinned") === "true";
  }

  function insertRowItemByTime(list, item, row, target) {
    const ref = sessionRefFromRow(row);
    const sortMs = rowSortMs(row, ref, target);
    item.dataset.codexProjectMoveSortMs = String(sortMs || 0);
    row.dataset.codexProjectMoveSortMs = String(sortMs || 0);
    const pinned = rowPinned(row);
    const sessionKey = projectMoveSessionKey(ref.session_id);
    const existingItems = Array.from(list.children).filter((child) => child !== item);
    let firstNonThreadItem = null;
    for (const child of existingItems) {
      const childRow = threadRowFromListItem(child);
      if (!childRow) {
        firstNonThreadItem = firstNonThreadItem || child;
        continue;
      }
      const childPinned = rowPinned(childRow);
      if (childPinned && !pinned) continue;
      if (!childPinned && pinned) {
        list.insertBefore(item, child);
        return;
      }
      const childSortMs = rowSortMs(childRow);
      const childKey = projectMoveSessionKey(sessionRefFromRow(childRow).session_id);
      if (sortMs > childSortMs || (sortMs === childSortMs && sessionKey > childKey)) {
        list.insertBefore(item, child);
        return;
      }
    }
    if (firstNonThreadItem) {
      list.insertBefore(item, firstNonThreadItem);
      return;
    }
    list.appendChild(item);
  }

  function moveRowToProjectList(row, target) {
    const projectItem = findProjectListItem(target);
    if (!projectItem) return false;
    const list = projectThreadList(projectItem, target);
    if (!list) return false;
    const item = rowListItem(row);
    insertRowItemByTime(list, item, row, target);
    cachedSessionRowsAt = 0;
    item.dataset.codexProjectMoveTargetKind = "project";
    item.dataset.codexProjectMoveTargetCwd = target.path;
    row.dataset.codexProjectMoveTargetKind = "project";
    row.dataset.codexProjectMoveTargetCwd = target.path;
    setProjectEmptyStateHidden(projectItem, true);
    return true;
  }

  function moveRowToChats(row, target = null) {
    const list = chatsThreadList();
    if (!list) return false;
    const item = rowListItem(row);
    insertRowItemByTime(list, item, row, target);
    cachedSessionRowsAt = 0;
    item.dataset.codexProjectMoveTargetKind = "projectless";
    row.dataset.codexProjectMoveTargetKind = "projectless";
    delete item.dataset.codexProjectMoveTargetCwd;
    delete row.dataset.codexProjectMoveTargetCwd;
    updateProjectMoveEmptyStates();
    return true;
  }

  function rowProjectionKind(row) {
    return row?.dataset?.codexProjectMoveTargetKind || rowListItem(row)?.dataset?.codexProjectMoveTargetKind || "";
  }

  function clearRowProjectionMarkers(row) {
    const item = rowListItem(row);
    delete row.dataset.codexProjectMoveTargetKind;
    delete row.dataset.codexProjectMoveTargetCwd;
    delete item.dataset.codexProjectMoveTargetKind;
    delete item.dataset.codexProjectMoveTargetCwd;
  }

  function applyProjectMoveProjection() {
    if (!codexMateSettings().projectMove) return;
    const projection = readProjectMoveProjection();
    const rows = sessionRows(true);
    const targetRowsById = new Map();
    const settledRefs = [];
    const now = Date.now();
    rows.forEach((row) => {
      const ref = sessionRefFromRow(row);
      const target = projectionForSessionId(ref.session_id, projection);
      if (!target) {
        clearRowProjectionMarkers(row);
        return;
      }
      const rowId = projectMoveSessionKey(ref.session_id);
      if (rowIsUnderTarget(row, target)) {
        const existingRow = targetRowsById.get(rowId);
        if (existingRow && existingRow !== row) {
          const rowToRemove = rowProjectionKind(existingRow) && !rowProjectionKind(row) ? existingRow : row;
          rowListItem(rowToRemove).remove();
          if (rowToRemove === existingRow) targetRowsById.set(rowId, row);
          return;
        }
        targetRowsById.set(rowId, row);
        if (!rowProjectionKind(row) && typeof target.at === "number" && now - target.at > projectMoveProjectionSettleMs) settledRefs.push(ref);
      }
    });
    rows.forEach((row) => {
      if (!row.isConnected) return;
      const ref = sessionRefFromRow(row);
      const target = projectionForSessionId(ref.session_id, projection);
      if (!target || rowIsUnderTarget(row, target)) return;
      const rowId = projectMoveSessionKey(ref.session_id);
      if (targetRowsById.has(rowId)) {
        rowListItem(row).remove();
        return;
      }
      const moved = target.kind === "projectless" ? moveRowToChats(row, target) : moveRowToProjectList(row, target);
      if (moved) targetRowsById.set(rowId, row);
    });
    settledRefs.forEach(clearProjectMoveProjection);
    updateProjectMoveEmptyStates();
  }

  function scheduleProjectMoveProjection() {
    if (!codexMateSettings().projectMove || window.__codexProjectMoveProjectionTimer) return;
    window.__codexProjectMoveProjectionTimer = setTimeout(() => {
      if (window.__codexProjectMoveRuntimeId !== codexProjectMoveRuntimeId) return;
      window.__codexProjectMoveProjectionTimer = null;
      applyProjectMoveProjection();
    }, 80);
  }

  function visibleChatsRows() {
    const list = chatsThreadList();
    if (!list) return [];
    return Array.from(list.children).map(threadRowFromListItem).filter(Boolean).filter((row) => rowIsInChats(row));
  }

  function chatsSortNeedsCorrection(rows) {
    let previousPinned = true;
    let previousSortMs = Infinity;
    let previousKey = "\uffff";
    for (const row of rows) {
      const pinned = rowPinned(row);
      const ref = sessionRefFromRow(row);
      const sortMs = rowSortMs(row, ref);
      const key = projectMoveSessionKey(ref.session_id);
      if (previousPinned && !pinned) {
        previousPinned = false;
        previousSortMs = sortMs;
        previousKey = key;
        continue;
      }
      if (!previousPinned && pinned) return true;
      if (sortMs > previousSortMs || (sortMs === previousSortMs && key > previousKey)) return true;
      previousSortMs = sortMs;
      previousKey = key;
    }
    return false;
  }

  function reorderChatsRows(rows) {
    const list = chatsThreadList();
    if (!list || rows.length < 2) return;
    const rowItems = new Set(rows.map(rowListItem));
    const firstNonThreadItem = Array.from(list.children).find((child) => !rowItems.has(child) && !threadRowFromListItem(child));
    const orderedRows = [...rows].sort((left, right) => {
      const leftPinned = rowPinned(left);
      const rightPinned = rowPinned(right);
      if (leftPinned !== rightPinned) return leftPinned ? -1 : 1;
      const leftRef = sessionRefFromRow(left);
      const rightRef = sessionRefFromRow(right);
      const leftSortMs = rowSortMs(left, leftRef);
      const rightSortMs = rowSortMs(right, rightRef);
      if (leftSortMs !== rightSortMs) return rightSortMs - leftSortMs;
      return projectMoveSessionKey(rightRef.session_id).localeCompare(projectMoveSessionKey(leftRef.session_id));
    });
    orderedRows.forEach((row) => list.insertBefore(rowListItem(row), firstNonThreadItem || null));
    cachedSessionRowsAt = 0;
  }

  async function applyChatsSortCorrection() {
    if (!codexMateSettings().projectMove || chatsSortInFlight) return;
    const rows = visibleChatsRows();
    if (rows.length < 2) return;
    const refs = rows.map(sessionRefFromRow).filter((ref) => ref.session_id);
    const signature = refs.map((ref) => projectMoveSessionKey(ref.session_id)).join("|");
    const allRowsHaveSortMs = rows.every((row) => numericTimestamp(row.dataset.codexProjectMoveSortMs || rowListItem(row).dataset.codexProjectMoveSortMs));
    const shouldRefreshSortKeys = signature !== chatsSortSignature || !allRowsHaveSortMs || Date.now() - chatsSortLastFetchAt > chatsSortDbRefreshIntervalMs;
    if (!shouldRefreshSortKeys && !chatsSortNeedsCorrection(rows)) return;
    chatsSortInFlight = true;
    try {
      if (shouldRefreshSortKeys) {
        const result = await postJson("/thread-sort-keys", { sessions: refs }).catch(() => ({ status: "failed", sort_keys: [] }));
        chatsSortLastFetchAt = Date.now();
        const byId = new Map();
        if (result?.status === "ok" && Array.isArray(result?.sort_keys)) {
          result.sort_keys.forEach((item) => {
            const key = projectMoveSessionKey(String(item?.session_id || ""));
            if (key) byId.set(key, item);
          });
        }
        rows.forEach((row) => {
          const ref = sessionRefFromRow(row);
          const payload = byId.get(projectMoveSessionKey(ref.session_id));
          const sortMs = timestampMsFromPayload(payload) || rowSortMs(row, ref);
          row.dataset.codexProjectMoveSortMs = String(sortMs || 0);
          rowListItem(row).dataset.codexProjectMoveSortMs = String(sortMs || 0);
        });
      }
      if (chatsSortNeedsCorrection(rows)) reorderChatsRows(rows);
      chatsSortSignature = visibleChatsRows().map((row) => projectMoveSessionKey(sessionRefFromRow(row).session_id)).join("|");
    } finally {
      chatsSortInFlight = false;
    }
  }

  function scheduleChatsSortCorrection(delay = chatsSortRefreshIntervalMs) {
    if (!codexMateSettings().projectMove) return;
    if (window.__codexProjectMoveChatsSortTimer) {
      if (delay !== 0) return;
      clearTimeout(window.__codexProjectMoveChatsSortTimer);
      window.__codexProjectMoveChatsSortTimer = null;
    }
    window.__codexProjectMoveChatsSortTimer = setTimeout(() => {
      if (window.__codexProjectMoveRuntimeId !== codexProjectMoveRuntimeId) return;
      window.__codexProjectMoveChatsSortTimer = null;
      applyChatsSortCorrection().catch((error) => {
        window.__codexProjectMoveSortFailures = window.__codexProjectMoveSortFailures || [];
        window.__codexProjectMoveSortFailures.push(String(error?.stack || error));
      }).finally(() => {
        if (codexMateSettings().projectMove) scheduleChatsSortCorrection();
      });
    }, delay);
  }

  function refreshAfterProjectMove() {
    const refreshVisibleSidebar = () => {
      if (window.__codexProjectMoveRuntimeId !== codexProjectMoveRuntimeId) return;
      applyProjectMoveProjection();
      scheduleChatsSortCorrection(0);
      syncActionGroupsLayout();
    };
    refreshVisibleSidebar();
    projectMoveRefreshDelaysMs.forEach((delay) => setTimeout(refreshVisibleSidebar, delay));
  }

  async function moveSessionToProject(ref, target) {
    if (!ref.session_id) throw new Error("未找到会话 ID");
    if (!target?.path) throw new Error("目标项目路径为空");
    const result = await postJson("/move-thread-workspace", { ...ref, target_cwd: target.path });
    if (result.status !== "moved") throw new Error(result.message || "移动会话失败");
    return result;
  }

  async function moveSessionToProjectless(ref) {
    if (!ref.session_id) throw new Error("未找到会话 ID");
    const result = await postJson("/move-thread-projectless", ref);
    if (result.status !== "moved") throw new Error(result.message || "移动会话失败");
    const sortKey = await postJson("/thread-sort-key", ref).catch(() => ({}));
    return {
      ...sortKey,
      ...result,
      updated_at: result.updated_at ?? sortKey.updated_at,
      updated_at_ms: result.updated_at_ms ?? sortKey.updated_at_ms,
      created_at_ms: result.created_at_ms ?? sortKey.created_at_ms,
    };
  }

  function closeProjectMoveMenus() {
    document.querySelectorAll(`.${projectMoveOverlayClass}`).forEach((node) => node.remove());
    hideActionButtonTooltip();
  }

  function positionProjectMovePanel(panel, button) {
    const rect = button.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const left = Math.min(window.innerWidth - panelRect.width - 8, Math.max(8, rect.right - panelRect.width));
    const top = Math.min(window.innerHeight - panelRect.height - 8, Math.max(8, rect.bottom + 8));
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  async function applyProjectMove(row, ref, target) {
    try {
      const result = target.kind === "projectless" ? await moveSessionToProjectless(ref) : await moveSessionToProject(ref, target);
      const movedTarget = { ...target, sortMs: timestampMsFromPayload(result), sortMsTrusted: true };
      saveProjectMoveProjection(ref, movedTarget, movedTarget.sortMs);
      const moved = target.kind === "projectless" ? moveRowToChats(row, movedTarget) : moveRowToProjectList(row, movedTarget);
      refreshAfterProjectMove();
      const targetLabel = target.kind === "projectless" ? "普通对话" : target.label || displayProjectName(target.path);
      showToast(moved ? `已移动到${targetLabel}` : `已移动到${targetLabel}，刷新侧边栏后显示`, null);
    } catch (error) {
      showToast(`移动失败：${error?.message || error}`, null);
    } finally {
      closeProjectMoveMenus();
    }
  }

  function openProjectMoveMenuForRow(row, button, ref, event) {
    stopActionButtonEvent(row, button, event);
    closeProjectMoveMenus();
    const overlay = document.createElement("div");
    overlay.className = projectMoveOverlayClass;
    const targets = projectMoveTargets();
    const panel = document.createElement("div");
    panel.className = "codex-project-move-panel";
    panel.setAttribute("role", "menu");
    panel.innerHTML = `<div class="codex-project-move-title">移动会话</div>`;
    if (targets.length === 0) {
      const empty = document.createElement("div");
      empty.className = "codex-project-move-empty";
      empty.textContent = "没有可移动的目标";
      panel.appendChild(empty);
    }
    targets.forEach((target) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "codex-project-move-item";
      item.setAttribute("role", "menuitem");
      const current = rowIsUnderTarget(row, target);
      item.innerHTML = `
        <span class="codex-project-move-label">${escapeHtml(target.label)}</span>
        ${current ? '<span class="codex-project-move-current">当前</span>' : "<span></span>"}
        <span class="codex-project-move-path">${escapeHtml(target.description || target.path || "")}</span>
      `;
      item.addEventListener("click", (clickEvent) => {
        clickEvent.preventDefault();
        clickEvent.stopPropagation();
        clickEvent.stopImmediatePropagation?.();
        if (current) {
          showToast("这个会话已经在这里", null);
          closeProjectMoveMenus();
          return;
        }
        item.disabled = true;
        void applyProjectMove(row, ref, target);
      }, true);
      panel.appendChild(item);
    });
    overlay.appendChild(panel);
    overlay.addEventListener("click", (clickEvent) => {
      if (clickEvent.target === overlay) closeProjectMoveMenus();
    }, true);
    overlay.addEventListener("keydown", (keyEvent) => {
      if (keyEvent.key === "Escape") closeProjectMoveMenus();
    }, true);
    document.body.appendChild(overlay);
    positionProjectMovePanel(panel, button);
    panel.querySelector("button")?.focus();
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
        if (event.target === overlay || closestElement(event.target, "[data-codex-delete-cancel]")) {
          finish(false, event);
          return;
        }
        if (closestElement(event.target, "[data-codex-delete-confirm]")) {
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
        if (button.closest(`.${actionGroupClass}`) || label === "归档对话" || label === "置顶对话") return false;
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

  function actionGroupFromRow(row) {
    return row.querySelector(`.${actionGroupClass}`);
  }

  function nativeActionButtonsFromRow(row) {
    return [...row.querySelectorAll('button,[role="button"],a')]
      .filter((node) => !node.closest(`.${actionGroupClass}`))
      .filter((node) => {
        const rect = node.getBoundingClientRect();
        if (rect.width < 12 || rect.height < 12) return false;
        const label = [
          node.getAttribute("aria-label"),
          node.getAttribute("title"),
          node.dataset?.state,
          node.textContent,
        ].filter(Boolean).join(" ");
        if (/(pin|archive|置顶|归档)/i.test(label)) return true;
        const rowRect = row.getBoundingClientRect();
        return rect.left > rowRect.left + rowRect.width * 0.68;
      });
  }

  function syncActionGroupLayout(row, group) {
    if (!row || !group) return;
    const rowRect = row.getBoundingClientRect();
    const leftmostNative = nativeActionButtonsFromRow(row)
      .map((button) => button.getBoundingClientRect())
      .filter((rect) => rect.width > 0 && rect.height > 0)
      .sort((left, right) => left.left - right.left)[0];
    const gap = 8;
    const fallbackRight = 28;
    const right = leftmostNative ? Math.max(fallbackRight, Math.round(rowRect.right - leftmostNative.left + gap)) : fallbackRight;
    const groupWidth = Math.ceil(group.getBoundingClientRect().width || 58);
    group.style.setProperty("--codex-session-actions-right", `${right}px`);
    row.style.setProperty("--codex-session-title-mask", `${right + groupWidth + 12}px`);
  }

  function syncActionGroupsLayout() {
    sessionRows().forEach((row) => {
      const group = actionGroupFromRow(row);
      if (group) syncActionGroupLayout(row, group);
    });
  }

  function removeActionGroups(row) {
    row.querySelectorAll(`.${actionGroupClass}`).forEach((group) => group.remove());
  }

  function stopActionButtonEvent(row, button, event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation?.();
    releaseDeleteFocus(row, button);
  }

  function hideActionButtonTooltip() {
    document.querySelectorAll(`.${actionTooltipClass}`).forEach((node) => node.remove());
  }

  function showActionButtonTooltip(button) {
    const label = button.dataset.codexActionLabel || button.getAttribute("aria-label") || "";
    if (!label) return;
    hideActionButtonTooltip();
    const tooltip = document.createElement("div");
    tooltip.className = actionTooltipClass;
    tooltip.textContent = label;
    document.body.appendChild(tooltip);
    const buttonRect = button.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const left = Math.min(
      window.innerWidth - tooltipRect.width - 8,
      Math.max(8, buttonRect.left + buttonRect.width / 2 - tooltipRect.width / 2),
    );
    const top = Math.min(window.innerHeight - tooltipRect.height - 8, buttonRect.bottom + 8);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${Math.max(8, top)}px`;
  }

  function installActionButtonEvents(row, button, onActivate) {
    ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
      button.addEventListener(eventName, (event) => stopActionButtonEvent(row, button, event), true);
    });
    button.addEventListener("pointerenter", () => showActionButtonTooltip(button));
    button.addEventListener("pointerleave", hideActionButtonTooltip);
    button.addEventListener("focus", () => showActionButtonTooltip(button));
    button.addEventListener("blur", hideActionButtonTooltip);
    button.addEventListener("pointerup", onActivate, true);
    button.addEventListener("click", (event) => {
      hideActionButtonTooltip();
      onActivate(event);
    }, true);
  }

  function refreshActionButton(originalButton, row, onActivate) {
    if (!originalButton.isConnected) return;
    const replacement = originalButton.cloneNode(true);
    installActionButtonEvents(row, replacement, onActivate);
    originalButton.replaceWith(replacement);
  }

  function configureActionButton(button, label, icon) {
    button.setAttribute("aria-label", label);
    button.dataset.codexActionLabel = label;
    button.removeAttribute("title");
    button.textContent = icon;
  }

  function trashIconSvg() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18"></path>
        <path d="M8 6V4h8v2"></path>
        <path d="M19 6l-1 14H6L5 6"></path>
        <path d="M10 11v5"></path>
        <path d="M14 11v5"></path>
      </svg>
    `;
  }

  function configureSvgActionButton(button, label, svg) {
    button.setAttribute("aria-label", label);
    button.dataset.codexActionLabel = label;
    button.removeAttribute("title");
    button.innerHTML = svg;
  }

  function attachButton(row) {
    const settings = codexMateSettings();
    if (!settings.sessionDelete && !settings.markdownExport && !settings.projectMove) {
      removeActionGroups(row);
      row.dataset.codexDeleteRow = "false";
      return;
    }
    const existingGroup = actionGroupFromRow(row);
    const existingDeleteButton = existingGroup?.querySelector(`.${buttonClass}`);
    const existingExportButton = existingGroup?.querySelector(`.${exportButtonClass}`);
    const existingMoveButton = existingGroup?.querySelector(`.${projectMoveButtonClass}`);
    const groupReady = existingGroup?.dataset.codexActionGroupVersion === codexActionGroupVersion;
    const deleteReady = !settings.sessionDelete || existingDeleteButton?.dataset.codexDeleteVersion === codexDeleteVersion;
    const exportReady = !settings.markdownExport || existingExportButton?.dataset.codexExportVersion === codexExportVersion;
    const moveReady = !settings.projectMove || existingMoveButton?.dataset.codexProjectMoveVersion === codexProjectMoveVersion;
    const missingDelete = settings.sessionDelete && !existingDeleteButton;
    const missingExport = settings.markdownExport && !existingExportButton;
    const missingMove = settings.projectMove && !existingMoveButton;
    const unexpectedDelete = !settings.sessionDelete && !!existingDeleteButton;
    const unexpectedExport = !settings.markdownExport && !!existingExportButton;
    const unexpectedMove = !settings.projectMove && !!existingMoveButton;
    if (groupReady && deleteReady && exportReady && moveReady && !missingDelete && !missingExport && !missingMove && !unexpectedDelete && !unexpectedExport && !unexpectedMove) {
      syncActionGroupLayout(row, existingGroup);
      return;
    }
    removeActionGroups(row);
    row.dataset.codexDeleteRow = "false";
    const ref = sessionRefFromRow(row);
    if (!ref.session_id) return;
    row.dataset.codexDeleteRow = "true";
    const group = document.createElement("div");
    group.className = actionGroupClass;
    group.dataset.codexActionGroupVersion = codexActionGroupVersion;
    if (settings.projectMove) {
      const moveButton = document.createElement("button");
      moveButton.type = "button";
      moveButton.className = `${actionButtonClass} ${projectMoveButtonClass}`;
      moveButton.dataset.codexProjectMoveVersion = codexProjectMoveVersion;
      configureActionButton(moveButton, "移动会话", "↗");
      const openMoveMenu = (event) => openProjectMoveMenuForRow(row, moveButton, ref, event);
      installActionButtonEvents(row, moveButton, openMoveMenu);
      group.appendChild(moveButton);
      setTimeout(() => refreshActionButton(moveButton, row, openMoveMenu), 0);
    }
    if (settings.markdownExport) {
      const exportButton = document.createElement("button");
      exportButton.type = "button";
      exportButton.className = `${actionButtonClass} ${exportButtonClass}`;
      exportButton.dataset.codexExportVersion = codexExportVersion;
      configureActionButton(exportButton, "导出 Markdown", "⇩");
      const openExport = (event) => {
        stopActionButtonEvent(row, exportButton, event);
        void exportMarkdown(ref);
      };
      installActionButtonEvents(row, exportButton, openExport);
      group.appendChild(exportButton);
      setTimeout(() => refreshActionButton(exportButton, row, openExport), 0);
    }
    if (settings.sessionDelete) {
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = `${actionButtonClass} ${buttonClass}`;
      deleteButton.dataset.codexDeleteVersion = codexDeleteVersion;
      configureSvgActionButton(deleteButton, "删除", trashIconSvg());
      const openDeleteConfirm = (event) => openDeleteConfirmForRow(row, deleteButton, ref, event);
      installActionButtonEvents(row, deleteButton, openDeleteConfirm);
      group.appendChild(deleteButton);
      setTimeout(() => refreshActionButton(deleteButton, row, openDeleteConfirm), 0);
    }
    row.appendChild(group);
    syncActionGroupLayout(row, group);
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
    const settings = codexMateSettings();
    if (!settings.sessionDelete && !settings.markdownExport) return;
    if (row.dataset.codexArchiveDeleteRow === "true") return;
    row.dataset.codexArchiveDeleteRow = "true";
    const unarchiveButton = Array.from(row.querySelectorAll("button")).find((button) => (button.textContent || "").trim() === "取消归档");
    if (!unarchiveButton) return;
    let insertAfter = unarchiveButton;
    if (settings.markdownExport) {
      const exportButton = document.createElement("button");
      exportButton.type = "button";
      exportButton.className = "codex-archive-delete-all codex-archive-export";
      exportButton.textContent = "导出";
      ["pointerdown", "mousedown", "mouseup", "touchstart"].forEach((eventName) => {
        exportButton.addEventListener(eventName, stopArchivedButtonEvent, true);
      });
      exportButton.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();
        const ref = await resolveArchivedThread(row);
        if (!ref.session_id) {
          showToast("导出失败：未找到归档会话 ID", null);
          return;
        }
        await exportMarkdown(ref);
      }, true);
      insertAfter.insertAdjacentElement("afterend", exportButton);
      insertAfter = exportButton;
    }
    if (settings.sessionDelete) {
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
      insertAfter.insertAdjacentElement("afterend", button);
    }
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

  function finiteNonNegativeNumber(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric >= 0 ? numeric : 0;
  }

  function finiteScrollNumber(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : 0;
  }

  function locationThreadId() {
    const source = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    const match = source.match(/(?:session|conversation|thread)(?:\/|=|:|-)([A-Za-z0-9_.-]+)/i)
      || source.match(/\/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:[/?#]|$)/)
      || source.match(/\/([A-Za-z0-9_-]{24,})(?:[/?#]|$)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function threadIdVariants(sessionId) {
    if (typeof sessionId !== "string" || !sessionId.trim()) return [];
    const id = sessionId.trim();
    const bareId = id.startsWith("local:") ? id.slice("local:".length) : id;
    return Array.from(new Set([id, bareId, `local:${bareId}`].filter(Boolean)));
  }

  function validThreadScrollSessionKey(sessionId) {
    const variants = threadIdVariants(sessionId);
    const bareId = variants.find((id) => !id.startsWith("local:")) || variants[0] || "";
    if (!bareId || bareId === "__proto__" || bareId === "prototype" || bareId === "constructor") return "";
    return /^[A-Za-z0-9_.-]{8,128}$/.test(bareId) ? bareId : "";
  }

  function currentSessionRef() {
    const rows = sessionRows();
    for (const row of rows) {
      const ref = sessionRefFromRow(row);
      if (ref.session_id && isCurrentSessionRow(row, ref)) return ref;
    }
    return { session_id: locationThreadId(), title: "" };
  }

  function truncateTimelineQuestion(text) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    const chars = Array.from(normalized);
    if (chars.length <= timelineQuestionLimit) return normalized;
    return `${chars.slice(0, timelineQuestionLimit).join("")}…`;
  }

  function conversationTimelineRoot() {
    return document.querySelector(".thread-scroll-container") || document.querySelector("main") || document.querySelector('[role="main"]');
  }

  function timelineQuestionSelector() {
    return [
      '[data-message-author-role="user"]',
      '[data-testid="conversation-turn"][data-message-author-role="user"]',
      '[data-testid="conversation-turn"] [data-message-author-role="user"]',
      '[class*="user-message"]',
      '[class*="UserMessage"]',
    ].join(", ");
  }

  function nodeOrAncestorLooksLikeCodexUserBubble(node) {
    if (node.nodeType !== 1) return false;
    const className = String(node.className || "");
    if (className.includes("bg-token-foreground/5") && node.parentElement?.classList?.contains("items-end")) return true;
    const bubble = node.closest?.("[class*='bg-token-foreground/5']");
    return !!bubble?.parentElement?.classList?.contains("items-end");
  }

  function nodeLooksLikeCodexUserBubble(node) {
    if (nodeOrAncestorLooksLikeCodexUserBubble(node)) return true;
    return !!node.querySelector?.(".group.flex.w-full.flex-col.items-end.justify-end.gap-1 > [class*='bg-token-foreground/5']");
  }

  function nodeLooksLikeTimelineQuestion(node) {
    if (node.nodeType !== 1 || isExtensionUiNode(node)) return false;
    const questionSelector = timelineQuestionSelector();
    return !!node.matches?.(questionSelector) || !!node.closest?.(questionSelector) || !!node.querySelector?.(questionSelector) || nodeLooksLikeCodexUserBubble(node);
  }

  function conversationTimelineQuestionCandidates(root) {
    const explicitCandidates = Array.from(root.querySelectorAll(timelineQuestionSelector()));
    const codexUserBubbles = Array.from(root.querySelectorAll(".group.flex.w-full.flex-col.items-end.justify-end.gap-1")).flatMap((group) => {
      return Array.from(group.children).filter((child) => String(child.className || "").includes("bg-token-foreground/5"));
    });
    return [...explicitCandidates, ...codexUserBubbles];
  }

  function extractTimelineQuestionText(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll("button, svg, [aria-hidden='true'], .sr-only").forEach((child) => child.remove());
    return (clone.textContent || "").replace(/\s+/g, " ").trim();
  }

  function timelineNodeId(node) {
    if (!node.__codexConversationTimelineNodeId) {
      window.__codexConversationTimelineNodeCounter += 1;
      node.__codexConversationTimelineNodeId = String(window.__codexConversationTimelineNodeCounter);
    }
    return node.__codexConversationTimelineNodeId;
  }

  function visibleTimelineNode(node) {
    if (!node.isConnected) return false;
    const style = getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 || rect.height > 0 || !!node.textContent?.trim();
  }

  function conversationTimelineQuestions() {
    const root = conversationTimelineRoot();
    if (!root?.matches?.(".thread-scroll-container, main, [role='main']")) return [];
    const seen = new Set();
    return conversationTimelineQuestionCandidates(root).flatMap((node) => {
      if (node.closest("[data-app-action-sidebar-thread-id]")) return [];
      if (isExtensionUiNode(node)) return [];
      const target = node.closest('[data-testid="conversation-turn"]') || node;
      if (seen.has(target)) return [];
      seen.add(target);
      if (!visibleTimelineNode(target)) return [];
      const text = extractTimelineQuestionText(node);
      if (!text) return [];
      return [{ node: target, text, nodeId: timelineNodeId(target) }];
    });
  }

  function timelineScrollerViewportTop(scroller) {
    if (scroller === document.scrollingElement || scroller === document.documentElement || scroller === document.body) return 0;
    return scroller.getBoundingClientRect().top;
  }

  function timelineScrollableHeight(scroller) {
    return Math.max(1, scroller.scrollHeight - scroller.clientHeight);
  }

  function timelineRawMarkerTop(question, scroller) {
    const scrollOffset = scroller.scrollTop + question.node.getBoundingClientRect().top - timelineScrollerViewportTop(scroller);
    const percent = (scrollOffset / timelineScrollableHeight(scroller)) * 100;
    return Math.max(timelineMinTopPercent, Math.min(timelineMaxTopPercent, percent));
  }

  function timelineMarkerTops(questions, scroller) {
    if (questions.length <= 1) return [50];
    const minGap = Math.min(timelineMaxMarkerGapPercent, (timelineMaxTopPercent - timelineMinTopPercent) / Math.max(questions.length - 1, 1));
    const tops = questions.map((question) => timelineRawMarkerTop(question, scroller));
    for (let index = 1; index < tops.length; index += 1) {
      tops[index] = Math.max(tops[index], tops[index - 1] + minGap);
    }
    for (let index = tops.length - 1; index >= 0; index -= 1) {
      const maxForIndex = timelineMaxTopPercent - ((tops.length - 1 - index) * minGap);
      tops[index] = Math.min(tops[index], maxForIndex);
    }
    return tops.map((top) => Math.max(timelineMinTopPercent, Math.min(timelineMaxTopPercent, top)));
  }

  function removeConversationTimeline() {
    document.querySelectorAll(`.${timelineClass}`).forEach((node) => node.remove());
  }

  function nearestTimelineScroller(node) {
    for (let current = node?.parentElement; current; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (/(auto|scroll)/.test(style.overflowY) && current.scrollHeight > current.clientHeight) return current;
    }
    return document.querySelector(".thread-scroll-container") || document.scrollingElement || document.documentElement;
  }

  function scrollTimelineTarget(node) {
    const scroller = nearestTimelineScroller(node);
    const nodeRect = node.getBoundingClientRect();
    const nextTop = scroller.scrollTop + nodeRect.top - timelineScrollerViewportTop(scroller) - (scroller.clientHeight / 2) + (nodeRect.height / 2);
    scroller.scrollTo({ top: nextTop, behavior: "smooth" });
  }

  function highlightTimelineTarget(node) {
    node.classList.remove(timelineTargetClass);
    void node.offsetWidth;
    node.classList.add(timelineTargetClass);
    clearTimeout(node.__codexConversationTimelineHighlightTimer);
    node.__codexConversationTimelineHighlightTimer = setTimeout(() => {
      node.classList.remove(timelineTargetClass);
    }, 1300);
  }

  function createConversationTimelineMarker(question) {
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = timelineMarkerClass;
    marker.style.top = `${question.markerTop}%`;
    marker.setAttribute("aria-label", `跳转到：${truncateTimelineQuestion(question.text)}`);
    const tooltip = document.createElement("span");
    tooltip.className = timelineTooltipClass;
    tooltip.id = `codex-conversation-timeline-tooltip-${question.nodeId}`;
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = truncateTimelineQuestion(question.text);
    marker.setAttribute("aria-describedby", tooltip.id);
    marker.appendChild(tooltip);
    const activateMarker = (event) => {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation?.();
      document.querySelectorAll(`.${timelineMarkerClass}.codex-conversation-timeline-marker-active`).forEach((node) => {
        node.classList.remove("codex-conversation-timeline-marker-active");
      });
      marker.classList.add("codex-conversation-timeline-marker-active");
      scrollTimelineTarget(question.node);
      highlightTimelineTarget(question.node);
    };
    marker.addEventListener("pointerup", activateMarker, true);
    marker.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") activateMarker(event);
    }, true);
    return marker;
  }

  function prepareTimelineQuestions(questions) {
    if (questions.length === 0) return [];
    const scroller = nearestTimelineScroller(questions[0].node);
    const tops = timelineMarkerTops(questions, scroller);
    return questions.map((question, index) => ({ ...question, markerTop: Number(tops[index].toFixed(3)) }));
  }

  function timelineSignature(questions) {
    return questions.map((question) => `${question.nodeId}:${Math.round(question.markerTop * 10)}:${truncateTimelineQuestion(question.text)}`).join("|");
  }

  function refreshConversationTimeline() {
    if (!codexMateSettings().conversationTimeline) {
      removeConversationTimeline();
      return;
    }
    const questions = prepareTimelineQuestions(conversationTimelineQuestions());
    if (questions.length === 0) {
      removeConversationTimeline();
      return;
    }
    const signature = timelineSignature(questions);
    const existing = document.querySelector(`.${timelineClass}`);
    if (
      existing?.dataset.codexConversationTimelineVersion === codexConversationTimelineVersion &&
      existing?.dataset.codexConversationTimelineSignature === signature
    ) {
      return;
    }
    removeConversationTimeline();
    const container = document.createElement("div");
    container.className = timelineClass;
    container.dataset.codexConversationTimelineVersion = codexConversationTimelineVersion;
    container.dataset.codexConversationTimelineSignature = signature;
    const track = document.createElement("div");
    track.className = timelineTrackClass;
    container.appendChild(track);
    questions.forEach((question) => {
      container.appendChild(createConversationTimelineMarker(question));
    });
    document.body.appendChild(container);
  }

  function readThreadScrollEntries() {
    if (window.__codexMateThreadScrollEntries && typeof window.__codexMateThreadScrollEntries === "object") {
      return { ...window.__codexMateThreadScrollEntries };
    }
    try {
      const parsed = JSON.parse(localStorage.getItem(codexThreadScrollKey) || "{}");
      const rawEntries = parsed?.version === codexThreadScrollVersion && parsed?.entries && typeof parsed.entries === "object"
        ? parsed.entries
        : {};
      const entries = Object.create(null);
      Object.entries(rawEntries).forEach(([key, value]) => {
        const safeKey = validThreadScrollSessionKey(key);
        if (!safeKey || !value || typeof value !== "object") return;
        entries[safeKey] = {
          top: finiteScrollNumber(value.top),
          scrollHeight: finiteNonNegativeNumber(value.scrollHeight),
          clientHeight: finiteNonNegativeNumber(value.clientHeight),
          at: finiteNonNegativeNumber(value.at),
        };
      });
      window.__codexMateThreadScrollEntries = entries;
      return { ...entries };
    } catch {
      window.__codexMateThreadScrollEntries = Object.create(null);
      return {};
    }
  }

  function writeThreadScrollEntries(entries) {
    const pruned = Object.create(null);
    Object.entries(entries || {})
      .sort((left, right) => finiteNonNegativeNumber(right[1]?.at) - finiteNonNegativeNumber(left[1]?.at))
      .slice(0, codexThreadScrollMaxEntries)
      .forEach(([key, value]) => {
        const safeKey = validThreadScrollSessionKey(key);
        if (safeKey) pruned[safeKey] = value;
      });
    window.__codexMateThreadScrollEntries = pruned;
    localStorage.setItem(codexThreadScrollKey, JSON.stringify({ version: codexThreadScrollVersion, entries: pruned }));
  }

  function currentThreadScroller() {
    const explicit = document.querySelector(".thread-scroll-container");
    if (explicit?.isConnected) return explicit;
    const root = conversationTimelineRoot();
    if (!root?.isConnected) return document.scrollingElement || document.documentElement;
    const style = getComputedStyle(root);
    if (/(auto|scroll)/.test(style.overflowY) && root.scrollHeight > root.clientHeight) return root;
    return nearestTimelineScroller(root);
  }

  function threadScrollRuntime() {
    if (!window.__codexMateThreadScrollRuntime || typeof window.__codexMateThreadScrollRuntime !== "object") {
      window.__codexMateThreadScrollRuntime = {
        activeSessionId: "",
        activeScroller: null,
        scrollListener: null,
        scrollListenerUsesWindow: false,
        lastSavedTop: -1,
        lastSavedHeight: -1,
        lastSavedClientHeight: -1,
        applyingRestore: false,
        userScrollIntentUntil: 0,
      };
    }
    return window.__codexMateThreadScrollRuntime;
  }

  function clearThreadScrollRestoreTimers() {
    (window.__codexMateThreadScrollRestoreTimers || []).forEach((timer) => clearTimeout(timer));
    window.__codexMateThreadScrollRestoreTimers = [];
  }

  function userScrollIntentActive() {
    return finiteNonNegativeNumber(threadScrollRuntime().userScrollIntentUntil) > Date.now();
  }

  function threadScrollTargetTop(scroller, targetTop) {
    const max = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
    return Math.max(0, Math.min(max, finiteScrollNumber(targetTop)));
  }

  function bindThreadScrollListener(scroller) {
    const runtime = threadScrollRuntime();
    const nextUsesWindow = !scroller || scroller === document.scrollingElement || scroller === document.documentElement || scroller === document.body;
    if (runtime.scrollListener && runtime.scrollListenerVersion !== codexThreadScrollListenerVersion) {
      const oldTarget = runtime.scrollListenerUsesWindow ? window : runtime.activeScroller;
      oldTarget?.removeEventListener?.("scroll", runtime.scrollListener, true);
      runtime.scrollListener = null;
    }
    runtime.scrollListener = runtime.scrollListener || (() => scheduleThreadScrollSave());
    runtime.scrollListenerVersion = codexThreadScrollListenerVersion;
    if (runtime.activeScroller === scroller && runtime.scrollListenerUsesWindow === nextUsesWindow) return;
    const oldTarget = runtime.scrollListenerUsesWindow ? window : runtime.activeScroller;
    oldTarget?.removeEventListener?.("scroll", runtime.scrollListener, true);
    runtime.activeScroller = scroller;
    runtime.scrollListenerUsesWindow = nextUsesWindow;
    if (!scroller || !codexMateSettings().threadScrollRestore) return;
    const target = nextUsesWindow ? window : scroller;
    target.addEventListener("scroll", runtime.scrollListener, true);
  }

  function saveThreadScrollPositionNow(sessionId = threadScrollRuntime().activeSessionId, scroller = threadScrollRuntime().activeScroller) {
    if (!codexMateSettings().threadScrollRestore) return;
    const runtime = threadScrollRuntime();
    const key = validThreadScrollSessionKey(sessionId);
    if (!key || !scroller || runtime.applyingRestore) return;
    const snapshot = {
      top: finiteScrollNumber(scroller.scrollTop),
      scrollHeight: finiteNonNegativeNumber(scroller.scrollHeight),
      clientHeight: finiteNonNegativeNumber(scroller.clientHeight),
      at: Date.now(),
    };
    if (Math.abs(runtime.lastSavedTop - snapshot.top) < 2 && runtime.lastSavedHeight === snapshot.scrollHeight && runtime.lastSavedClientHeight === snapshot.clientHeight) return;
    const entries = readThreadScrollEntries();
    entries[key] = snapshot;
    writeThreadScrollEntries(entries);
    runtime.lastSavedTop = snapshot.top;
    runtime.lastSavedHeight = snapshot.scrollHeight;
    runtime.lastSavedClientHeight = snapshot.clientHeight;
  }

  function scheduleThreadScrollSave() {
    if (!codexMateSettings().threadScrollRestore || window.__codexMateThreadScrollSaveTimer) return;
    window.__codexMateThreadScrollSaveTimer = setTimeout(() => {
      window.__codexMateThreadScrollSaveTimer = null;
      saveThreadScrollPositionNow();
    }, codexThreadScrollSaveThrottleMs);
  }

  function restoreThreadScrollPosition(sessionId) {
    const runtime = threadScrollRuntime();
    const key = validThreadScrollSessionKey(sessionId);
    if (!codexMateSettings().threadScrollRestore || !key || runtime.activeSessionId !== key || userScrollIntentActive()) return;
    const entry = readThreadScrollEntries()[key];
    if (!entry) return;
    const scroller = currentThreadScroller();
    if (!scroller) return;
    bindThreadScrollListener(scroller);
    const targetTop = threadScrollTargetTop(scroller, entry.top);
    if (Math.abs(scroller.scrollTop - targetTop) <= 1) return;
    runtime.applyingRestore = true;
    try {
      if (typeof scroller.scrollTo === "function") {
        scroller.scrollTo({ top: targetTop, behavior: "auto" });
      } else {
        scroller.scrollTop = targetTop;
      }
    } finally {
      runtime.applyingRestore = false;
    }
    runtime.lastSavedTop = targetTop;
    runtime.lastSavedHeight = finiteNonNegativeNumber(scroller.scrollHeight);
    runtime.lastSavedClientHeight = finiteNonNegativeNumber(scroller.clientHeight);
  }

  function scheduleThreadScrollRestore(sessionId) {
    clearThreadScrollRestoreTimers();
    const key = validThreadScrollSessionKey(sessionId);
    if (!codexMateSettings().threadScrollRestore || !key || userScrollIntentActive() || !readThreadScrollEntries()[key]) return;
    const restoreRevision = (window.__codexMateThreadScrollRestoreRevision || 0) + 1;
    window.__codexMateThreadScrollRestoreRevision = restoreRevision;
    window.__codexMateThreadScrollRestoreTimers = codexThreadScrollRestoreDelaysMs.map((delay) => setTimeout(() => {
      if (window.__codexMateThreadScrollRestoreRevision !== restoreRevision) return;
      restoreThreadScrollPosition(key);
    }, delay));
  }

  function syncThreadScrollState(forceRestore = false) {
    const runtime = threadScrollRuntime();
    const nextSessionId = validThreadScrollSessionKey(currentSessionRef().session_id);
    if (!nextSessionId) return;
    if (!codexMateSettings().threadScrollRestore) {
      bindThreadScrollListener(null);
      clearThreadScrollRestoreTimers();
      runtime.activeSessionId = nextSessionId;
      return;
    }
    const nextScroller = currentThreadScroller();
    bindThreadScrollListener(nextScroller);
    if (runtime.activeSessionId !== nextSessionId) {
      runtime.lastSavedTop = -1;
      runtime.lastSavedHeight = -1;
      runtime.lastSavedClientHeight = -1;
      runtime.activeSessionId = nextSessionId;
      runtime.userScrollIntentUntil = 0;
      scheduleThreadScrollRestore(nextSessionId);
      return;
    }
    if (forceRestore && !userScrollIntentActive()) scheduleThreadScrollRestore(nextSessionId);
  }

  function markThreadScrollUserIntent(event) {
    if (!codexMateSettings().threadScrollRestore) return;
    const scroller = threadScrollRuntime().activeScroller || currentThreadScroller();
    if (!scroller) return;
    const target = event?.target;
    if (target && target !== document && target !== window && !scroller.contains?.(target) && target !== scroller) return;
    threadScrollRuntime().userScrollIntentUntil = Date.now() + codexThreadScrollUserIntentWindowMs;
    clearThreadScrollRestoreTimers();
  }

  function installThreadScrollUserIntentCapture() {
    if (window.__codexMateThreadScrollUserIntentInstalled === codexThreadScrollUserIntentVersion) return;
    document.removeEventListener("wheel", window.__codexMateThreadScrollWheelIntentHandler, true);
    document.removeEventListener("touchmove", window.__codexMateThreadScrollTouchIntentHandler, true);
    document.removeEventListener("keydown", window.__codexMateThreadScrollKeyIntentHandler, true);
    window.__codexMateThreadScrollWheelIntentHandler = (event) => markThreadScrollUserIntent(event);
    window.__codexMateThreadScrollTouchIntentHandler = (event) => markThreadScrollUserIntent(event);
    window.__codexMateThreadScrollKeyIntentHandler = (event) => {
      if (event.target?.closest?.("input, textarea, select, [contenteditable='true'], [contenteditable='']")) return;
      if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " ", "Spacebar"].includes(event.key)) markThreadScrollUserIntent(event);
    };
    document.addEventListener("wheel", window.__codexMateThreadScrollWheelIntentHandler, { capture: true, passive: true });
    document.addEventListener("touchmove", window.__codexMateThreadScrollTouchIntentHandler, { capture: true, passive: true });
    document.addEventListener("keydown", window.__codexMateThreadScrollKeyIntentHandler, true);
    window.__codexMateThreadScrollUserIntentInstalled = codexThreadScrollUserIntentVersion;
  }

  function installThreadScrollNavigationCapture() {
    document.removeEventListener("pointerdown", window.__codexMateThreadScrollNavigationHandler, true);
    document.removeEventListener("click", window.__codexMateThreadScrollClickNavigationHandler, true);
    const handler = (event) => {
      if (!codexMateSettings().threadScrollRestore) return;
      const row = event.target?.closest?.("[data-app-action-sidebar-thread-id]");
      if (!row) return;
      saveThreadScrollPositionNow();
      scheduleThreadScrollRestore(sessionRefFromRow(row).session_id);
    };
    window.__codexMateThreadScrollNavigationHandler = handler;
    window.__codexMateThreadScrollClickNavigationHandler = handler;
    document.addEventListener("pointerdown", handler, true);
    document.addEventListener("click", handler, true);
  }

  function installThreadScrollRouteHooks() {
    if (window.__codexMateThreadScrollRouteHooksInstalled === codexThreadScrollRouteHooksVersion) return;
    window.__codexMateThreadScrollRouteHooksInstalled = codexThreadScrollRouteHooksVersion;
    window.__codexMateThreadScrollOriginals = window.__codexMateThreadScrollOriginals || {};
    const originals = window.__codexMateThreadScrollOriginals;
    ["pushState", "replaceState"].forEach((method) => {
      const original = originals[`history_${method}`] || history[method];
      originals[`history_${method}`] = original;
      if (typeof original !== "function") return;
      history[method] = function codexMateThreadScrollPatchedHistory(...args) {
        saveThreadScrollPositionNow();
        const result = original.apply(this, args);
        setTimeout(() => syncThreadScrollState(true), 0);
        return result;
      };
    });
    window.removeEventListener("popstate", window.__codexMateThreadScrollPopStateHandler, true);
    window.removeEventListener("hashchange", window.__codexMateThreadScrollHashChangeHandler, true);
    document.removeEventListener("visibilitychange", window.__codexMateThreadScrollVisibilityHandler, true);
    window.__codexMateThreadScrollPopStateHandler = () => {
      saveThreadScrollPositionNow();
      setTimeout(() => syncThreadScrollState(true), 0);
    };
    window.__codexMateThreadScrollHashChangeHandler = window.__codexMateThreadScrollPopStateHandler;
    window.__codexMateThreadScrollVisibilityHandler = () => {
      if (document.visibilityState === "hidden") saveThreadScrollPositionNow();
    };
    window.addEventListener("popstate", window.__codexMateThreadScrollPopStateHandler, true);
    window.addEventListener("hashchange", window.__codexMateThreadScrollHashChangeHandler, true);
    document.addEventListener("visibilitychange", window.__codexMateThreadScrollVisibilityHandler, true);
  }

  function scanLightweight() {
    installStyle();
    installCodexMateMenu();
    installDeleteButtonEventDelegation();
    installThreadScrollNavigationCapture();
    installThreadScrollUserIntentCapture();
    installThreadScrollRouteHooks();
  }

  function scanDeferred() {
    enablePluginEntry();
    unblockPluginInstallButtons();
    sessionRows().forEach(tryAttachButton);
    applyProjectMoveProjection();
    scheduleProjectMoveProjection();
    scheduleChatsSortCorrection(0);
    syncActionGroupsLayout();
    updateDeleteButtonOffsets();
    archivedPageRows().forEach(attachArchivedPageDeleteButton);
    installArchivedDeleteAllButton();
    refreshConversationTimeline();
    syncThreadScrollState();
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
    return !!node?.closest?.(`.codex-delete-toast, .codex-delete-confirm-overlay, .codex-mate-modal-overlay, .${projectMoveOverlayClass}, .${actionTooltipClass}, .${timelineClass}, #codex-mate-menu`);
  }

  const scanRelevantSelector = '[data-app-action-sidebar-thread-id], [data-app-action-sidebar-project-row], [data-app-action-sidebar-project-list-id], [data-codex-project-move-injected-list], [data-codex-archive-page-row="true"], [data-codex-archive-delete-all], .app-header-tint, button[aria-label="已归档对话"], button[aria-label="Archived conversations"], button:disabled.w-full.justify-center, [role="button"][aria-disabled="true"].cursor-not-allowed, [data-message-author-role="user"], [data-testid="conversation-turn"]';

  function isScanRelevantNode(node) {
    if (node.nodeType !== 1) return false;
    if (isExtensionUiNode(node)) return false;
    return !!node.matches?.(scanRelevantSelector) || !!node.closest?.(scanRelevantSelector) || !!node.querySelector?.(scanRelevantSelector);
  }

  function isChatContentMutation(mutation) {
    const target = mutation.target;
    if (target?.closest?.('[data-message-author-role], [data-testid="conversation-turn"], main .prose')) {
      const changedNodes = [...Array.from(mutation.addedNodes), ...Array.from(mutation.removedNodes)];
      if (changedNodes.some(nodeLooksLikeTimelineQuestion)) return false;
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

  const initialAuthModeStatusCheck = checkCodexMateAuthModeStatus();
  scan();
  void initialAuthModeStatusCheck.finally(scan);
  window.__codexMateObserver?.disconnect();
  window.__codexMateObserver = new MutationObserver(scheduleScan);
  window.__codexMateObserver.observe(document.body || document.documentElement, { childList: true, subtree: true });
})();
