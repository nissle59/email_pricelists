from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship, mapped_column, Mapped

from utils.db import Base


class Filters(Base):
    __tablename__ = "emailfilters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    senders: Mapped[str] = mapped_column(String, unique=True, default="")
    vendor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("vendors.id"))
    subject_contains: Mapped[str | None] = mapped_column(String)
    subject_excludes: Mapped[str | None] = mapped_column(String)
    filename_contains: Mapped[str | None] = mapped_column(String)
    filename_excludes: Mapped[str | None] = mapped_column(String)
    extensions: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    vendor: Mapped["Vendor"] = relationship(back_populates="filters")
    filters_configs: Mapped["RefFiltersConfigs"] = relationship(back_populates="filter", cascade="all, delete-orphan")

    def as_dict(self):
        d = {
            "id": self.id,
            "name": self.name,
            "senders": self.senders,
            "subject_contains": self.subject_contains,
            "subject_excludes": self.subject_excludes,
            "filename_contains": self.filename_contains,
            "filename_excludes": self.filename_excludes,
            "extensions": self.extensions,
            "active": self.active
        }
        if self.subject_contains in [None, ""] \
                and self.subject_excludes in [None, ""] \
                and self.filename_contains in [None, ""] \
                and self.filename_excludes in [None, ""]:
            d["accept_all"] = True
        else:
            d["accept_all"] = False
        return d


class RefFiltersConfigs(Base):
    __tablename__ = "ref_filters_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filter_id: Mapped[int] = mapped_column(Integer, ForeignKey("emailfilters.id", ondelete="CASCADE"), index=True)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("parsing_configs.id"), index=True)

    config: Mapped["ParsingConfig"] = relationship(back_populates="filters_configs")
    filter: Mapped["Filters"] = relationship(back_populates="filters_configs")