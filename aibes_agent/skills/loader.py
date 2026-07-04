"""Skill discovery and loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from aibes_agent.skills.skill import Skill, SkillProfile


class SkillLoader:
    """Discover and load skills from directories containing ``skill.yaml`` or ``SKILL.md``."""

    def __init__(self, search_paths: Optional[List[str]] = None) -> None:
        self.search_paths: List[str] = search_paths or [".aibes-agent/skills"]

    def load_all(self) -> List[Skill]:
        """Load all skills from search paths, later paths override earlier ones by name."""
        by_name: Dict[str, Skill] = {}
        for raw_path in self.search_paths:
            path = Path(raw_path).expanduser().resolve()
            if not path.exists():
                continue
            for skill in self._load_path(path):
                by_name[skill.name] = skill
        return list(by_name.values())

    def load_one(self, directory: str) -> Skill:
        """Load a single skill directory."""
        path = Path(directory).expanduser().resolve()
        skill_file = path / "skill.yaml"
        if skill_file.exists():
            return self._load_skill_file(skill_file, path)
        skill_md = path / "SKILL.md"
        if skill_md.exists():
            return self._load_skill_markdown(skill_md, path)
        raise FileNotFoundError(f"No skill.yaml or SKILL.md found in {path}")

    def _load_path(self, path: Path) -> List[Skill]:
        skills: List[Skill] = []
        if path.is_file() and path.name == "skill.yaml":
            return [self._load_skill_file(path, path.parent)]
        if not path.is_dir():
            return skills
        for subdir in sorted(path.iterdir()):
            if not subdir.is_dir():
                continue
            skill_file = subdir / "skill.yaml"
            if skill_file.exists():
                skills.append(self._load_skill_file(skill_file, subdir))
                continue
            skill_md = subdir / "SKILL.md"
            if skill_md.exists():
                skills.append(self._load_skill_markdown(skill_md, subdir))
        return skills

    @staticmethod
    def _load_skill_file(skill_file: Path, directory: Path) -> Skill:
        with skill_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        profiles: Dict[str, SkillProfile] = {}
        raw_profiles = data.get("profiles", {})
        for name, prof in raw_profiles.items():
            profiles[name] = SkillProfile(
                name=name,
                system_prompt=prof.get("system_prompt", ""),
                tools=list(prof.get("tools", [])),
                max_turns=int(prof.get("max_turns", 10)),
                model=prof.get("model"),
            )

        return Skill(
            name=data.get("name", directory.name),
            path=directory,
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            tools=list(data.get("tools", [])),
            mcp_servers=list(data.get("mcp_servers", [])),
            profiles=profiles,
            restrict_tools="tools" in data,
        )

    @staticmethod
    def _load_skill_markdown(skill_md: Path, directory: Path) -> Skill:
        frontmatter, body = _parse_markdown_frontmatter(skill_md)

        tools = list(frontmatter.get("tools", []))
        restrict_tools = "tools" in frontmatter

        return Skill(
            name=frontmatter.get("name", directory.name),
            path=directory,
            description=frontmatter.get("description", ""),
            system_prompt=body.strip(),
            tools=tools,
            mcp_servers=list(frontmatter.get("mcp_servers", [])),
            profiles={},
            restrict_tools=restrict_tools,
        )


def _parse_markdown_frontmatter(path: Path) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter and markdown body from a file.

    Returns a tuple ``(frontmatter_dict, body)``. If no frontmatter is found,
    the entire content is returned as the body and frontmatter is empty.
    """
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    fm_text = content[3:end].strip()
    body = content[end + 3 :]
    try:
        frontmatter = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        frontmatter = {}

    if not isinstance(frontmatter, dict):
        frontmatter = {}

    return frontmatter, body
