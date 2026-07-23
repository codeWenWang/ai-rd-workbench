from __future__ import annotations

import asyncio
import json
import re

from app.domain.entities import MessageRole, ModelMessage
from app.domain.errors import ResourceNotFound, ValidationError


class ImprovementTaskUseCase:
    def __init__(
        self,
        tasks,
        projects,
        analysis,
        model,
        model_gateway=None,
        project_analysis_use_case=None,
        project_use_case=None,
    ) -> None:
        self.tasks = tasks
        self.projects = projects
        self.analysis = analysis
        self.model = model
        self.model_gateway = model_gateway
        self.project_analysis_use_case = project_analysis_use_case
        self.project_use_case = project_use_case

    async def create(
        self,
        *,
        project_id: str,
        goal: str,
        title: str = "",
        model_id: str | None = None,
    ):
        project = self.projects.get(project_id)
        if not project:
            raise ResourceNotFound("project not found")
        files = self.analysis.list_files(project_id)
        if not files or not project.source_revision:
            raise ValidationError("请先扫描项目，再创建研发任务")
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValidationError("任务目标不能为空")

        response = await self._invoke(
            _plan_prompt(project, files, normalized_goal), model_id
        )
        generated = _normalize_plan(_json_object(response), normalized_goal, response)
        task_title = title.strip() or generated["title"]
        plan = {
            "summary": generated["summary"],
            "steps": generated["steps"],
            "affected_files": generated["affected_files"],
            "risks": generated["risks"],
        }
        agent_prompt = _agent_prompt(
            project.name,
            normalized_goal,
            plan,
            generated["acceptance_criteria"],
        )
        return self.tasks.create(
            project_id=project_id,
            title=task_title[:300],
            goal=normalized_goal,
            plan=plan,
            acceptance_criteria=generated["acceptance_criteria"],
            agent_prompt=agent_prompt,
            baseline_revision=project.source_revision,
            baseline_hashes={item.relative_path: item.content_hash for item in files},
        )

    def get(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            raise ResourceNotFound("improvement task not found")
        return task

    def list(self, *, project_id: str | None = None):
        return self.tasks.list(project_id=project_id)

    def update(
        self,
        task_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        completed_step_ids: list[str] | None = None,
        agent_prompt: str | None = None,
    ):
        task = self.get(task_id)
        if status is not None and status not in {
            "planned", "in_progress", "needs_review", "completed"
        }:
            raise ValidationError("不支持的任务状态")
        valid_step_ids = {
            str(item.get("id")) for item in task.plan.get("steps", []) if item.get("id")
        }
        normalized_steps = None
        if completed_step_ids is not None:
            normalized_steps = list(dict.fromkeys(
                step_id for step_id in completed_step_ids if step_id in valid_step_ids
            ))
            if status is None and task.status == "planned" and normalized_steps:
                status = "in_progress"
        return self.tasks.update(
            task_id,
            title=title.strip()[:300] if title is not None else None,
            status=status,
            completed_step_ids=normalized_steps,
            agent_prompt=agent_prompt.strip() if agent_prompt is not None else None,
        )

    async def review(self, task_id: str, *, model_id: str | None = None):
        task = self.get(task_id)
        project = self.projects.get(task.project_id)
        if not project:
            raise ResourceNotFound("project not found")
        if self.project_use_case:
            await asyncio.to_thread(
                self.project_use_case.prepare_for_scan, task.project_id
            )
        if self.project_analysis_use_case:
            await asyncio.to_thread(
                self.project_analysis_use_case.scan_incremental, task.project_id
            )
        project = self.projects.get(task.project_id)
        files = self.analysis.list_files(task.project_id)
        if not files or not project.source_revision:
            raise ValidationError("请先重新扫描项目，再开始审查")

        current_hashes = {item.relative_path: item.content_hash for item in files}
        changes = _changes(task.baseline_hashes, current_hashes)
        changed_paths = set(changes["added"] + changes["modified"])
        changed_files = [item for item in files if item.relative_path in changed_paths]
        if not any(changes.values()):
            review = {
                "summary": "未检测到基线之后的源码变化，请修改项目并重新扫描后再审查。",
                "changed_files": changes,
                "criteria": [
                    {"criterion": item, "status": "pending", "evidence": "未检测到代码变化"}
                    for item in task.acceptance_criteria
                ],
                "findings": [],
                "next_actions": ["完成代码修改后重新扫描项目"],
                "source_revision": project.source_revision,
                "scan_mode": "incremental",
            }
            return self.tasks.update(task.id, status="needs_review", review=review)

        response = await self._invoke(
            _review_prompt(task, project, changes, changed_files), model_id
        )
        review = _normalize_review(
            _json_object(response),
            task.acceptance_criteria,
            changes,
            project.source_revision,
            response,
        )
        review["scan_mode"] = "incremental"
        all_passed = bool(review["criteria"]) and all(
            item["status"] == "passed" for item in review["criteria"]
        ) and not any(
            item["severity"] == "high" for item in review["findings"]
        )
        return self.tasks.update(
            task.id,
            status="completed" if all_passed else "needs_review",
            review=review,
        )

    def delete(self, task_id: str) -> None:
        self.get(task_id)
        self.tasks.delete(task_id)

    async def _invoke(self, prompt: str, model_id: str | None) -> str:
        messages = [ModelMessage(MessageRole.USER, prompt)]
        if model_id and self.model_gateway:
            return await self.model_gateway.invoke(model_id, messages)
        return await self.model.ainvoke(messages)


def _project_context(files, goal: str, *, limit: int = 12) -> str:
    keywords = {
        item.casefold() for item in re.findall(r"[A-Za-z_][\w.-]{2,}|[\u4e00-\u9fff]{2,6}", goal)
    }
    important = {
        "readme.md", "pom.xml", "package.json", "pyproject.toml",
        "requirements.txt", "build.gradle", "settings.gradle",
    }

    def score(item) -> tuple[int, str]:
        path = item.relative_path.casefold()
        value = 20 if path.rsplit("/", 1)[-1] in important else 0
        value += sum(3 for keyword in keywords if keyword in path)
        value += sum(1 for keyword in keywords if keyword in item.content[:8000].casefold())
        return (-value, path)

    selected = sorted(files, key=score)[:limit]
    return "\n\n".join(
        f"文件：{item.relative_path}\n{item.content[:2600]}" for item in selected
    )[:28000]


def _plan_prompt(project, files, goal: str) -> str:
    return f"""你是严谨的软件研发规划助手。请根据真实源码为研发任务制定可执行计划。

写作要求：
- 只输出一个合法 JSON 对象，不要使用 Markdown 代码围栏。
- 不使用 emoji、装饰图标、口号或夸张措辞。
- 不编造不存在的文件；不确定的路径应明确标记为建议新建。
- 步骤应按实施顺序排列，验收标准必须可检查。

JSON 结构：
{{
  "title": "简短任务名称",
  "summary": "方案概述",
  "steps": [{{"id": "step-1", "title": "步骤标题", "description": "具体操作", "affected_files": ["路径"]}}],
  "affected_files": [{{"path": "路径", "reason": "修改原因"}}],
  "risks": ["风险"],
  "acceptance_criteria": ["可验证的验收标准"],
  "agent_prompt": "可直接交给编码 Agent 的完整中文提示词"
}}

项目名称：{project.name}
技术栈：{', '.join(project.tech_stack) or '未识别'}
任务目标：{goal}

项目源码上下文：
{_project_context(files, goal)}
"""


def _review_prompt(task, project, changes: dict, files) -> str:
    changed_source = "\n\n".join(
        f"文件：{item.relative_path}\n{item.content[:5000]}" for item in files[:12]
    )[:42000]
    return f"""你是严谨的代码审查与验收助手。请根据研发任务、验收标准和重扫后的源码进行静态审查。

要求：
- 只输出一个合法 JSON 对象，不要使用 Markdown 代码围栏。
- 不使用 emoji、装饰图标或空泛赞美。
- 只能引用提供的源码，证据包含真实文件路径和尽可能准确的行号。
- 未运行测试，不得声称运行结果通过。

JSON 结构：
{{
  "summary": "审查结论",
  "criteria": [{{"criterion": "原验收标准", "status": "passed|failed|uncertain", "evidence": "证据"}}],
  "findings": [{{"severity": "high|medium|low", "title": "问题", "detail": "原因和影响", "path": "文件路径", "line": 1}}],
  "next_actions": ["下一步操作"]
}}

项目：{project.name}
任务目标：{task.goal}
实施计划：{json.dumps(task.plan, ensure_ascii=False)}
验收标准：{json.dumps(task.acceptance_criteria, ensure_ascii=False)}
变更文件：{json.dumps(changes, ensure_ascii=False)}

重扫后的相关源码：
{changed_source}
"""


def _json_object(text: str) -> dict:
    source = str(text or "").strip()
    if source.startswith("```"):
        source = re.sub(r"^```(?:json)?\s*|\s*```$", "", source, flags=re.I)
    start, end = source.find("{"), source.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        value = json.loads(source[start:end + 1])
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _strings(value, *, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _normalize_plan(value: dict, goal: str, raw: str) -> dict:
    raw_steps = value.get("steps") if isinstance(value.get("steps"), list) else []
    steps = []
    for index, item in enumerate(raw_steps[:8], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or f"实施步骤 {index}").strip()
        steps.append({
            "id": str(item.get("id") or f"step-{index}"),
            "title": title,
            "description": str(item.get("description") or "").strip(),
            "affected_files": _strings(item.get("affected_files"), limit=8),
        })
    if not steps:
        steps = [
            {"id": "step-1", "title": "确认影响范围", "description": "结合源码确认需要修改的模块和接口。", "affected_files": []},
            {"id": "step-2", "title": "实现任务目标", "description": goal, "affected_files": []},
            {"id": "step-3", "title": "补充验证", "description": "根据验收标准补充测试并检查回归风险。", "affected_files": []},
        ]
    affected = []
    for item in value.get("affected_files", []) if isinstance(value.get("affected_files"), list) else []:
        if isinstance(item, dict) and str(item.get("path") or "").strip():
            affected.append({
                "path": str(item["path"]).strip(),
                "reason": str(item.get("reason") or "").strip(),
            })
    criteria = _strings(value.get("acceptance_criteria"), limit=10) or [
        "任务目标对应的代码路径已经实现",
        "关键行为有明确的测试或人工验证方式",
        "现有主要功能没有明显回归",
    ]
    return {
        "title": str(value.get("title") or goal[:28]).strip(),
        "summary": str(value.get("summary") or raw[:500] or goal).strip(),
        "steps": steps,
        "affected_files": affected[:16],
        "risks": _strings(value.get("risks"), limit=8),
        "acceptance_criteria": criteria,
        "agent_prompt": str(value.get("agent_prompt") or "").strip(),
    }


def _normalize_review(
    value: dict,
    acceptance_criteria: list[str],
    changes: dict,
    revision: str,
    raw: str,
) -> dict:
    supplied = value.get("criteria") if isinstance(value.get("criteria"), list) else []
    by_criterion = {
        str(item.get("criterion") or "").strip(): item
        for item in supplied if isinstance(item, dict)
    }
    criteria = []
    for criterion in acceptance_criteria:
        item = by_criterion.get(criterion, {})
        status = str(item.get("status") or "uncertain").casefold()
        if status not in {"passed", "failed", "uncertain"}:
            status = "uncertain"
        criteria.append({
            "criterion": criterion,
            "status": status,
            "evidence": str(item.get("evidence") or "模型未提供充分证据").strip(),
        })
    findings = []
    raw_findings = value.get("findings") if isinstance(value.get("findings"), list) else []
    for item in raw_findings[:12]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "medium").casefold()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        findings.append({
            "severity": severity,
            "title": str(item.get("title") or "待确认问题").strip(),
            "detail": str(item.get("detail") or "").strip(),
            "path": str(item.get("path") or "").strip(),
            "line": int(item.get("line") or 0) if str(item.get("line") or "").isdigit() else 0,
        })
    return {
        "summary": str(value.get("summary") or raw[:500] or "静态审查完成").strip(),
        "changed_files": changes,
        "criteria": criteria,
        "findings": findings,
        "next_actions": _strings(value.get("next_actions"), limit=8),
        "source_revision": revision,
    }


def _changes(baseline: dict[str, str], current: dict[str, str]) -> dict[str, list[str]]:
    before, after = set(baseline), set(current)
    return {
        "added": sorted(after - before),
        "modified": sorted(path for path in before & after if baseline[path] != current[path]),
        "deleted": sorted(before - after),
    }


def _agent_prompt(project_name: str, goal: str, plan: dict, criteria: list[str]) -> str:
    lines = [
        f"请修改项目：{project_name}",
        "",
        "## 任务目标",
        goal,
        "",
        "## 实施步骤",
    ]
    for index, step in enumerate(plan.get("steps", []), start=1):
        lines.append(f"{index}. {step.get('title', '').strip()}")
        if step.get("description"):
            lines.append(f"   {step['description'].strip()}")
        files = step.get("affected_files") or []
        if files:
            lines.append("   涉及文件：" + ", ".join(f"`{path}`" for path in files))
    lines.extend(["", "## 影响文件"])
    for item in plan.get("affected_files", []):
        path = item.get("path", "").strip()
        reason = item.get("reason", "").strip()
        if path:
            lines.append(f"- `{path}`" + (f"：{reason}" if reason else ""))
    lines.extend(["", "## 验收标准"])
    lines.extend(f"- {item}" for item in criteria)
    lines.extend([
        "",
        "## 约束",
        "- 先阅读相关源码，再按现有架构和编码风格修改。",
        "- 只修改完成任务所需的文件，不编造不存在的路径。",
        "- 补充必要测试，并在完成后报告改动文件、验证结果和剩余风险。",
    ])
    return "\n".join(lines).strip()
