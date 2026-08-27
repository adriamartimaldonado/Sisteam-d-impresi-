# -*- coding: utf-8 -*-
"""Modelo de datos del central (PostgreSQL), segun §11 del documento de contexto.

Los estados se guardan como texto usando los valores del contrato compartido
(`comun.contrato`), la unica fuente de verdad. La estructura fisica exacta la fija
la migracion Alembic `0001_inicial`; estos modelos deben coincidir con ella.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from comun.contrato import EstadoPedido, EstadoTrabajo


class Base(DeclarativeBase):
    pass


class Sede(Base):
    __tablename__ = "sede"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)


class ClienteApi(Base):
    __tablename__ = "cliente_api"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey("sede.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    rol: Mapped[str] = mapped_column(String(16), nullable=False)   # origen|puesto|lectura
    clave_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class Puesto(Base):
    __tablename__ = "puesto"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey("sede.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    capacidades: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    ultimo_latido: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Impresora(Base):
    __tablename__ = "impresora"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    puesto_id: Mapped[int] = mapped_column(ForeignKey("puesto.id"), nullable=False)
    modelo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    puerto: Mapped[int] = mapped_column(Integer, nullable=False, default=9100)
    dpi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rfid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Plantilla(Base):
    __tablename__ = "plantilla"
    __table_args__ = (UniqueConstraint("codigo", "version", name="uq_plantilla_codigo_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)          # ZPL / plantilla
    campos: Mapped[list | dict] = mapped_column(JSONB, nullable=False)    # spec de columnas


class Pedido(Base):
    __tablename__ = "pedido"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey("sede.id"), nullable=False)
    clave_idem: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    plantilla_id: Mapped[int] = mapped_column(ForeignKey("plantilla.id"), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    max_puestos: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estado: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EstadoPedido.ABIERTO.value)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("cliente_api.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)

    trabajos: Mapped[list["Trabajo"]] = relationship(back_populates="pedido")


class Sesion(Base):
    __tablename__ = "sesion"
    __table_args__ = ()
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), nullable=False)
    puesto_id: Mapped[int] = mapped_column(ForeignKey("puesto.id"), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False)
    abierta_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    preparada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pruebas_impresas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validada_por: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Trabajo(Base):
    __tablename__ = "trabajo"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    datos: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EstadoTrabajo.PENDIENTE.value)
    sesion_id: Mapped[int | None] = mapped_column(ForeignKey("sesion.id"), nullable=True)
    puesto_id: Mapped[int | None] = mapped_column(ForeignKey("puesto.id"), nullable=True)
    reclamado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    pedido: Mapped["Pedido"] = relationship(back_populates="trabajos")


class Evento(Base):
    __tablename__ = "evento"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(48), nullable=False)
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedido.id"), nullable=True)
    trabajo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trabajo.id"), nullable=True)
    datos: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
