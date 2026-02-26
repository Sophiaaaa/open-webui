from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from open_webui.apps.bots.runtime_config import (
    is_user_allowed_for_bot,
    load_bots_runtime_config,
)
from open_webui.internal.db import get_session
from open_webui.models.groups import Groups
from open_webui.utils.auth import get_verified_user


router = APIRouter()


@router.get("/access")
async def get_bots_access(user=Depends(get_verified_user), db: Session = Depends(get_session)):
    cfg = load_bots_runtime_config()

    groups = Groups.get_groups_by_member_id(user.id, db=db)
    user_group_names = [g.name for g in (groups or [])]

    return {
        "kpi_bot": is_user_allowed_for_bot(user, cfg.kpi_access, user_group_names),
        "bkm_bot": is_user_allowed_for_bot(user, cfg.bkm_access, user_group_names),
    }

