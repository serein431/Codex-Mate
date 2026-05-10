import subprocess
from pathlib import Path


def test_renderer_script_exists_and_parses_with_node():
    script = Path("codex_session_delete/inject/renderer-inject.js")
    assert script.exists()
    result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_renderer_script_contains_hover_delete_contract():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "codex-delete-button" in text
    assert "MutationObserver" in text
    assert "confirmDelete" in text
    assert "/delete" in text
    assert "/undo" in text


def test_renderer_script_supports_codex_sidebar_thread_attributes():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("function sessionRows")
    end = text.index("\n\n  function archivePageHintVisible", start)
    session_rows_code = text[start:end]
    assert "data-app-action-sidebar-thread-id" in session_rows_code
    assert "data-thread-title" in text
    assert "a[href*='session']" not in session_rows_code
    assert "conversation" not in session_rows_code
    assert "thread" not in session_rows_code.replace("data-app-action-sidebar-thread-id", "")
    assert "hasSessionHint" not in session_rows_code


def test_renderer_script_positions_delete_button_without_affecting_layout():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "position: absolute" in text
    assert "right: 28px" in text
    assert "top: 50%" in text
    assert "transform: translateY(-50%)" in text
    assert "min-width: 38px" in text
    assert "height: 22px" in text
    assert "font: inherit" in text
    assert "font-size: 12px" in text
    assert "line-height: 18px" in text
    assert "border-radius: 6px" in text
    assert "aria-label" in text
    start = text.index("function attachButton")
    end = text.index("\n\n  function tryAttachButton", start)
    attach_button_code = text[start:end]
    assert "button.textContent = \"删除\"" in attach_button_code
    assert "codex-delete-icon" not in attach_button_code




def test_renderer_script_enables_plugin_entry_for_api_key_users():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
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
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
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
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "scanLightweight" in text
    assert "scanDeferred" in text
    assert "runScanStep" in text
    assert "codexSessionDeleteScanFailures" in text
    assert "runScanStep(scanLightweight)" in text
    assert "requestAnimationFrame(() => runScanStep(scanDeferred))" in text
    assert "if (window.__codexSessionDeleteScanPending) return" in text
    assert "setTimeout(runScheduledScan, 200)" in text
    assert "setTimeout(() => runScanStep(scanDeferred), 50)" not in text
    assert "codexSessionDeleteAttachButtonFailures" in text
    assert "tryAttachButton" in text
    assert "sessionRows().forEach(tryAttachButton)" in text
    assert "sessionRows().forEach(attachButton)" not in text
    assert "new MutationObserver(scheduleScan)" in text
    assert "new MutationObserver(scan)" not in text
    assert "scan();" in text
    assert "  scan();\n  window.__codexSessionDeleteObserver" in text


def test_renderer_script_ignores_chat_content_mutations_before_scheduling_scan():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
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
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    start = text.index("const scanRelevantSelector")
    end = text.index("\n\n  function isChatContentMutation", start)
    relevant_code = text[start:end]
    assert "node.matches?.(scanRelevantSelector)" in relevant_code
    assert "node.querySelector?.(scanRelevantSelector)" in relevant_code
    assert "button[aria-label=\"已归档对话\"]" in relevant_code
    assert "button:disabled.w-full.justify-center" in relevant_code
    assert "[role=\"button\"][aria-disabled=\"true\"].cursor-not-allowed" in relevant_code


def test_renderer_script_clears_focus_and_removes_deleted_rows():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "removeDeletedRow(row, button, ref)" in text
    assert "function releaseDeleteFocus" in text
    assert "releaseDeleteFocus(row, button)" in text
    assert "button.blur()" in text
    assert "document.activeElement.blur()" in text
    assert "row.remove()" in text
    assert "row.style.display = \"none\"" not in text


def test_renderer_script_uses_in_page_confirm_and_stops_early_pointer_events():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "confirm(" not in text
    assert "codex-delete-confirm-overlay" in text
    assert "escapeHtml(title)" in text
    assert "stopImmediatePropagation" in text
    assert "\"pointerdown\", \"mousedown\", \"mouseup\", \"touchstart\"" in text


def test_renderer_script_reloads_after_deleting_current_session():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "isCurrentSessionRow" in text
    assert "window.location.href.includes(ref.session_id)" in text
    assert "window.location.reload()" in text


def test_renderer_script_toast_does_not_capture_page_interactions():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "z-index: 2147483000" in text
    assert "pointer-events: none" in text
    assert "pointer-events: auto" in text
def test_renderer_script_sidebar_delete_opens_on_pointerup_when_click_is_unreliable():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "openDeleteConfirm" in text
    assert "codexDeleteVersion = \"5\"" in text
    assert "existingDeleteButtons.length === 1" in text
    assert "existingDeleteButtons[0].dataset.codexDeleteVersion === codexDeleteVersion" in text
    assert "existingDeleteButtons.forEach((button) => button.remove())" in text
    assert "row.dataset.codexDeleteRow = \"false\"" in text
    assert "installDeleteButtonEventDelegation" in text
    assert "codexSessionDeleteDocumentDeleteHandler" in text
    assert "document.addEventListener(\"pointerup\", handler, true)" in text
    assert "document.addEventListener(\"click\", handler, true)" in text
    assert "button.addEventListener(\"pointerup\", openDeleteConfirm, true)" in text


    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "updateDeleteButtonOffsets" in text
    assert "codexDeleteStyleVersion = \"6\"" in text
    assert "right: 66px" in text
    assert "确认" in text
    assert "归档对话" in text
    assert "button.getAttribute(\"aria-label\")" in text
    assert "label === \"归档对话\"" in text


    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
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
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
    assert "删除成功" in text
    assert "删除失败" in text
    assert "撤销完成" in text
    assert "Delete failed" not in text
    assert "Deleted\"" not in text
    assert "Undo finished" not in text


def test_renderer_script_does_not_include_fast_mode_patch():
    text = Path("codex_session_delete/inject/renderer-inject.js").read_text(encoding="utf-8")
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
    assert "codexPlusVersion = \"1.0.4\"" in text
    assert "Codex Mate ${codexPlusVersion}" in text
    assert "提出问题" in text
    assert "https://github.com/serein431/Codex-Mate/issues" in text
    assert "window.open(issueUrl, \"_blank\")" in text
    assert "插件选项解锁" in text
    assert "特殊插件强制安装" in text
    assert "会话删除" in text
    assert "原生菜单栏位置" in text
    assert "nativeMenuPlacement: true" in text
    assert "关于 Codex Mate" in text
    assert "https://github.com/serein431/Codex-Mate" in text
    assert "codexPlusSettings" in text
    assert "pluginEntryUnlock" in text
    assert "forcePluginInstall" in text
    assert "sessionDelete" in text
    assert "codex-plus-modal-overlay" in text
    assert "codex-plus-modal-content" in text
    assert "codex-plus-modal-header" in text
    assert "codex-dialog-overlay" not in text
    assert "bg-token-dropdown-background/90" not in text
    assert "backdrop-blur-xl" not in text
    assert "codex-plus-menu-floating" in text
    assert "findNativeMenuInsertionPoint" in text
    assert "if (!codexPlusSettings().nativeMenuPlacement) return null" in text
    assert "right: 140px" in text
    assert "left: auto" in text
    assert "pointer-events: auto" in text
    assert "-webkit-app-region: no-drag" in text
    assert ".codex-plus-trigger" in text
    assert "app-header-tint" in text
    assert "flex items-center gap-0.5" in text
    assert "codex-plus-menu-floating" in text
    assert "nativeButtonClass" in text
    assert "removeDuplicateCodexPlusMenus" in text
    assert "data-codex-plus-menu" in text
    assert "textContent || \"\").trim() === `Codex Mate ${codexPlusVersion}`" in text
    assert "codexPlusMenuVersion = \"5\"" in text
    assert "codexPlusTriggerInstalled = \"5\"" in text
    assert ".codex-plus-trigger:hover" not in text
