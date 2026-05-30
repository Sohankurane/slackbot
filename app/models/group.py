"""User Workspace Groups — named groups of Slack users within a tenant."""

from sqlalchemy import Boolean, ForeignKey, Index, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    __tablename__ = "groups"
    __table_args__ = (
        Index("uq_group_name_per_tenant", "tenant_id", "name", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    can_use_bot: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=false(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Group {self.name} tenant_id={self.tenant_id}>"


class GroupMember(Base, TimestampMixin):
    __tablename__ = "group_members"
    __table_args__ = (
        Index("uq_member_per_group", "group_id", "slack_user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    slack_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<GroupMember group={self.group_id} user={self.slack_user_id}>"