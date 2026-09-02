from runrepro.redaction import SecretRedactor


def test_redactor_masks_token_families_and_secret_assignments() -> None:
    github_token = "gh" + "p_" + "A" * 36
    fine_grained = "github" + "_pat_" + "B" * 48
    text = (
        f"token={github_token}\n"
        f"Authorization: Bearer {fine_grained}\n"
        "DATABASE_PASSWORD=hunter2\n"
        "commit=" + "a" * 40 + "\n"
    )

    redacted = SecretRedactor().redact(text)

    assert github_token not in redacted
    assert fine_grained not in redacted
    assert "hunter2" not in redacted
    assert redacted.count("[REDACTED]") >= 3
    assert "a" * 40 in redacted


def test_redactor_honors_github_mask_commands_without_persisting_the_mask_value() -> None:
    log = "::add-mask::top-secret-value\nbefore top-secret-value after\n"

    redacted = SecretRedactor().redact(log)

    assert "top-secret-value" not in redacted
    assert "::add-mask::[REDACTED]" in redacted
    assert "before [REDACTED] after" in redacted


def test_redactor_accepts_bytes_and_replaces_invalid_utf8() -> None:
    value = SecretRedactor().redact_bytes(b"ok\xffAPI_KEY=unsafe")

    assert value.startswith("ok")
    assert "unsafe" not in value
