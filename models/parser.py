from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, DateTime
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from utils.db import Base


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)

    mappings: Mapped[list["RoleMapping"]] = relationship(back_populates="role")

    def __repr__(self):
        return f"<Role(id={self.id} name={self.name} required={self.required})>"


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    last_load: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    configs: Mapped[list["ParsingConfig"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    filters: Mapped[list["Filters"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    letters: Mapped[list["Letter"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vendor(id={self.id} name={self.name})>"


class ParsingConfig(Base):
    __tablename__ = "parsing_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=False)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    header_row: Mapped[int] = mapped_column(Integer)
    filename_template: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    to_common: Mapped[bool | None] = mapped_column(Boolean, default=True)
    save_original: Mapped[bool | None] = mapped_column(Boolean, default=False)
    save_parsed: Mapped[bool | None] = mapped_column(Boolean, default=False)

    vendor: Mapped[list["Vendor"]] = relationship(back_populates="configs")
    mappings: Mapped[list["RoleMapping"]] = relationship(back_populates="config", cascade="all, delete-orphan")
    filters_configs: Mapped[list["RefFiltersConfigs"]] = relationship(back_populates="config")

    def __repr__(self):
        return f"<ParsingConfig(id={self.id} name={self.name} header_row={self.header_row} vendor_id={self.vendor_id})>"


class RoleMapping(Base):
    __tablename__ = "role_mappings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("parsing_configs.id"))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    column_name: Mapped[str] = mapped_column(String)  # имя колонки в Excel, например "Номенклатура"

    config: Mapped["ParsingConfig"] = relationship(back_populates="mappings")
    role: Mapped["Role"] = relationship(back_populates="mappings")

    __table_args__ = (
        UniqueConstraint('config_id', 'role_id', name='_config_role_uc'),
    )

    def __repr__(self):
        return f"<RoleMapping(config_id={self.config_id} role_id={self.role_id} column={self.column_name})>"
