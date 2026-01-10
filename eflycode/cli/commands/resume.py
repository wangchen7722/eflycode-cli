"""恢复会话命令"""

import asyncio
from typing import Optional

from eflycode.cli.components.select import SelectComponent
from eflycode.cli.main import run_interactive_cli
from eflycode.core.agent.session_store import SessionStore


async def _select_session() -> Optional[str]:
    store = SessionStore.get_instance()
    sessions = store.list_recent()
    if not sessions:
        return None

    options = []
    for session in sessions:
        session_id = session["id"]
        count = session.get("message_count")
        label = session_id
        if count is not None:
            label = f"{label}  ({count} messages)"

        desc_parts = []
        updated_at = session.get("updated_at")
        if updated_at:
            desc_parts.append(f"updated {updated_at}")
        last_user_preview = session.get("last_user_message_preview")
        if last_user_preview:
            desc_parts.append(last_user_preview)

        description = " | ".join(desc_parts) if desc_parts else None
        options.append(
            {
                "key": session_id,
                "label": label,
                "description": description,
            }
        )

    select_component = SelectComponent()
    selected = await select_component.show(
        title="Select session to resume",
        options=options,
        default_key=sessions[0]["id"],
    )
    return selected


def resume_command(args) -> None:
    """恢复指定会话并进入交互式模式"""
    if args.session_id:
        asyncio.run(run_interactive_cli(resume_session_id=args.session_id))
        return

    async def _run() -> None:
        selected = await _select_session()
        if not selected:
            raise ValueError("没有可恢复的会话")
        await run_interactive_cli(resume_session_id=selected)

    asyncio.run(_run())
