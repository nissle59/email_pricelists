# models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    required = Column(Boolean, default=False, nullable=False)

    mappings = relationship("RoleMapping", back_populates="role")

    def __repr__(self):
        return f"<Role(id={self.id} name={self.name} required={self.required})>"

class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    configs = relationship("ParsingConfig", back_populates="vendor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vendor(id={self.id} name={self.name})>"

class ParsingConfig(Base):
    __tablename__ = "parsing_configs"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)      # например "velomag"
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    header_row = Column(Integer, nullable=False)

    vendor = relationship("Vendor", back_populates="configs")
    mappings = relationship("RoleMapping", back_populates="config", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ParsingConfig(id={self.id} name={self.name} header_row={self.header_row} vendor_id={self.vendor_id})>"

class RoleMapping(Base):
    __tablename__ = "role_mappings"
    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, ForeignKey("parsing_configs.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    column_name = Column(String, nullable=False)  # имя колонки в Excel, например "Номенклатура"

    config = relationship("ParsingConfig", back_populates="mappings")
    role = relationship("Role", back_populates="mappings")

    __table_args__ = (
        UniqueConstraint('config_id', 'role_id', name='_config_role_uc'),
    )

    def __repr__(self):
        return f"<RoleMapping(config_id={self.config_id} role_id={self.role_id} column={self.column_name})>"