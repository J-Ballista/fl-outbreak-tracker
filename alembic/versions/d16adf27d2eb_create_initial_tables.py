"""create initial tables

Revision ID: d16adf27d2eb
Revises:
Create Date: 2026-04-06

Creates all seven application tables and promotes disease_cases to a
TimescaleDB hypertable partitioned on report_date.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d16adf27d2eb"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # counties
    # ------------------------------------------------------------------
    op.create_table(
        "counties",
        sa.Column("fips_code", sa.String(5), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("centroid_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("centroid_lng", sa.Numeric(9, 6), nullable=True),
    )

    # ------------------------------------------------------------------
    # diseases
    # ------------------------------------------------------------------
    op.create_table(
        "diseases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("icd10_code", sa.String(16), nullable=True),
        sa.Column("herd_threshold_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("r0_estimate", sa.Numeric(6, 2), nullable=True),
        sa.UniqueConstraint("name", name="uq_diseases_name"),
    )

    # ------------------------------------------------------------------
    # disease_cases  (becomes a TimescaleDB hypertable)
    # TimescaleDB requires the partitioning column (report_date) to be
    # part of every unique index, including the primary key.
    # We use a composite PK (id, report_date) to satisfy this constraint
    # while keeping id as the logical row identifier.
    # ------------------------------------------------------------------
    op.execute("CREATE SEQUENCE disease_cases_id_seq")
    op.create_table(
        "disease_cases",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('disease_cases_id_seq')"),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column(
            "county_fips",
            sa.String(5),
            sa.ForeignKey("counties.fips_code"),
            nullable=False,
        ),
        sa.Column(
            "disease_id",
            sa.Integer(),
            sa.ForeignKey("diseases.id"),
            nullable=False,
        ),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_count", sa.Integer(), nullable=True),
        sa.Column("probable_count", sa.Integer(), nullable=True),
        sa.Column("age_group", sa.String(32), nullable=True),
        sa.Column("acquisition", sa.String(32), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", "report_date", name="pk_disease_cases"),
    )
    op.create_index("ix_disease_cases_county_fips", "disease_cases", ["county_fips"])
    op.create_index("ix_disease_cases_disease_id", "disease_cases", ["disease_id"])

    # Promote to TimescaleDB hypertable partitioned by report_date.
    # if_not_exists makes reruns safe during development.
    op.execute(
        "SELECT create_hypertable('disease_cases', 'report_date', "
        "if_not_exists => TRUE, migrate_data => TRUE);"
    )

    # ------------------------------------------------------------------
    # vaccination_rates
    # ------------------------------------------------------------------
    op.create_table(
        "vaccination_rates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("survey_year", sa.SmallInteger(), nullable=False),
        sa.Column(
            "county_fips",
            sa.String(5),
            sa.ForeignKey("counties.fips_code"),
            nullable=False,
        ),
        sa.Column(
            "disease_id",
            sa.Integer(),
            sa.ForeignKey("diseases.id"),
            nullable=False,
        ),
        sa.Column("facility_type", sa.String(64), nullable=True),
        sa.Column("vaccinated_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("exempt_medical_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("exempt_religious_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_vaccination_rates_county_fips", "vaccination_rates", ["county_fips"]
    )
    op.create_index(
        "ix_vaccination_rates_disease_id", "vaccination_rates", ["disease_id"]
    )

    # ------------------------------------------------------------------
    # news_articles
    # ------------------------------------------------------------------
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("url", name="uq_news_articles_url"),
    )

    # ------------------------------------------------------------------
    # article_signals
    # ------------------------------------------------------------------
    op.create_table(
        "article_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "article_id",
            sa.Integer(),
            sa.ForeignKey("news_articles.id"),
            nullable=False,
        ),
        sa.Column(
            "county_fips",
            sa.String(5),
            sa.ForeignKey("counties.fips_code"),
            nullable=True,
        ),
        sa.Column(
            "disease_id",
            sa.Integer(),
            sa.ForeignKey("diseases.id"),
            nullable=True,
        ),
        sa.Column("extracted_case_count", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("extraction_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_article_signals_article_id", "article_signals", ["article_id"])
    op.create_index("ix_article_signals_county_fips", "article_signals", ["county_fips"])
    op.create_index("ix_article_signals_disease_id", "article_signals", ["disease_id"])

    # ------------------------------------------------------------------
    # outbreak_alerts
    # ------------------------------------------------------------------
    op.create_table(
        "outbreak_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "county_fips",
            sa.String(5),
            sa.ForeignKey("counties.fips_code"),
            nullable=False,
        ),
        sa.Column(
            "disease_id",
            sa.Integer(),
            sa.ForeignKey("diseases.id"),
            nullable=False,
        ),
        sa.Column("alert_date", sa.Date(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("threshold_value", sa.Numeric(10, 4), nullable=True),
        sa.Column("observed_value", sa.Numeric(10, 4), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_outbreak_alerts_county_fips", "outbreak_alerts", ["county_fips"]
    )
    op.create_index(
        "ix_outbreak_alerts_disease_id", "outbreak_alerts", ["disease_id"]
    )


def downgrade() -> None:
    op.drop_table("outbreak_alerts")
    op.drop_table("article_signals")
    op.drop_table("news_articles")
    op.drop_table("vaccination_rates")
    # TimescaleDB hypertable — execute raw DROP to avoid ORM confusion
    op.execute("DROP TABLE IF EXISTS disease_cases CASCADE;")
    op.execute("DROP SEQUENCE IF EXISTS disease_cases_id_seq;")
    op.drop_table("diseases")
    op.drop_table("counties")
