"""Chapter 10: Learning Loop — Self-Improving Agent Skills.

Teaches:
- How an agent can learn from successful task completions
- Persistent skill storage with JSON (no vector DB required)
- Simple skill retrieval by keyword matching
- Skill improvement: updating an existing skill based on new experience
- The full learning loop: Experience → Synthesize → Store → Retrieve → Reuse

Inspired by hermes-agent (NousResearch) which implements a closed learning loop:
agents autonomously create and improve skills during use, storing them in a
structured skill library for cross-session reuse.

Run:
    python learning_loop.py
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data model: a Skill is a reusable, named piece of procedural knowledge
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A persistent unit of learned agent behavior.

    Attributes:
        name:        Unique short identifier, e.g. "sort_list_by_key"
        description: One-sentence summary of what this skill does.
        trigger:     Keywords that should activate this skill, e.g. ["sort", "order", "rank"]
        template:    The reusable prompt or code template the agent executes.
        created_at:  ISO-8601 timestamp of first creation.
        updated_at:  ISO-8601 timestamp of last improvement.
        use_count:   How many times the agent has reused this skill.
        version:     Increments each time the skill is improved.
    """

    name: str
    description: str
    trigger: list[str]
    template: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    use_count: int = 0
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        return cls(**data)


# ---------------------------------------------------------------------------
# Experience: the raw material from which skills are synthesized
# ---------------------------------------------------------------------------

@dataclass
class Experience:
    """A recorded successful task completion.

    Attributes:
        task:       The user's original request.
        steps:      The sequence of actions the agent took to complete it.
        outcome:    The final result or observation.
        timestamp:  When this experience was collected.
    """

    task: str
    steps: list[str]
    outcome: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# SkillStore: persistent JSON-backed skill library
# ---------------------------------------------------------------------------

class SkillStore:
    """Stores and retrieves learned skills in a JSON file.

    Design note:
      Real systems (e.g. hermes-agent) use FTS5 SQLite or vector embeddings for
      semantic search. This implementation uses keyword matching to stay
      dependency-free and easy to understand.
    """

    def __init__(self, filepath: str = ".skill_store.json") -> None:
        self.filepath = filepath
        self._skills: dict[str, Skill] = {}
        self._load()

    # --- Persistence ---

    def _load(self) -> None:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                self._skills = {k: Skill.from_dict(v) for k, v in raw.items()}
            except (json.JSONDecodeError, OSError, TypeError):
                self._skills = {}

    def _save(self) -> None:
        with open(self.filepath, "w", encoding="utf-8") as fh:
            json.dump(
                {k: v.to_dict() for k, v in self._skills.items()},
                fh,
                indent=2,
                ensure_ascii=False,
            )

    # --- CRUD ---

    def add(self, skill: Skill) -> None:
        """Store a new skill (or overwrite if same name)."""
        self._skills[skill.name] = skill
        self._save()

    def get(self, name: str) -> Optional[Skill]:
        """Return skill by exact name."""
        return self._skills.get(name)

    def update(self, skill: Skill) -> None:
        """Update an existing skill (increments version, refreshes timestamp)."""
        skill.version += 1
        skill.updated_at = datetime.now().isoformat()
        self._skills[skill.name] = skill
        self._save()

    def record_use(self, name: str) -> None:
        """Increment the use counter for a skill."""
        if name in self._skills:
            self._skills[name].use_count += 1
            self._save()

    def list_all(self) -> list[Skill]:
        return list(self._skills.values())

    # --- Retrieval ---

    def search(self, query: str, top_k: int = 3) -> list[Skill]:
        """Return up to *top_k* skills whose triggers or description match *query*.

        Scoring: each trigger keyword found in query earns 2 points;
        each query word found in description earns 1 point.
        CJK text is matched using character n-grams (bigrams and trigrams).
        """
        # Build a set of query tokens: ASCII words + CJK bigrams/trigrams
        query_tokens: set[str] = set()
        query_tokens.update(w.lower() for w in re.findall(r"[a-zA-Z]{2,}", query))
        cjk = re.findall(r"[\u4e00-\u9fff]", query)
        for n in (2, 3):
            for i in range(len(cjk) - n + 1):
                query_tokens.add("".join(cjk[i : i + n]))

        scored: list[tuple[float, Skill]] = []

        for skill in self._skills.values():
            score = 0.0
            for kw in skill.trigger:
                if kw.lower() in query_tokens or kw.lower() in query.lower():
                    score += 2
            desc_tokens: set[str] = set()
            desc_tokens.update(w.lower() for w in re.findall(r"[a-zA-Z]{2,}", skill.description))
            cjk_d = re.findall(r"[\u4e00-\u9fff]", skill.description)
            for n in (2, 3):
                for i in range(len(cjk_d) - n + 1):
                    desc_tokens.add("".join(cjk_d[i : i + n]))
            score += len(query_tokens & desc_tokens)
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: (-x[0], -x[1].use_count))
        return [s for _, s in scored[:top_k]]


# ---------------------------------------------------------------------------
# SkillSynthesizer: converts raw experience into a reusable Skill
# ---------------------------------------------------------------------------

class SkillSynthesizer:
    """Converts an Experience into a Skill (or improves an existing one).

    In hermes-agent this is done by the LLM itself (it writes the skill
    template). Here we use a simplified rule-based approach so the demo
    runs without an API key.
    """

    def synthesize(self, exp: Experience, existing: Optional[Skill] = None) -> Skill:
        """Create a new Skill from *exp*, optionally merging with *existing*.

        Args:
            exp:       The experience to learn from.
            existing:  If provided, the skill will be improved rather than created.

        Returns:
            A (new or improved) Skill ready to be stored.
        """
        # Derive a short name (ASCII slug from first 4 ASCII words, or a hash for CJK)
        ascii_words = re.findall(r"[a-zA-Z]+", exp.task)[:4]
        if ascii_words:
            name = "_".join(w.lower() for w in ascii_words)
        else:
            # CJK task: use a 6-char hex digest for a stable, short name
            import hashlib
            name = "skill_" + hashlib.blake2b(exp.task.encode(), digest_size=3).hexdigest()
        if existing:
            name = existing.name

        # Extract trigger keywords:
        # - ASCII words of length >= 3
        # - CJK n-grams of length 2-4 (sliding window over the task string)
        trigger: list[str] = []
        ascii_kws = [w.lower() for w in re.findall(r"[a-zA-Z]{3,}", exp.task)]
        trigger.extend(ascii_kws)

        cjk_chars = re.findall(r"[\u4e00-\u9fff]", exp.task)
        for n in (2, 3):
            for i in range(len(cjk_chars) - n + 1):
                trigger.append("".join(cjk_chars[i : i + n]))

        trigger = list(dict.fromkeys(trigger))[:10]  # deduplicate, keep order

        # Build a step-by-step template
        steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(exp.steps))
        template = textwrap.dedent(f"""\
            任务：{{task}}

            执行步骤：
            {steps_text}

            预期结果：{exp.outcome}
        """)

        if existing:
            # Improvement: merge steps and keep both templates
            try:
                old_steps = existing.template.split("执行步骤：\n")[1].split("\n\n")[0]
            except IndexError:
                old_steps = existing.template
            template = textwrap.dedent(f"""\
                任务：{{task}}

                改进后的执行步骤（v{existing.version + 1}）：
                {steps_text}

                原有步骤参考（v{existing.version}）：
                {old_steps}

                预期结果：{exp.outcome}
            """)
            existing.description = f"[v{existing.version+1}] " + exp.task[:60]
            existing.trigger = list(set(existing.trigger + trigger))[:8]
            existing.template = template
            return existing

        return Skill(
            name=name,
            description=exp.task[:80],
            trigger=trigger,
            template=template,
        )


# ---------------------------------------------------------------------------
# LearningAgent: an agent that accumulates experience and grows its skill library
# ---------------------------------------------------------------------------

class LearningAgent:
    """A simple agent that learns from its own experiences.

    Lifecycle for each task:
      1. Search existing skills for relevant knowledge.
      2. Execute the task (mock or real), recording steps.
      3. On success, synthesize a skill and store/improve it.

    This mirrors hermes-agent's closed learning loop:
      - Agent completes a task
      - LLM is prompted to extract a reusable skill
      - Skill is saved to disk and indexed for future retrieval
    """

    def __init__(self, skill_store: SkillStore) -> None:
        self.store = skill_store
        self.synthesizer = SkillSynthesizer()
        self._experience_log: list[Experience] = []

    # --- Task execution (mocked) ---

    def run(self, task: str) -> str:
        """Execute *task*, learn from the experience, and return the result."""
        print(f"\n{'='*60}")
        print(f"📋 任务: {task}")
        print(f"{'='*60}")

        # Step 1: retrieve relevant skills
        relevant = self.store.search(task)
        if relevant:
            print(f"\n🔍 找到 {len(relevant)} 个相关技能：")
            for sk in relevant:
                print(f"  • [{sk.name}] v{sk.version}（使用次数: {sk.use_count}）: {sk.description}")
                self.store.record_use(sk.name)
            hint = f"（参考技能: {relevant[0].name}）"
        else:
            print("\n🔍 未找到相关技能，将从头解决此任务。")
            hint = ""

        # Step 2: simulate task execution
        steps, outcome = self._mock_execute(task)
        print(f"\n🛠  执行步骤:")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {s}")
        print(f"\n✅ 结果: {outcome} {hint}")

        # Step 3: record experience and learn
        exp = Experience(task=task, steps=steps, outcome=outcome)
        self._experience_log.append(exp)
        self._learn(exp, task)

        return outcome

    def _mock_execute(self, task: str) -> tuple[list[str], str]:
        """Simulate task execution. Returns (steps, outcome)."""
        task_lower = task.lower()

        if any(w in task_lower for w in ["排序", "sort", "order"]):
            return (
                ["读取输入列表", "确定排序键", "调用内置排序算法", "返回有序列表"],
                "列表已按指定键升序排列",
            )
        if any(w in task_lower for w in ["搜索", "search", "查找", "find"]):
            return (
                ["解析查询关键词", "遍历数据源", "过滤匹配项", "返回结果列表"],
                "已返回 5 条匹配结果",
            )
        if any(w in task_lower for w in ["总结", "summarize", "摘要"]):
            return (
                ["分割原文为段落", "提取每段关键句", "拼接摘要", "压缩至目标长度"],
                "已生成 200 字摘要",
            )
        if any(w in task_lower for w in ["翻译", "translate"]):
            return (
                ["检测源语言", "调用翻译引擎", "后处理格式", "返回译文"],
                "翻译完成",
            )
        return (
            ["分析任务", "制定执行计划", "逐步执行", "验证结果"],
            "任务已完成",
        )

    def _learn(self, exp: Experience, original_task: str) -> None:
        """Synthesize a skill from *exp* and store or improve it."""
        # Check if a similar skill already exists (reuse its name for improvement)
        candidates = self.store.search(original_task, top_k=1)
        existing = candidates[0] if candidates else None

        skill = self.synthesizer.synthesize(exp, existing=existing)

        if existing and skill.name == existing.name:
            print(f"\n📈 改进现有技能: [{skill.name}] → v{skill.version + 1}")
            self.store.update(skill)
        else:
            print(f"\n🧠 学到新技能: [{skill.name}]")
            self.store.add(skill)

    def show_skill_library(self) -> None:
        """Pretty-print all skills in the store."""
        skills = self.store.list_all()
        print(f"\n{'='*60}")
        print(f"📚 技能库（共 {len(skills)} 个技能）")
        print(f"{'='*60}")
        if not skills:
            print("  （空）")
            return
        for sk in sorted(skills, key=lambda s: -s.use_count):
            print(f"\n  [{sk.name}] v{sk.version}")
            print(f"    描述   : {sk.description}")
            print(f"    触发词 : {sk.trigger}")
            print(f"    使用次数: {sk.use_count}")
            print(f"    创建于 : {sk.created_at[:19]}")
            print(f"    更新于 : {sk.updated_at[:19]}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pathlib

    store_file = str(pathlib.Path(__file__).parent / ".skill_store_demo.json")

    # Start with a clean slate for the demo
    if os.path.exists(store_file):
        os.remove(store_file)

    store = SkillStore(filepath=store_file)
    agent = LearningAgent(skill_store=store)

    print("=" * 60)
    print("Chapter 10: Learning Loop Demo")
    print("=" * 60)

    # --- Round 1: new tasks, agent has no prior skills ---
    agent.run("对用户列表按注册时间排序")
    agent.run("搜索商品数据库中的手机")
    agent.run("总结本月销售报告")

    # --- Round 2: similar tasks — agent finds and reuses skills ---
    print("\n\n--- Round 2: 相似任务，观察技能复用与改进 ---")
    agent.run("将订单列表按金额从大到小排序")
    agent.run("在日志文件中搜索错误关键词")

    # --- Show the learned skill library ---
    agent.show_skill_library()

    print("\n\n--- 技能检索演示 ---")
    query = "如何对数据进行排序"
    results = store.search(query, top_k=2)
    print(f"查询: 「{query}」")
    for r in results:
        print(f"  匹配技能: [{r.name}] — {r.description}")

    # Cleanup
    if os.path.exists(store_file):
        os.remove(store_file)
    print("\nDemo 完成！")
