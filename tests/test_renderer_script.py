import subprocess
from pathlib import Path


def test_renderer_script_exists_and_parses_with_node():
    script = Path("codex_mate/inject/renderer-inject.js")
    assert script.exists()
    result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_renderer_script_contains_hover_delete_contract():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "codex-delete-button" in text
    assert "MutationObserver" in text
    assert "confirmDelete" in text
    assert "/delete" in text
    assert "/undo" in text


def test_renderer_script_contains_update_check_contract():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "检查更新" in text
    assert "一键更新" in text
    assert "data-codex-mate-check-update" in text
    assert "data-codex-mate-run-update" in text
    assert "data-codex-mate-update-status" in text
    assert 'postJson("/check-update", {})' in text
    assert 'postJson("/update", {})' in text
    assert "renderUpdateState" in text
    assert "withTimeout" in text
    assert "finally" in text
    assert "检查更新超时" in text
    assert "更新超时" in text
    assert "retryableUpdateResult" in text
    assert 'result?.status === "failed"' in text
    assert 'can_update: true' in text


def test_renderer_script_supports_codex_sidebar_thread_attributes():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("function sessionRows")
    end = text.index("\n\n  function archivePageHintVisible", start)
    session_rows_code = text[start:end]
    assert "data-app-action-sidebar-thread-id" in session_rows_code
    assert "data-thread-title" in text
    assert "a[href*='session']" not in session_rows_code
    assert "conversation" not in session_rows_code
    assert "thread" not in session_rows_code.replace("data-app-action-sidebar-thread-id", "")
    assert "hasSessionHint" not in session_rows_code


def test_renderer_script_positions_session_action_group_without_affecting_layout():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "codex-session-actions" in text
    assert "codex-session-action-button" in text
    assert "position: absolute" in text
    assert "right: var(--codex-session-actions-right, 28px)" in text
    assert "top: 50%" in text
    assert "transform: translateY(-50%)" in text
    assert "width: 26px" in text
    assert "height: 26px" in text
    assert "font: 14px/1 system-ui" in text
    assert "border-radius: 6px" in text
    assert "aria-label" in text
    start = text.index("function attachButton")
    end = text.index("\n\n  function tryAttachButton", start)
    attach_button_code = text[start:end]
    assert "configureSvgActionButton(deleteButton, \"删除\", trashIconSvg())" in attach_button_code
    assert "configureActionButton(exportButton, \"导出 Markdown\", \"⇩\")" in attach_button_code
    assert "codex-delete-icon" not in attach_button_code




def test_renderer_script_enables_plugin_entry_for_api_key_users():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("function pluginEntryButton")
    end = text.index("\n\n  function unblockPluginInstallButtons", start)
    plugin_entry_code = text[start:end]
    assert "enablePluginEntry" in plugin_entry_code
    assert "pluginEntryButton" in plugin_entry_code
    assert "nav[role=\"navigation\"] button.h-token-nav-row.w-full" in plugin_entry_code
    assert "svg path[d^=\"M7.94562 14.0277\"]" in plugin_entry_code
    assert "document.querySelectorAll(\"button\")" not in plugin_entry_code
    assert "disabled = false" in plugin_entry_code
    assert "removeAttribute(\"disabled\")" in plugin_entry_code
    assert "setAuthMethod(\"chatgpt\")" in text
    assert "插件 - 已解锁" in plugin_entry_code
    assert "Plugins - Unlocked" in plugin_entry_code
    assert "labelUnlockedPluginEntry" in plugin_entry_code
    assert "childNodes" in plugin_entry_code
    assert "node.nodeType === 3" in plugin_entry_code
    assert "labelTextNode.nodeValue" in plugin_entry_code
    assert ".textContent = /^Plugins" not in plugin_entry_code
    assert "__reactFiber" in text
    assert "/skills/plugins" not in text
    assert "skillProps.onClick" not in text


def test_renderer_script_unblocks_connector_unavailable_plugin_install_buttons_without_full_body_text_scan():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("function pluginInstallCandidates")
    end = text.index("\n  let cachedSessionRows", start)
    plugin_unlock_code = text[start:end]
    assert "unblockPluginInstallButtons" in plugin_unlock_code
    assert "pluginInstallCandidates" in plugin_unlock_code
    assert "button:disabled.w-full.justify-center" in plugin_unlock_code
    assert "[role=\"button\"][aria-disabled=\"true\"].cursor-not-allowed" in plugin_unlock_code
    assert "document.body.textContent" not in plugin_unlock_code
    assert "button.disabled = false" in plugin_unlock_code
    assert "removeAttribute(\"aria-disabled\")" in plugin_unlock_code
    assert "labelForcedInstallButton" in plugin_unlock_code
    assert "强制安装" in plugin_unlock_code


def test_renderer_script_debounces_mutation_observer_scan():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "scanLightweight" in text
    assert "scanDeferred" in text
    assert "runScanStep" in text
    assert "codexMateScanFailures" in text
    assert "runScanStep(scanLightweight)" in text
    assert "requestAnimationFrame(() => runScanStep(scanDeferred))" in text
    assert "if (window.__codexMateScanPending) return" in text
    assert "setTimeout(runScheduledScan, 200)" in text
    assert "setTimeout(() => runScanStep(scanDeferred), 50)" not in text
    assert "codexMateAttachButtonFailures" in text
    assert "tryAttachButton" in text
    assert "sessionRows().forEach(tryAttachButton)" in text
    assert "sessionRows().forEach(attachButton)" not in text
    assert "new MutationObserver(scheduleScan)" in text
    assert "new MutationObserver(scan)" not in text
    assert "scan();" in text
    assert "  scan();\n  void initialAuthModeStatusCheck.finally(scan);\n  window.__codexMateObserver" in text


def test_renderer_script_ignores_chat_content_mutations_before_scheduling_scan():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("function isExtensionUiNode")
    end = text.index("\n\n  function runScheduledScan", start)
    should_schedule_code = text[start:end]
    assert "isChatContentMutation" in should_schedule_code
    assert "data-message-author-role" in should_schedule_code
    assert "data-testid=\"conversation-turn\"" in should_schedule_code
    assert "main .prose" in should_schedule_code
    assert "if (isChatContentMutation(mutation)) return false" in should_schedule_code
    should_start = text.index("function shouldScheduleScan")
    should_end = text.index("\n\n  function runScheduledScan", should_start)
    should_schedule_only = text[should_start:should_end]
    assert "node.nodeType === 1 && !isExtensionUiNode(node)" in should_schedule_only
    assert "Array.from(mutation.addedNodes).some(isScanRelevantNode)" not in should_schedule_only
    assert "data-app-action-sidebar-thread-id" in should_schedule_code
    assert "app-header-tint" in should_schedule_code


def test_renderer_script_chat_filter_keeps_relevant_node_escape_hatch():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("const scanRelevantSelector")
    end = text.index("\n\n  function isChatContentMutation", start)
    relevant_code = text[start:end]
    assert "node.matches?.(scanRelevantSelector)" in relevant_code
    assert "node.querySelector?.(scanRelevantSelector)" in relevant_code
    assert "button[aria-label=\"已归档对话\"]" in relevant_code
    assert "button:disabled.w-full.justify-center" in relevant_code
    assert "[role=\"button\"][aria-disabled=\"true\"].cursor-not-allowed" in relevant_code


def test_renderer_script_clears_focus_and_removes_deleted_rows():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "removeDeletedRow(row, button, ref)" in text
    assert "function releaseDeleteFocus" in text
    assert "releaseDeleteFocus(row, button)" in text
    assert "button.blur()" in text
    assert "document.activeElement.blur()" in text
    assert "row.remove()" in text
    assert "row.style.display = \"none\"" not in text


def test_renderer_script_uses_in_page_confirm_and_stops_early_pointer_events():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "confirm(" not in text
    assert "codex-delete-confirm-overlay" in text
    assert "escapeHtml(title)" in text
    assert "stopImmediatePropagation" in text
    assert "\"pointerdown\", \"mousedown\", \"mouseup\", \"touchstart\"" in text


def test_renderer_script_reloads_after_deleting_current_session():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "isCurrentSessionRow" in text
    assert "window.location.href.includes(ref.session_id)" in text
    assert "window.location.reload()" in text


def test_renderer_script_toast_does_not_capture_page_interactions():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "z-index: 2147483000" in text
    assert "pointer-events: none" in text
    assert "pointer-events: auto" in text
def test_renderer_script_sidebar_delete_opens_on_pointerup_when_click_is_unreliable():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "openDeleteConfirm" in text
    assert "codexDeleteVersion = \"6\"" in text
    assert "codexExportVersion = \"1\"" in text
    assert "existingGroup?.querySelector" in text
    assert "removeActionGroups(row)" in text
    assert "row.dataset.codexDeleteRow = \"false\"" in text
    assert "installDeleteButtonEventDelegation" in text
    assert "codexMateDocumentDeleteHandler" in text
    assert "document.addEventListener(\"pointerup\", handler, true)" in text
    assert "document.addEventListener(\"click\", handler, true)" in text
    assert "button.addEventListener(\"pointerup\", onActivate, true)" in text


    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "updateDeleteButtonOffsets" in text
    assert "codexDeleteStyleVersion = \"15\"" in text
    assert "right: max(66px, var(--codex-session-actions-right, 28px))" in text
    assert "确认" in text
    assert "归档对话" in text
    assert "button.getAttribute(\"aria-label\")" in text
    assert "button.closest(`.${actionGroupClass}`)" in text


def test_renderer_script_uses_theme_adaptive_sidebar_action_colors():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "--codex-mate-action-color" in text
    assert "--codex-mate-action-hover-color" in text
    assert "--codex-mate-action-hover-bg" in text
    assert "--codex-mate-popover-bg" in text
    assert "--codex-mate-popover-fg" in text
    assert "--codex-mate-popover-muted" in text
    assert "--codex-mate-control-bg" in text
    assert "--codex-mate-card-bg" in text
    assert "--codex-mate-input-bg" in text
    assert "prefers-color-scheme: dark" in text
    assert "html.electron-light" in text
    assert "html.electron-dark" in text
    assert '[data-theme="dark"]' in text
    assert "--codex-mate-popover-bg: var(--main-surface-primary" not in text
    assert "--codex-mate-popover-bg: var(--bg-primary" not in text
    assert "color: var(--codex-mate-action-color)" in text
    assert "background: var(--codex-mate-action-hover-bg)" in text
    assert "color: var(--codex-mate-popover-muted)" in text
    assert "background: var(--codex-mate-popover-bg)" in text
    assert "color: var(--codex-mate-popover-fg)" in text


def test_renderer_script_uses_theme_adaptive_modal_colors():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index(".codex-mate-modal-content")
    end = text.index(".codex-mate-row", start)
    modal_css = text[start:end]

    assert "color-scheme: light" in modal_css
    assert "background: var(--codex-mate-popover-bg)" in modal_css
    assert "color: var(--codex-mate-popover-fg)" in modal_css
    assert "border: 1px solid var(--codex-mate-popover-border)" in modal_css
    assert "color: var(--codex-mate-popover-muted)" in modal_css
    assert "background: var(--codex-mate-card-bg)" in modal_css
    assert "background: var(--codex-mate-control-bg)" in modal_css
    assert "background: var(--codex-mate-input-bg)" in modal_css
    assert "color: var(--codex-mate-input-fg)" in modal_css
    assert "border: 1px solid var(--codex-mate-input-border)" in modal_css
    assert "rgba(255,255,255,.12)" not in modal_css
    assert "background: #2b2b2b" not in modal_css
    assert "color: #f3f4f6" not in modal_css


    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    archive_visible_start = text.index("function archivedPageVisible")
    archive_visible_end = text.index("\n\n  function sessionRefFromRow", archive_visible_start)
    archive_visible_code = text[archive_visible_start:archive_visible_end]
    assert "archivePageHintVisible" in text
    assert "button[aria-label=\"已归档对话\"]" in text
    assert "button[aria-label=\"Archived conversations\"]" in text
    assert "bg-token-list-hover-background" in text
    assert "archivedPageVisible" in text
    assert "document.body.textContent" not in archive_visible_code
    assert "archivedSessionRows" in text
    assert "archivedPageRows" in text
    assert "installArchivedDeleteAllButton" in text
    assert "if (!archivePageHintVisible()) return []" in text
    assert "if (!archivePageHintVisible())" in text
    assert "删除全部归档" in text
    assert "deleteArchivedSessions" in text
    assert "attachArchivedPageDeleteButton" in text
    assert "resolveArchivedThread" in text
    assert "stopArchivedButtonEvent" in text
    assert "[\"pointerdown\", \"mousedown\", \"mouseup\", \"touchstart\"].forEach((eventName) => {\n      button.addEventListener(eventName, stopArchivedButtonEvent, true);" in text
    assert "pointerup" in text
    assert "button.addEventListener(\"pointerup\", openArchivedDeleteAllConfirm, true)" in text
    assert "archivedRefFromRow(row)" in text
    assert "reactArchivedThreadFromNode" in text
    assert "archivedThreadFromRow" in text
    assert "props.archivedThread?.id" in text
    assert "archivedThread.id || archivedThread.sessionId" in text
    assert "replace(/\\d{4}年\\d{1,2}月\\d{1,2}日.*$/, \"\")" in text
    assert "const titleMatches = sessionRows().map(sessionRefFromRow)" not in text
    assert "document.querySelectorAll(\"[data-codex-archive-delete-all]\").forEach((node) => node.remove())" not in text
    assert "const existingButton = document.querySelector(\"[data-codex-archive-delete-all]\")" in text
    assert "if (existingButton?.dataset.codexArchiveDeleteAllVersion === codexArchiveDeleteAllVersion) return" in text
    assert "existingButton?.remove()" in text
    assert "button.dataset.codexArchiveDeleteAllVersion = codexArchiveDeleteAllVersion" in text
    assert "data-codex-archive-delete-all" in text
    assert "codex-archive-action-bar" in text
    assert "codexDeleteStyleVersion" in text
    assert "style.dataset.codexDeleteStyleVersion" in text
    assert "position: fixed" in text
    assert "archiveTitleContainer" in text
    assert "element.getBoundingClientRect().x > 350" in text
    assert "已归档对话" in text
    assert "insertAdjacentElement(\"afterend\", button)" in text
    assert "maxWidth: \"fit-content\"" in text
    assert "alignSelf: \"flex-start\"" in text
    assert "Object.assign(button.style" in text
    assert "cursor: \"pointer\"" in text
    assert "position: \"static\"" in text
    assert "data-codex-archive-page-row" in text
    assert "data-app-action-sidebar-thread-id" in text
    assert "取消归档" in text
    assert "已归档对话" in text


def test_renderer_script_uses_chinese_delete_toast_fallbacks():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "删除成功" in text
    assert "删除失败" in text
    assert "撤销完成" in text
    assert "Delete failed" not in text
    assert "Deleted\"" not in text
    assert "Undo finished" not in text


def test_renderer_script_does_not_include_legacy_project_file_tree_panel():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "projectFileTree" not in text
    assert "项目文件树" not in text


def test_renderer_script_removes_native_file_tree_entry():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "data-codex-mate-open-files" not in text
    assert "codex-mate-file-button" not in text
    assert "function findNativeFilePanelButton" not in text
    assert "function openNativeWorkspaceFileTab" not in text
    assert "async function nativeFileSearchTerms" not in text
    assert 'postJson("/workspace/first-file", {})' not in text
    assert "function openNativeFilePanel" not in text
    assert "function codexFetch" not in text
    assert "sendMessageFromView" not in text
    assert "function openCodexMateFileTreePanel" not in text
    assert "function renderCodexMateFileTree" not in text
    assert 'postJson("/file-tree/roots"' not in text
    assert 'postJson("/file-tree/list"' not in text


def test_renderer_script_adds_markdown_export_contract():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "markdownExport: true" in text
    assert "codex-export-button" in text
    assert "function downloadMarkdown" in text
    assert "async function exportMarkdown" in text
    assert 'postJson("/export-markdown", ref)' in text
    assert "导出 Markdown" in text
    assert "text/markdown;charset=utf-8" in text


def test_renderer_script_adds_session_move_contract():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "projectMove: true" in text
    assert "codex-project-move-button" in text
    assert "codex-project-move-overlay" in text
    assert "function projectMoveTargets" in text
    assert "function openProjectMoveMenuForRow" in text
    assert "function saveProjectMoveProjection" in text
    assert "function applyProjectMoveProjection" in text
    assert "function scheduleProjectMoveProjection" in text
    assert "function updateProjectMoveEmptyStates" in text
    assert "function scheduleChatsSortCorrection" in text
    assert "function applyChatsSortCorrection" in text
    assert "async function moveSessionToProject" in text
    assert "async function moveSessionToProjectless" in text
    assert 'postJson("/move-thread-workspace"' in text
    assert 'postJson("/move-thread-projectless"' in text
    assert 'postJson("/thread-sort-key", ref)' in text
    assert 'postJson("/thread-sort-keys", { sessions: refs })' in text
    assert "localStorage.setItem(projectMoveProjectionKey" in text
    assert "codex-project-move-hidden" in text
    assert "scheduleProjectMoveProjection()" in text
    assert "scheduleChatsSortCorrection(0)" in text
    assert "会话移动" in text
    assert "移动会话" in text


def test_renderer_script_adds_conversation_timeline_and_scroll_restore():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "conversationTimeline: true" in text
    assert "threadScrollRestore: true" in text
    assert "codex-conversation-timeline" in text
    assert "function refreshConversationTimeline" in text
    assert "function conversationTimelineQuestions" in text
    assert "function createConversationTimelineMarker" in text
    assert "完整对话目录" in text
    assert 'postJson("/conversation-timeline", ref)' in text
    assert "conversationTimelineCache" in text
    assert "approximateScrollTimelineTarget" in text
    assert "retryResolveTimelineTarget" in text
    assert "markTimelineProgrammaticScroll" in text
    assert "const questions = prepareTimelineQuestions(conversationTimelineQuestions())" not in text
    assert "function readThreadScrollEntries" in text
    assert "function saveThreadScrollPositionNow" in text
    assert "function restoreThreadScrollPosition" in text
    assert "installThreadScrollRouteHooks" in text
    assert "localStorage.setItem(codexThreadScrollKey" in text


def test_renderer_script_adds_backend_status_contract():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "codex-mate-backend-indicator" in text
    assert "data-codex-mate-backend-status" in text
    assert "function checkBackendStatus" in text
    assert 'postJson("/backend/status", {})' in text
    assert "后端已连接" in text
    assert "function httpPostJson(path, payload)" in text
    assert "Codex Mate bridge timeout" in text
    assert "return await httpPostJson(path, payload)" in text


def test_renderer_script_keeps_codex_mate_modal_contained_and_closable():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "max-height: min(760px, calc(100vh - 32px))" in text
    assert "overflow: hidden" in text
    assert "overflow-y: auto" in text
    assert "overlay.querySelector(\".codex-mate-modal-close\")?.addEventListener(\"click\"" in text
    assert "overlay.addEventListener(\"keydown\"" in text
    assert "event.key === \"Escape\"" in text


def test_renderer_script_delegated_clicks_tolerate_text_targets():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")

    assert "function closestElement(target, selector)" in text
    assert 'closestElement(event.target, ".codex-mate-modal-close")' in text
    assert 'closestElement(event.target, "[data-codex-mate-setting]")' in text
    assert 'closestElement(event.target, "[data-codex-delete-confirm]")' in text
    assert 'event.target.closest(".codex-mate-modal-close")' not in text
    assert 'event.target.closest("[data-codex-delete-confirm]")' not in text


def test_renderer_script_does_not_include_fast_mode_patch():
    text = Path("codex_mate/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "codexFastModeUnlockVersion" not in text
    assert "enableFastModeFeatureFlags" not in text
    assert "patchFastModeGates" not in text
    assert "patchGeneralSettingsSpeedGate" not in text
    assert "patchCodexPostForFastMode" not in text
    assert "recordFastModeDiagnostic" not in text
    assert "additionalSpeedTiers" not in text
    assert "bodyJsonString" not in text
    assert "forceChatGPTAuthForFastMode" not in text
    assert "codex-fast-mode-row" not in text
    assert "setAuthMethod(\"chatgpt\")" in text
    assert "patchFastModeGateOnObject" not in text
    assert "Codex Mate" in text
    assert "codexMateVersion = window.__CODEX_MATE_VERSION__ || \"dev\"" in text
    assert "1.1.7" not in text
    assert "Codex Mate ${codexMateVersion}" in text
    assert "提出问题" in text
    assert "https://github.com/serein431/Codex-Mate/issues" in text
    assert "window.open(issueUrl, \"_blank\")" in text
    assert "增强模式" in text
    assert "保持登录态" in text
    assert "强制注入" in text
    assert "当前检测" in text
    assert "未检测到 ChatGPT 登录" in text
    assert "我已登录，重新检测" in text
    assert 'button.textContent = waiting ? "正在检测…" : loginReady ? "重新检测" : "我已登录，重新检测"' in text
    assert "启用推荐模式" in text
    assert "临时启用强制注入" in text
    assert "供应商配置" in text
    assert "CC Switch 速切" in text
    assert "data-codex-mate-cc-switch-list" in text
    assert "data-codex-mate-cc-switch-refresh" in text
    assert "data-codex-mate-cc-switch-apply" in text
    assert "checkCodexMateCcSwitchProviders" in text
    assert "applyCodexMateCcSwitchProvider" in text
    assert 'postJson("/cc-switch/providers", {})' in text
    assert 'postJson("/cc-switch/apply", { source_id: sourceId })' in text
    assert "保留登录态 + API" in text
    assert "纯 API" in text
    assert "官方登录" in text
    assert "data-codex-mate-provider-mode" in text
    assert "data-codex-mate-provider-field" in text
    assert "data-codex-mate-provider-apply" in text
    assert "data-codex-mate-provider-status" in text
    assert "checkCodexMateProviderProfileStatus" in text
    assert "applyCodexMateProviderProfile" in text
    assert 'postJson("/provider-profile/status", {})' in text
    assert 'postJson("/provider-profile/apply", { profile })' in text
    assert "data-codex-mate-auth-summary" in text
    assert "data-codex-mate-auth-detail" in text
    assert "data-codex-mate-auth-mode" in text
    assert "authEnhancementMode" in text
    assert "setCodexMateAuthMode" in text
    assert "checkCodexMateAuthModeStatus" in text
    assert 'postJson("/auth-enhancement-mode/status", {})' in text
    assert 'postJson("/auth-enhancement-mode/set", { mode })' in text
    assert "data-codex-mate-auth-mode-status" in text
    assert "initialAuthModeStatusCheck.finally(scan)" in text
    assert 'codexMateAuthModeStatus.status === "checking"' in text
    assert "normalizeCodexMateSettings" in text
    assert '"loginPreserving"' in text
    assert '"forceInject"' in text
    assert "会话删除" in text
    assert "Markdown 导出" in text
    assert "完整对话目录" in text
    assert 'data-codex-mate-setting="conversationTimeline"' in text
    assert "滚动位置恢复" in text
    assert "原生菜单栏位置" in text
    assert "nativeMenuPlacement: true" in text
    assert "关于 Codex Mate" in text
    assert "https://github.com/serein431/Codex-Mate" in text
    assert "codexMateSettings" in text
    assert "pluginEntryUnlock" in text
    assert "forcePluginInstall" in text
    assert "sessionDelete" in text
    assert "codex-mate-modal-overlay" in text
    assert "codex-mate-modal-content" in text
    assert "codex-mate-modal-header" in text
    assert "codex-dialog-overlay" not in text
    assert "bg-token-dropdown-background/90" not in text
    assert "backdrop-blur-xl" not in text
    assert "codex-mate-menu-floating" in text
    assert "findNativeMenuInsertionPoint" in text
    assert "if (!codexMateSettings().nativeMenuPlacement) return null" in text
    assert "top: 8px" in text
    assert "right: 196px" in text
    assert "left: auto" in text
    assert "pointer-events: auto" in text
    assert "-webkit-app-region: no-drag" in text
    assert ".codex-mate-trigger" in text
    assert "trigger.textContent = \"CM\"" in text
    assert "data-codex-mate-compact" in text
    assert "app-header-tint" in text
    assert "ms-auto" in text
    assert "rect.left < window.innerWidth * 0.55" in text
    assert "codex-mate-menu-floating" in text
    assert "nativeButtonClass" in text
    assert "removeDuplicateCodexMateMenus" in text
    assert "data-codex-mate-menu" in text
    assert "label.startsWith(\"Codex Mate\")" in text
    assert "codexMateMenuVersion = \"25\"" in text
    assert "codexMateTriggerInstalled = \"25\"" in text
    assert "codexMateFileButtonVersion" not in text
    assert "function visibleRightPanelLeft" in text
    assert "[role='tabpanel'], .absolute.top-0.bottom-0.left-0" in text
    assert "function floatingMenuLeft" in text
    assert "function placeCodexMateMenu" in text
    assert "Math.round(panelLeft) + margin" in text
    assert "Math.round(window.innerWidth) - margin" in text
    assert "rect.top < 44" in text
    assert "cursor - rect.right >= menuWidth" in text
    assert '.ms-auto.flex.shrink-0.items-center.gap-1\\\\.5' in text
    assert 'existing && existing.isConnected' in text
    assert 'event.stopImmediatePropagation?.()' in text
    assert ".codex-mate-toolbar-button" in text
    assert 'trigger.className = "codex-mate-toolbar-button codex-mate-trigger"' in text
    assert "codex-mate-file-button" not in text
    assert ".codex-mate-trigger:hover" not in text
