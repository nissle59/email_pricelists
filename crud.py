# crud.py
import json
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.orm import selectinload, joinedload

from models.email import RefFiltersConfigs
from utils.db import SessionLocal
from models import Role, Vendor, ParsingConfig, RoleMapping, Filters, Settings, Letter, Attachment


def list_email_filters():
    with SessionLocal() as s:
        r = s.query(Filters).options(joinedload(Filters.vendor)).all()
        return s.query(Filters).all()


def add_email_filter(filter: Filters):
    with SessionLocal() as s:
        s.add(filter)
        s.commit()
        s.refresh(filter)
        v = s.query(Vendor).filter_by(name=filter.name).first()
        if not v:
            v = Vendor(name=filter.name)
            s.add(v)
            s.commit()
            s.refresh(v)
        filter.vendor_id = v.id
        s.commit()
        s.refresh(filter)
        return filter


def set_email_filter_vendor_id(filter_id: int, vendor_id: int):
    with SessionLocal() as s:
        db_filter: Filters = s.query(Filters).filter(Filters.id == filter_id).first()
        if db_filter:
            db_filter.vendor_id = vendor_id
            s.commit()
            s.refresh(db_filter)
            return db_filter
        else:
            raise NoResultFound("Filter not found")


def get_email_filter(filter_id: int):
    with SessionLocal() as s:
        return s.query(Filters).options(joinedload(Filters.vendor)).filter(Filters.id == filter_id).first()


def get_email_filter_by_vendor(vendor_id: int):
    with SessionLocal() as s:
        return s.query(Filters).options(joinedload(Filters.vendor)).filter(Filters.vendor_id == vendor_id).first()


def get_email_filter_by_name(name: str):
    with SessionLocal() as s:
        return s.query(Filters).options(joinedload(Filters.vendor)).filter(Filters.name == name).first()


def update_email_filter(filter_id: int, filter: Filters):
    with SessionLocal() as s:
        db_filter: Filters = s.query(Filters).filter(Filters.id == filter_id).first()
        if db_filter:
            db_filter.name = filter.name
            db_filter.subject_contains = filter.subject_contains
            db_filter.subject_excludes = filter.subject_excludes
            db_filter.filename_contains = filter.filename_contains
            db_filter.filename_excludes = filter.filename_excludes
            db_filter.senders = filter.senders
            db_filter.extensions = filter.extensions
            db_filter.active = db_filter.active
            s.commit()
            s.refresh(db_filter)
            return db_filter
        else:
            raise NoResultFound("Filter not found")


def delete_email_filter(filter_id: int):
    with SessionLocal() as s:
        db_filter: Filters = s.query(Filters).filter(Filters.id == filter_id).first()
        # cfgs: list[ParsingConfig] = ...
        if db_filter:
            s.delete(db_filter)
            s.commit()
            v = s.query(Vendor).filter(Vendor.id == db_filter.vendor_id).first()
            if v:
                s.delete(v)
                s.commit()
                s.refresh(v)
            return True
        else:
            raise NoResultFound("Filter not found")


def get_settings():
    with SessionLocal() as s:
        settings = s.query(Settings).all()
        return {item.setting: item.value for item in settings}


def set_settings(settings: dict):
    with SessionLocal() as s:
        for key, value in settings.items():
            setting = s.query(Settings).filter_by(setting=key).first()
            if setting:
                setting.value = value
            else:
                setting = Settings(setting=key, value=value)
                s.add(setting)
        s.commit()
        return settings


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


def update_role(id: int, name: str, required: bool = False):
    with SessionLocal() as s:
        r = s.query(Role).filter_by(id=id).first()
        if r:
            r.name = name
            r.required = required
            s.commit()
            s.refresh(r)
        return r


def delete_role(id: int):
    with SessionLocal() as s:
        r = s.query(Role).filter_by(id=id).first()
        if r:
            s.delete(r)
            s.commit()
        return r


def add_vendor(name: str):
    with SessionLocal() as s:
        v = s.query(Vendor).filter_by(name=name).first()
        if not v:
            v = Vendor(name=name)
            s.add(v)
            s.commit()
            s.refresh(v)
        return v


def toggle_vendor(id: int):
    with SessionLocal() as s:
        v = s.query(Vendor).filter_by(id=id).first()
        if v.active:
            v.active = False
        else:
            v.active = True
        s.commit()
        s.refresh(v)
        return v


def list_vendors() -> list[Vendor]:
    with SessionLocal() as s:
        return s.query(Vendor).order_by(Vendor.name).all()


def set_vendor_last_load(vendor_id: int, last_load: datetime):
    with SessionLocal() as s:
        stmt = update(Vendor).where(Vendor.id == vendor_id).values(last_load=last_load)
        result = s.execute(stmt)
        s.commit()
        if result.rowcount > 0:
            updated_vendor = s.get(Vendor, vendor_id)
            return updated_vendor
        return None


def get_vendor_by_name(name: str):
    with SessionLocal() as s:
        return s.query(Vendor).filter_by(name=name).first()


def get_vendor_name_by_id(id: int):
    with SessionLocal() as s:
        try:
            return s.query(Vendor).filter_by(id=id).first().name
        except AttributeError:
            return ""


def get_config_by_name(name: str):
    with SessionLocal() as s:
        try:
            return s.query(ParsingConfig).filter_by(name=name).first()
        except AttributeError:
            return None


def update_config(id: int, vendor_name: str | None, filename_template: str | None = None):
    with SessionLocal() as s:
        config: ParsingConfig = s.query(ParsingConfig).filter_by(id=id).first()
        if config:
            if vendor_name:
                config.vendor_id = get_vendor_by_name(vendor_name).id
            if filename_template:
                config.filename_template = filename_template
            s.commit()
            s.refresh(config)
        return config


def set_ref_filter_config(filter_id: int, config_id: int):
    with SessionLocal() as s:
        ref = RefFiltersConfigs(
            filter_id=filter_id,
            config_id=config_id
        )
        s.add(ref)
        s.commit()
        s.refresh(ref)
        return ref


def save_config(
        config_name: str,
        vendor_name: str,
        roles_mapping: dict | None = None,
        header_row: int | None = None,
        filename_pattern: str | None = None,
        to_common: bool | None = None,
        active: bool | None = None,
        save_original: bool | None = None,
        save_parsed: bool | None = None,
        quantum_config: dict | None = None
):
    """
    roles_mapping: { role_name: column_name }
    Если роль не существует — создастся с required=False.
    Если конфигурация существует, обновляются header_row и mappings при изменении.
    """
    with SessionLocal() as s:
        # --- 1. Получаем или создаём вендора ---
        stmt_vendor = select(Vendor).where(Vendor.name == vendor_name)
        vendor = s.execute(stmt_vendor).scalar_one_or_none()
        if vendor is None:
            vendor = Vendor(name=vendor_name)
            s.add(vendor)
            s.flush()  # чтобы получить vendor.id

        # --- 2. Получаем или создаём ParsingConfig ---
        stmt_cfg = (
            select(ParsingConfig)
            .join(ParsingConfig.vendor)
            .where(Vendor.name == vendor_name)
            .where(ParsingConfig.name == config_name)
        )
        cfg = s.execute(stmt_cfg).scalar_one_or_none()

        if cfg is None:
            # создаём новую конфигурацию
            cfg = ParsingConfig(
                name=config_name,
                vendor_id=vendor.id,
                header_row=header_row,
                filename_template=None
            )
            if header_row is not None:
                cfg.header_row = header_row
            if filename_pattern is not None:
                cfg.filename_template = filename_pattern
            if active is not None:
                cfg.active = active
            if to_common is not None:
                cfg.to_common = to_common
            if save_original is not None:
                cfg.save_original = save_original
            if save_parsed is not None:
                cfg.save_parsed = save_parsed
            if quantum_config is not None:
                cfg.quantum_config = json.dumps(quantum_config, indent=2, ensure_ascii=False)
            s.add(cfg)
            s.flush()
            # добавляем mappings ниже (поскольку их не было)
            existing = {}
        else:
            # обновляем header_row и vendor_id при изменении
            updated = False
            if cfg.header_row != header_row and header_row is not None:
                cfg.header_row = header_row
                updated = True
            if cfg.filename_template != filename_pattern and filename_pattern is not None:
                cfg.filename_template = filename_pattern
                updated = True
            if cfg.vendor_id != vendor.id:
                cfg.vendor_id = vendor.id
                updated = True

            if cfg.active != active and active is not None:
                cfg.active = active
                updated = True
            if cfg.to_common != to_common and to_common is not None:
                cfg.to_common = to_common
                updated = True
            if cfg.save_original != save_original and save_original is not None:
                cfg.save_original = save_original
                updated = True
            if cfg.save_parsed != save_parsed and save_parsed is not None:
                cfg.save_parsed = save_parsed
                updated = True
            if cfg.quantum_config != quantum_config and quantum_config is not None:
                cfg.quantum_config = json.dumps(quantum_config, indent=2, ensure_ascii=False)
                updated = True

            # подготовим словарь существующих mapping'ов (role_name -> column_name)
            # обращаемся к cfg.mappings — они могут быть ленивыми, но сессия открыта
            existing = {m.role.name: m.column_name for m in cfg.mappings}

            # если словари совпадают — не трогаем mappings
            if existing == roles_mapping or roles_mapping is None:
                # ничего менять не нужно — завершаем (но всё равно коммитим возможные vendor/header изменения)
                if updated:
                    s.add(cfg)
                s.commit()
                s.refresh(cfg)
                return cfg

            # если разные — очистим текущие mapping'и и будем воссоздавать/обновлять
            # вариант: можно обновлять диффами, но проще и надёжнее — синхронизировать ниже
            # Не очищаем заранее — синхронизация ниже обновит/создаст/удалит записи.
            # однако если хочется очистить — можно:
            # cfg.mappings.clear()
            # s.flush()

            # --- 3. Синхронизация mappings ---
            # Подход: для каждой пары role_name, col_name — убедиться, что в БД есть соответствующий RoleMapping.
            # Также удалим лишние mappings, которые есть в existing, но отсутствуют в roles_mapping.
        if roles_mapping:
            role_names_to_keep = set(roles_mapping.keys())
            existing_role_names = set(existing.keys())

            # Удаляем mappings, которые больше не нужны
            to_delete = existing_role_names - role_names_to_keep
            if to_delete:
                # находим эти mapping'и и удаляем
                stmt_del = (
                    select(RoleMapping)
                    .join(Role)
                    .where(RoleMapping.config_id == cfg.id)
                    .where(Role.name.in_(list(to_delete)))
                )
                rows = s.execute(stmt_del).scalars().all()
                for r in rows:
                    s.delete(r)
                s.flush()

            # Для каждой требуемой роли — обновим или создадим mapping
            for role_name, col_name in roles_mapping.items():
                # найдем или создадим Role
                stmt_role = select(Role).where(Role.name == role_name)
                role = s.execute(stmt_role).scalar_one_or_none()
                if role is None:
                    role = Role(name=role_name, required=False)
                    s.add(role)
                    s.flush()  # чтобы получить role.id

                # найдем существующий RoleMapping для (cfg.id, role.id)
                stmt_map = (
                    select(RoleMapping)
                    .where(RoleMapping.config_id == cfg.id)
                    .where(RoleMapping.role_id == role.id)
                )
                mapping = s.execute(stmt_map).scalar_one_or_none()

                if mapping is None:
                    # создаём новый mapping
                    try:
                        mapping = RoleMapping(config_id=cfg.id, role_id=role.id, column_name=col_name)
                        s.add(mapping)
                        s.flush()
                    except IntegrityError:
                        s.rollback()
                        # попытка создать еще раз — на случай гонки
                        mapping = s.execute(stmt_map).scalar_one_or_none()
                        if mapping is None:
                            # если всё ещё нет — пробуем вставить напрямую
                            s.begin()
                            try:
                                mapping = RoleMapping(config_id=cfg.id, role_id=role.id, column_name=col_name)
                                s.add(mapping)
                                s.flush()
                            except Exception:
                                s.rollback()
                                raise
                else:
                    # если найден — обновим column_name при отличии
                    if mapping.column_name != col_name:
                        mapping.column_name = col_name
                        s.add(mapping)

        # --- 4. Финализируем ---
        s.commit()
        s.refresh(cfg)
        return cfg


def delete_config(config_id: int):
    """Удаляет конфигурацию по id"""
    with SessionLocal() as s:
        cfg = s.query(ParsingConfig).filter_by(id=config_id).first()
        if cfg:
            s.delete(cfg)
            s.commit()
            return True
        else:
            return False


def load_config_by_name(config_name: str, vendor_name: str | None = None):
    """Возвращает dict {'id', 'name', 'vendor', 'header_row', 'roles_mapping'} или None"""
    with SessionLocal() as s:
        if vendor_name:
            vendor = s.query(Vendor).filter_by(name=vendor_name).first()
        cfg = s.query(ParsingConfig).filter_by(name=config_name)
        if vendor_name and vendor:
            cfg = cfg.filter_by(vendor_id=vendor.id)
        cfg = cfg.first()
        if not cfg:
            return None
        roles_map = {m.role.name: m.column_name for m in cfg.mappings}
        return {
            "id": cfg.id,
            "name": cfg.name,
            "vendor": cfg.vendor.name if cfg.vendor else None,
            "header_row": cfg.header_row,
            "roles_mapping": roles_map,
            "quantum_config": json.loads(cfg.quantum_config) if cfg.quantum_config else None,
        }


def list_configs_for_vendor(vendor_name: str) -> list[ParsingConfig]:
    with SessionLocal() as session:
        stmt = (
            select(ParsingConfig)
            .join(ParsingConfig.vendor)  # Предполагаем отношение vendor в ParsingConfig
            .where(Vendor.name == vendor_name)
            .options(
                selectinload(ParsingConfig.mappings)
                .selectinload(RoleMapping.role)
            )
        )

        result = session.execute(stmt)
        return list(result.scalars().all())


def list_configs_for_vendor_dict(vendor_name: str) -> dict:
    configs = list_configs_for_vendor(vendor_name)
    out = {}
    for config in configs:
        d = {}
        d.update({'header_row': config.header_row})
        d.update({'pattern': config.filename_template})
        if config.mappings:
            d.update({'roles_mapping': {}})
        for mapping in config.mappings:
            d['roles_mapping'].update({mapping.role.name: mapping.column_name})
        out.update({config.id: d})
    return out


def list_all_configs():
    with SessionLocal() as s:
        stmt = (
            select(ParsingConfig)
            .join(ParsingConfig.vendor)  # Предполагаем отношение vendor в ParsingConfig
            .options(
                selectinload(ParsingConfig.mappings)
                .selectinload(RoleMapping.role)
            )
        )

        result = s.execute(stmt)
        return list(result.scalars().all())


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


def add_letter(letter: Letter):
    with SessionLocal() as s:
        s.add(letter)
        s.commit()
        s.refresh(letter)
        return letter.id


def list_letters(vendor_id: int | None = None, days: int | None = None):
    with SessionLocal() as s:
        q = (
            s.query(Letter)
            .options(selectinload(Letter.attachments))
        )
        if vendor_id:
            q = q.filter(Letter.vendor_id == vendor_id)
        if days is not None:
            since_date = datetime.now() - timedelta(days=days)
            q = q.filter(Letter.date >= since_date)
        return q.all()


def find_attachment_by_filename(filename: str):
    with SessionLocal() as s:
        return s.query(Attachment).filter(Attachment.file_name == filename).first()


def list_letters_email_ids():
    with SessionLocal() as s:
        return [l[0] for l in s.query(Letter.letter_id).all()]


def add_attachment(attachment: Attachment):
    with SessionLocal() as s:
        s.add(attachment)
        s.commit()
        s.refresh(attachment)
        return attachment.id


def list_attachments_by_vendor(vendor_id: int):
    with SessionLocal() as s:
        letters = s.query(Letter).options(selectinload(Letter.attachments)).filter(Letter.vendor_id == vendor_id).all()
        attachments = [a for l in letters for a in l.attachments]
        return attachments
