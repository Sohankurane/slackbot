"""Computes dashboard metrics + time-series from the messages table."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bot, Message, SlackUser, Tenant

logger = logging.getLogger(__name__)


async def compute_dashboard_metrics(session: AsyncSession) -> dict:
    """Return headline metrics + a 14-day message time series."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)
    window_start = today_start - timedelta(days=13)  # 14-day window incl. today

    # --- Headline counts ---
    total_messages = (await session.execute(
        select(func.count(Message.id))
    )).scalar_one()

    messages_today = (await session.execute(
        select(func.count(Message.id)).where(Message.created_at >= today_start)
    )).scalar_one()

    ai_replies_total = (await session.execute(
        select(func.count(Message.id)).where(Message.kind == "ai_reply")
    )).scalar_one()

    ai_replies_week = (await session.execute(
        select(func.count(Message.id)).where(
            Message.kind == "ai_reply", Message.created_at >= week_start
        )
    )).scalar_one()

    # Active (non-deleted) users across all tenants
    active_users = (await session.execute(
        select(func.count(SlackUser.id)).where(SlackUser.is_deleted.is_(False))
    )).scalar_one()

    active_tenants = (await session.execute(
        select(func.count(Tenant.id)).where(Tenant.is_active.is_(True))
    )).scalar_one()

    active_bots = (await session.execute(
        select(func.count(Bot.id)).where(Bot.is_active.is_(True))
    )).scalar_one()

    ai_enabled_bots = (await session.execute(
        select(func.count(Bot.id)).where(
            Bot.is_active.is_(True), Bot.ai_enabled.is_(True)
        )
    )).scalar_one()

    # --- 14-day time series, split by direction ---
    rows = (await session.execute(
        select(
            func.date(Message.created_at).label("day"),
            Message.direction,
            func.count(Message.id).label("cnt"),
        )
        .where(Message.created_at >= window_start)
        .group_by(func.date(Message.created_at), Message.direction)
    )).all()

    # Build a dict {date_str: {inbound, outbound}}
    series_map: dict[str, dict[str, int]] = {}
    for day, direction, cnt in rows:
        key = str(day)
        bucket = series_map.setdefault(key, {"inbound": 0, "outbound": 0})
        if direction in bucket:
            bucket[direction] = cnt

    # Fill all 14 days (including zero days) in order
    series = []
    for i in range(14):
        d = (window_start + timedelta(days=i)).date()
        key = str(d)
        b = series_map.get(key, {"inbound": 0, "outbound": 0})
        series.append({
            "date": d.strftime("%d %b"),
            "inbound": b["inbound"],
            "outbound": b["outbound"],
        })

    return {
        "total_messages": total_messages,
        "messages_today": messages_today,
        "ai_replies_total": ai_replies_total,
        "ai_replies_week": ai_replies_week,
        "active_users": active_users,
        "active_tenants": active_tenants,
        "active_bots": active_bots,
        "ai_enabled_bots": ai_enabled_bots,
        "series": series,
    }