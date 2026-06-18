from __future__ import annotations

import pathlib
import re
import subprocess
import tomllib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".ico"}


def test_compose_can_render_prowlarr_onboarding_before_api_key_exists():
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "config",
            "prowlarr",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_readme_architecture_mentions_cli_and_has_editable_source():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert readme.startswith("# qBitlarr")
    assert "REST / MCP / CLI" in readme
    assert "(docs/architecture.png)" in readme
    assert (REPO_ROOT / "docs" / "architecture.svg").exists()


def test_readme_leads_with_architecture_before_use_case():
    readmes = [
        (REPO_ROOT / "README.md", "## Architecture", "## What It Feels Like"),
        (REPO_ROOT / "README.zh-CN.md", "## 架构", "## 用起来是什么感觉"),
        (REPO_ROOT / "README.fr.md", "## Architecture", "## À quoi ça ressemble"),
    ]

    for readme_path, architecture_heading, use_case_heading in readmes:
        readme = readme_path.read_text(encoding="utf-8")
        assert readme.index(architecture_heading) < readme.index(use_case_heading)


def test_readme_language_switcher_links_are_reciprocal():
    english_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    chinese_readme_path = REPO_ROOT / "README.zh-CN.md"
    french_readme_path = REPO_ROOT / "README.fr.md"

    assert "[中文](README.zh-CN.md)" in english_readme
    assert "[Français](README.fr.md)" in english_readme
    assert chinese_readme_path.exists()
    assert french_readme_path.exists()

    chinese_readme = chinese_readme_path.read_text(encoding="utf-8")
    assert "[English](README.md)" in chinese_readme
    assert "[Français](README.fr.md)" in chinese_readme

    french_readme = french_readme_path.read_text(encoding="utf-8")
    assert "[English](README.md)" in french_readme
    assert "[中文](README.zh-CN.md)" in french_readme


def test_readme_examples_use_public_domain_sample_title():
    readmes = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.zh-CN.md",
        REPO_ROOT / "README.fr.md",
    ]
    disallowed_examples = [
        "YOUR" + "MOVIE",
        "YOUR" + "SHOW",
        "Pulp " + "Fiction",
        "The " + "Matrix",
        "Inter" + "stellar",
        "tt" + "0110912",
    ]

    for readme_path in readmes:
        readme = readme_path.read_text(encoding="utf-8")
        assert "The Hitch-Hiker" in readme
        assert "tt0045877" in readme

        for example in disallowed_examples:
            assert example not in readme


def test_tracked_text_files_do_not_reintroduce_legacy_media_examples():
    disallowed_examples = [
        "YOUR" + "MOVIE",
        "YOUR" + "SHOW",
        "Pulp " + "Fiction",
        "Fight " + "Club",
        "Jojo " + "Rabbit",
        "The " + "Matrix",
        "Inter" + "stellar",
        "The " + "Boys",
        "tt" + "0110912",
        "tt" + "1190634",
        "192" + ".168.1.139",
        "Co-" + "Authored-By",
        "Claude " + "Sonnet",
    ]
    disallowed_patterns = [
        r"\b" + "Qbit" + r"larr\b",
    ]
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr

    for relative_path in result.stdout.splitlines():
        path = REPO_ROOT / relative_path
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue

        content = path.read_text(encoding="utf-8")
        for example in disallowed_examples:
            assert example not in content, f"{example!r} found in {relative_path}"
        for pattern in disallowed_patterns:
            assert not re.search(pattern, content), f"{pattern!r} found in {relative_path}"


def test_readme_screenshots_are_referenced_and_explained():
    screenshot_paths = [
        "docs/screenshots/telegram-imdb-release-picker.jpg",
        "docs/screenshots/telegram-title-release-picker.jpg",
        "docs/screenshots/telegram-qbitlarr-babelarr-one-shot.jpg",
    ]
    readmes = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.zh-CN.md",
        REPO_ROOT / "README.fr.md",
    ]

    for screenshot_path in screenshot_paths:
        assert (REPO_ROOT / screenshot_path).exists()

    for readme_path in readmes:
        readme = readme_path.read_text(encoding="utf-8")
        assert "<table>" in readme
        for screenshot_path in screenshot_paths:
            assert screenshot_path in readme

        assert "Public Domain" in readme
        assert "specific restoration" in readme or "具体发行版" in readme or "restauration" in readme


def test_readme_documents_mcp_multilingual_behavior():
    assert "same language you use" in (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "用什么语言问" in (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    assert "même langue" in (REPO_ROOT / "README.fr.md").read_text(encoding="utf-8")


def test_readme_documents_qbittorrent_web_ui_setup():
    readmes = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.zh-CN.md",
        REPO_ROOT / "README.fr.md",
    ]

    for readme_path in readmes:
        readme = readme_path.read_text(encoding="utf-8")
        assert "qBittorrent Web UI" in readme
        assert "QBIT_URL" in readme
        assert "QBIT_USERNAME" in readme
        assert "QBIT_PASSWORD" in readme
        assert "host.docker.internal" in readme


def test_pyproject_exposes_qbitlarr_console_script():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["qbitlarr"] == "app.cli:main"


def test_production_requirements_do_not_install_test_runner():
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert not any(line.startswith("pytest") for line in requirements)


def test_dockerfile_runs_api_as_non_root_user():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "USER qbitlarr" in dockerfile


def test_compose_uses_pinned_third_party_image_tags():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert ":latest" not in compose
    assert "lscr.io/linuxserver/prowlarr:2.4.0.5397-ls149" in compose
    assert "ghcr.io/flaresolverr/flaresolverr:v3.5.0" in compose


def test_github_actions_runs_pytest_on_push_and_pull_request():
    workflow = REPO_ROOT / ".github" / "workflows" / "tests.yml"

    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")
    assert "pull_request:" in content
    assert "push:" in content
    assert "pytest -q" in content
