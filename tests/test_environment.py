from runrepro.environment import EnvironmentSnapshot, compare_environments, parse_runner_log


def test_parse_runner_log_extracts_evidenced_runner_image() -> None:
    snapshot = parse_runner_log(
        "Runner Image\nImage: ubuntu-24.04\nVersion: 20260824.1\nArchitecture: X64\n"
    )

    assert snapshot.os == "Linux"
    assert snapshot.architecture == "X64"
    assert snapshot.runner_image == "ubuntu-24.04"
    assert snapshot.runner_image_version == "20260824.1"
    assert snapshot.evidence == "job-log"


def test_parse_runner_log_handles_real_actions_prefixes_and_image_group() -> None:
    snapshot = parse_runner_log(
        "2026-09-02T15:19:42.4552922Z ##[group]Runner Image Provisioner\n"
        "2026-09-02T15:19:42.4554515Z Version: 20260819.586\n"
        "2026-09-02T15:19:42.4561590Z ##[group]Runner Image\n"
        "2026-09-02T15:19:42.4562132Z Image: ubuntu-24.04\n"
        "2026-09-02T15:19:42.4562705Z Version: 20260823.283.1\n"
        "2026-09-02T15:19:42.4563000Z ##[endgroup]\n"
        "2026-09-02T15:19:44.8921902Z RUNREPRO_TOOL bash=5.2.21(1)-release\n"
    )

    assert snapshot.runner_image == "ubuntu-24.04"
    assert snapshot.runner_image_version == "20260823.283.1"
    assert snapshot.os == "Linux"
    assert snapshot.tool_versions == {"bash": "5.2.21(1)-release"}


def test_compare_environments_marks_mismatch_match_and_unknown() -> None:
    remote = EnvironmentSnapshot(
        os="Linux",
        architecture="X64",
        runner_image="ubuntu-24.04",
        runner_image_version="20260824.1",
        runner_labels=["ubuntu-latest"],
        working_directory="/home/runner/work/widgets/widgets",
        environment_variables={"CI": "true", "GITHUB_ACTIONS": "true"},
        tool_versions={},
        container_image=None,
        evidence="job-log+inferred-standard",
    )
    local = EnvironmentSnapshot(
        os="Windows",
        architecture="AMD64",
        runner_image=None,
        runner_image_version=None,
        runner_labels=[],
        working_directory="C:/work/widgets",
        environment_variables={"CI": None, "GITHUB_ACTIONS": None},
        tool_versions={"python": "3.13.7"},
        container_image=None,
        evidence="local-probe",
    )

    report = compare_environments(remote, local)
    by_field = {item.field: item for item in report.items}

    assert by_field["os"].status == "mismatch"
    assert by_field["architecture"].status == "match"
    assert by_field["container_image"].status == "unknown"
    assert report.replay_equivalent is False
    assert any("tool versions" in limitation.lower() for limitation in report.limitations)
