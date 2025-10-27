# crud.py
from sqlalchemy.exc import NoResultFound
from utils.db import SessionLocal
from models import Role, Vendor, ParsingConfig, RoleMapping

def add_role(name: str, required: bool = False):
    with SessionLocal() as s:
        r = s.query(Role).filter_by(name=name).first()
        if not r:
            r = Role(name=name, required=required)
            s.add(r)
            s.commit()
            s.refresh(r)
        return r

def list_roles():
    with SessionLocal() as s:
        return s.query(Role).order_by(Role.id).all()

def get_role_by_name(name: str):
    with SessionLocal() as s:
        return s.query(Role).filter_by(name=name).first()

def add_vendor(name: str):
    with SessionLocal() as s:
        v = s.query(Vendor).filter_by(name=name).first()
        if not v:
            v = Vendor(name=name)
            s.add(v)
            s.commit()
            s.refresh(v)
        return v

def list_vendors():
    with SessionLocal() as s:
        return s.query(Vendor).order_by(Vendor.name).all()

def get_vendor_by_name(name: str):
    with SessionLocal() as s:
        return s.query(Vendor).filter_by(name=name).first()

def save_config(config_name: str, vendor_name: str|None, header_row: int, roles_mapping: dict):
    """
    roles_mapping: { role_name: column_name }
    Если роль не существует — создастся с required=False
    """
    with SessionLocal() as s:
        # vendor
        vendor = None
        if vendor_name:
            vendor = s.query(Vendor).filter_by(name=vendor_name).first()
            if not vendor:
                vendor = Vendor(name=vendor_name)
                s.add(vendor)
                s.commit()
                s.refresh(vendor)

        cfg = s.query(ParsingConfig).filter_by(name=config_name).first()
        if not cfg:
            cfg = ParsingConfig(name=config_name, vendor_id=(vendor.id if vendor else None), header_row=header_row)
            s.add(cfg)
            s.commit()
            s.refresh(cfg)
        else:
            # обновляем
            cfg.header_row = header_row
            cfg.vendor_id = vendor.id if vendor else None
            # удалить старые mappings
            cfg.mappings.clear()
            s.flush()

        # добавить mappings
        for role_name, col_name in roles_mapping.items():
            role = s.query(Role).filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name, required=False)
                s.add(role)
                s.flush()
                s.refresh(role)
            mapping = RoleMapping(config_id=cfg.id, role_id=role.id, column_name=col_name)
            cfg.mappings.append(mapping)

        s.commit()
        s.refresh(cfg)
        return cfg

def load_config_by_name(config_name: str):
    """Возвращает dict {'id', 'name', 'vendor', 'header_row', 'roles_mapping'} или None"""
    with SessionLocal() as s:
        cfg = s.query(ParsingConfig).filter_by(name=config_name).first()
        if not cfg:
            return None
        roles_map = {m.role.name: m.column_name for m in cfg.mappings}
        return {
            "id": cfg.id,
            "name": cfg.name,
            "vendor": cfg.vendor.name if cfg.vendor else None,
            "header_row": cfg.header_row,
            "roles_mapping": roles_map
        }

def list_configs_for_vendor(vendor_name: str):
    with SessionLocal() as s:
        v = s.query(Vendor).filter_by(name=vendor_name).first()
        if not v:
            return []
        return s.query(ParsingConfig).filter_by(vendor_id=v.id).all()

def list_all_configs():
    with SessionLocal() as s:
        return s.query(ParsingConfig).order_by(ParsingConfig.name).all()

def validate_config(config_name: str):
    """
    Проверяет, что конфиг содержит все обязательные роли (из таблицы roles.required=True).
    Возвращает (True, None) или (False, ["role1", "role2"])
    """
    with SessionLocal() as s:
        cfg = s.query(ParsingConfig).filter_by(name=config_name).first()
        if not cfg:
            return False, ["config_not_found"]
        required_roles = s.query(Role).filter_by(required=True).all()
        missing = []
        mapped_role_names = {m.role.name for m in cfg.mappings}
        for r in required_roles:
            if r.name not in mapped_role_names:
                missing.append(r.name)
        return (len(missing) == 0), missing