from codex_session_delete.models import DeleteResult, DeleteStatus, SessionRef


def test_session_ref_requires_session_id():
    try:
        SessionRef(session_id="", title="Untitled")
    except ValueError as exc:
        assert "session_id" in str(exc)
    else:
        raise AssertionError("SessionRef accepted an empty session_id")


def test_delete_result_serializes_to_json_dict():
    result = DeleteResult(
        status=DeleteStatus.LOCAL_DELETED,
        session_id="abc123",
        message="Deleted locally",
        undo_token="undo-1",
        backup_path="C:/tmp/backup.json",
    )

    assert result.to_dict() == {
        "status": "local_deleted",
        "session_id": "abc123",
        "message": "Deleted locally",
        "undo_token": "undo-1",
        "backup_path": "C:/tmp/backup.json",
    }
