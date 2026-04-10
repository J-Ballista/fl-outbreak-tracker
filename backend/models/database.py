from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:devpassword@localhost:5432/fl_outbreak",
)

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# County
# ---------------------------------------------------------------------------

class County(Base):
    """One row per Florida county (67 total)."""

    __tablename__ = "counties"

    fips_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    population: Mapped[Optional[int]] = mapped_column(Integer)
    centroid_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    centroid_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))

    cases: Mapped[list["DiseaseCase"]] = relationship(back_populates="county")
    vaccination_rates: Mapped[list["VaccinationRate"]] = relationship(back_populates="county")
    alerts: Mapped[list["OutbreakAlert"]] = relationship(back_populates="county")

    def __repr__(self) -> str:
        return f"<County fips={self.fips_code} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Disease
# ---------------------------------------------------------------------------

class Disease(Base):
    """Reference table of vaccine-preventable diseases tracked by the system."""

    __tablename__ = "diseases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(64))          # e.g. "respiratory", "enteric"
    icd10_code: Mapped[Optional[str]] = mapped_column(String(16))
    herd_threshold_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # 0–100
    r0_estimate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    medical_contraindication_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # % of population unable to vaccinate for medical reasons

    cases: Mapped[list["DiseaseCase"]] = relationship(back_populates="disease")
    vaccination_rates: Mapped[list["VaccinationRate"]] = relationship(back_populates="disease")
    alerts: Mapped[list["OutbreakAlert"]] = relationship(back_populates="disease")

    def __repr__(self) -> str:
        return f"<Disease id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# DiseaseCase
# ---------------------------------------------------------------------------

class DiseaseCase(Base):
    """Individual case reports aggregated by county/disease/date/age-group."""

    __tablename__ = "disease_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    county_fips: Mapped[str] = mapped_column(
        String(5), ForeignKey("counties.fips_code"), nullable=False, index=True
    )
    disease_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("diseases.id"), nullable=False, index=True
    )
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_count: Mapped[Optional[int]] = mapped_column(Integer)
    probable_count: Mapped[Optional[int]] = mapped_column(Integer)
    age_group: Mapped[Optional[str]] = mapped_column(String(32))         # e.g. "0-4", "5-17", "18-64", "65+"
    acquisition: Mapped[Optional[str]] = mapped_column(String(32))       # "community", "travel", "unknown"
    source: Mapped[Optional[str]] = mapped_column(String(128))           # originating data source URL / label
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    county: Mapped["County"] = relationship(back_populates="cases")
    disease: Mapped["Disease"] = relationship(back_populates="cases")

    def __repr__(self) -> str:
        return (
            f"<DiseaseCase id={self.id} disease_id={self.disease_id} "
            f"county={self.county_fips} date={self.report_date}>"
        )


# ---------------------------------------------------------------------------
# VaccinationRate
# ---------------------------------------------------------------------------

class VaccinationRate(Base):
    """Annual vaccination/exemption survey results per county, disease, and facility type."""

    __tablename__ = "vaccination_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    county_fips: Mapped[str] = mapped_column(
        String(5), ForeignKey("counties.fips_code"), nullable=False, index=True
    )
    disease_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("diseases.id"), nullable=False, index=True
    )
    facility_type: Mapped[Optional[str]] = mapped_column(String(64))     # "school", "childcare", "college", etc.
    vaccinated_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    exempt_medical_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    exempt_religious_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    source: Mapped[Optional[str]] = mapped_column(String(128))

    county: Mapped["County"] = relationship(back_populates="vaccination_rates")
    disease: Mapped["Disease"] = relationship(back_populates="vaccination_rates")

    def __repr__(self) -> str:
        return (
            f"<VaccinationRate id={self.id} year={self.survey_year} "
            f"county={self.county_fips} disease_id={self.disease_id}>"
        )


# ---------------------------------------------------------------------------
# NewsArticle
# ---------------------------------------------------------------------------

class NewsArticle(Base):
    """Raw article ingested from an RSS news feed."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    source: Mapped[Optional[str]] = mapped_column(String(128))           # "Orlando Sentinel", "Miami Herald", etc.
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    signals: Mapped[list["ArticleSignal"]] = relationship(back_populates="article")

    def __repr__(self) -> str:
        return f"<NewsArticle id={self.id} source={self.source!r} url={self.url[:60]!r}>"


# ---------------------------------------------------------------------------
# ArticleSignal
# ---------------------------------------------------------------------------

class ArticleSignal(Base):
    """NLP-extracted disease/county/count signal from a single news article."""

    __tablename__ = "article_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news_articles.id"), nullable=False, index=True
    )
    county_fips: Mapped[Optional[str]] = mapped_column(
        String(5), ForeignKey("counties.fips_code"), index=True
    )
    disease_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("diseases.id"), index=True
    )
    extracted_case_count: Mapped[Optional[int]] = mapped_column(Integer)
    confidence: Mapped[Optional[float]] = mapped_column(Float)           # 0.0–1.0 NLP confidence
    extraction_notes: Mapped[Optional[str]] = mapped_column(Text)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    article: Mapped["NewsArticle"] = relationship(back_populates="signals")
    county: Mapped[Optional["County"]] = relationship()
    disease: Mapped[Optional["Disease"]] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ArticleSignal id={self.id} article_id={self.article_id} "
            f"disease_id={self.disease_id} county={self.county_fips}>"
        )


# ---------------------------------------------------------------------------
# OutbreakAlert
# ---------------------------------------------------------------------------

class OutbreakAlert(Base):
    """Alert generated when a county/disease metric breaches a configured threshold."""

    __tablename__ = "outbreak_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    county_fips: Mapped[str] = mapped_column(
        String(5), ForeignKey("counties.fips_code"), nullable=False, index=True
    )
    disease_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("diseases.id"), nullable=False, index=True
    )
    alert_date: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)    # "watch", "warning", "emergency"
    metric: Mapped[str] = mapped_column(String(64), nullable=False)      # e.g. "case_spike", "below_herd_threshold"
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    observed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    county: Mapped["County"] = relationship(back_populates="alerts")
    disease: Mapped["Disease"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:
        return (
            f"<OutbreakAlert id={self.id} severity={self.severity!r} "
            f"county={self.county_fips} disease_id={self.disease_id} date={self.alert_date}>"
        )
