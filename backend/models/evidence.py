"""
SQLAlchemy ORM models for all 21 dataset evidence tables.
Exact column names matching BUILD-SPEC Section 2.1 verbatim.
"""
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Text, Date, DateTime, Boolean, Index
)
from backend.postgres import Base


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String(32), primary_key=True, index=True)
    case_title = Column(String(255), nullable=False)
    crime_type = Column(String(128), nullable=False, index=True)
    date_range_start = Column(String(32), nullable=True)
    date_range_end = Column(String(32), nullable=True)
    primary_location = Column(String(128), nullable=True, index=True)
    difficulty = Column(String(32), nullable=True, index=True)
    topology = Column(String(64), nullable=True)
    n_network_entities = Column(Integer, default=0)


class Person(Base):
    __tablename__ = "persons"

    person_id = Column(String(32), primary_key=True, index=True)
    full_name = Column(String(128), nullable=False, index=True)
    alias = Column(String(128), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(8), nullable=True)
    city = Column(String(64), nullable=True, index=True)
    occupation = Column(String(128), nullable=True)
    address = Column(Text, nullable=True)
    phone_ids = Column(Text, nullable=True)
    vehicle_ids = Column(Text, nullable=True)
    organization_ids = Column(Text, nullable=True)


class Phone(Base):
    __tablename__ = "phones"

    phone_id = Column(String(32), primary_key=True, index=True)
    person_id = Column(String(32), nullable=True, index=True)
    number = Column(String(32), nullable=False, index=True)


class SimCard(Base):
    __tablename__ = "sim_cards"

    sim_id = Column(String(32), primary_key=True, index=True)
    phone_id = Column(String(32), nullable=True, index=True)
    imsi = Column(String(32), nullable=True, index=True)
    operator = Column(String(64), nullable=True)
    activation_date = Column(String(32), nullable=True)


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(32), primary_key=True, index=True)
    imei = Column(String(32), nullable=False, index=True)
    make = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)


class PhoneSimImeiDevice(Base):
    __tablename__ = "phone_sim_imei_device"

    link_id = Column(String(32), primary_key=True, index=True)
    phone_id = Column(String(32), nullable=True, index=True)
    sim_id = Column(String(32), nullable=True, index=True)
    device_id = Column(String(32), nullable=True, index=True)
    person_id = Column(String(32), nullable=True, index=True)
    first_seen = Column(String(32), nullable=True)
    last_seen = Column(String(32), nullable=True)
    is_primary = Column(Boolean, default=False)


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id = Column(String(32), primary_key=True, index=True)
    registration_id = Column(String(32), nullable=False, index=True)
    vehicle_type = Column(String(64), nullable=True)
    make = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    color = Column(String(32), nullable=True)
    owner_person_id = Column(String(32), nullable=True, index=True)
    registration_city = Column(String(64), nullable=True)


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    account_id = Column(String(32), primary_key=True, index=True)
    person_id = Column(String(32), nullable=True, index=True)
    bank_name = Column(String(128), nullable=True)
    branch_city = Column(String(64), nullable=True)
    account_type = Column(String(64), nullable=True)
    opening_date = Column(String(32), nullable=True)


class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(String(32), primary_key=True, index=True)
    organization_name = Column(String(255), nullable=False, index=True)
    organization_type = Column(String(128), nullable=True)
    city = Column(String(64), nullable=True)
    address = Column(Text, nullable=True)


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(String(32), primary_key=True, index=True)
    city = Column(String(64), nullable=True, index=True)
    area = Column(String(128), nullable=True)
    location_name = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_type = Column(String(64), nullable=True)


class FIR(Base):
    __tablename__ = "fir"

    fir_id = Column(String(32), primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    fir_number = Column(String(64), nullable=False, index=True)
    police_station_id = Column(String(32), nullable=True)
    registration_date = Column(String(32), nullable=True)
    incident_date = Column(String(32), nullable=True)
    crime_type = Column(String(128), nullable=True)
    incident_city = Column(String(64), nullable=True)
    incident_area = Column(String(128), nullable=True)
    complainant_id = Column(String(32), nullable=True)
    victim_id = Column(String(32), nullable=True)
    officer_id = Column(String(32), nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(64), nullable=True)


class FIRPerson(Base):
    __tablename__ = "fir_person"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fir_id = Column(String(32), nullable=False, index=True)
    person_id = Column(String(32), nullable=False, index=True)
    role = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(64), nullable=True)


class CDR(Base):
    __tablename__ = "cdr"

    cdr_id = Column(String(32), primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    caller_phone_id = Column(String(32), nullable=False, index=True)
    receiver_phone_id = Column(String(32), nullable=False, index=True)
    timestamp = Column(String(32), nullable=False, index=True)
    duration_seconds = Column(Integer, default=0)
    call_type = Column(String(32), nullable=True)
    tower_location_id = Column(String(32), nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String(32), primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    timestamp = Column(String(32), nullable=False, index=True)
    sender_account = Column(String(32), nullable=False, index=True)
    receiver_account = Column(String(32), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(64), nullable=True)
    location = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)


class TransactionTypology(Base):
    __tablename__ = "transactions_typology"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String(32), nullable=False, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    timestamp = Column(String(32), nullable=True)
    sender_account = Column(String(32), nullable=True)
    receiver_account = Column(String(32), nullable=True)
    amount = Column(Float, nullable=True)
    transaction_type = Column(String(64), nullable=True)
    location = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)


class CCTVCamera(Base):
    __tablename__ = "cctv_cameras"

    camera_id = Column(String(32), primary_key=True, index=True)
    location_id = Column(String(32), nullable=True, index=True)
    camera_type = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)


class CCTVAnprEvent(Base):
    __tablename__ = "cctv_anpr_events"

    event_id = Column(String(32), primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    camera_id = Column(String(32), nullable=True)
    location_id = Column(String(32), nullable=True, index=True)
    timestamp = Column(String(32), nullable=True)
    detection_type = Column(String(64), nullable=True)
    plate_number = Column(String(32), nullable=True, index=True)
    description = Column(Text, nullable=True)


class LocationEvent(Base):
    __tablename__ = "location_events"

    event_id = Column(String(32), primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    person_id = Column(String(32), nullable=False, index=True)
    location_id = Column(String(32), nullable=True, index=True)
    timestamp = Column(String(32), nullable=True)
    event_type = Column(String(64), nullable=True)
    source = Column(String(64), nullable=True)


class Relationship(Base):
    __tablename__ = "relationships"

    relationship_id = Column(String(32), primary_key=True, index=True)
    source_entity = Column(String(32), nullable=False, index=True)
    target_entity = Column(String(32), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False, index=True)
    timestamp = Column(String(32), nullable=True)
    source_record = Column(String(64), nullable=True)
    confidence = Column(Float, default=1.0)


class EvidenceMetadata(Base):
    __tablename__ = "evidence_metadata"

    evidence_id = Column(String(32), primary_key=True, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    source_table = Column(String(64), nullable=True)
    record_id = Column(String(64), nullable=True)
    evidence_type = Column(String(64), nullable=True)
    collected_date = Column(String(32), nullable=True)
    custodian = Column(String(128), nullable=True)


class EvidenceHashChain(Base):
    __tablename__ = "evidence_hash_chain"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    evidence_id = Column(String(32), nullable=False, index=True)
    case_id = Column(String(32), nullable=False, index=True)
    source_table = Column(String(64), nullable=True)
    record_id = Column(String(64), nullable=True)
    sequence_index = Column(Integer, nullable=True)
    content_sha256 = Column(String(64), nullable=False)
    previous_hash = Column(String(64), nullable=True)
    block_hash = Column(String(64), nullable=True)
