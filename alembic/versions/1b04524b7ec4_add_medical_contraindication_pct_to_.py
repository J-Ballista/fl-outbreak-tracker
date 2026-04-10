"""add medical_contraindication_pct to diseases

Revision ID: 1b04524b7ec4
Revises: f291b56634d8
Create Date: 2026-04-09

Adds medical_contraindication_pct to the diseases table and seeds
CDC-based estimates of the population fraction that cannot receive
each vaccine for medical reasons.  The safe religious-exemption
ceiling = (100 - herd_threshold_pct) - medical_contraindication_pct.

Rates by vaccine family (CDC ACIP contraindication guidance):
  Live-attenuated (MMR, Varicella) — 0.40%  (immunocompromised)
  DTaP family (Pertussis, Tetanus, Diphtheria) — 0.25%  (neurological)
  Inactivated (Hep A/B, Meningo, HiB, Polio) — 0.15–0.20%
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1b04524b7ec4'
down_revision: Union[str, Sequence[str], None] = 'f291b56634d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RATES = {
    "Measles":                0.40,
    "Mumps":                  0.40,
    "Rubella":                0.40,
    "Pertussis":              0.25,
    "Varicella":              0.40,
    "Hepatitis A":            0.15,
    "Hepatitis B":            0.15,
    "Meningococcal Disease":  0.20,
    "Haemophilus Influenzae": 0.15,
    "Tetanus":                0.25,
    "Diphtheria":             0.25,
    "Poliomyelitis":          0.15,
}


def upgrade() -> None:
    op.add_column(
        "diseases",
        sa.Column("medical_contraindication_pct", sa.Numeric(5, 2), nullable=True),
    )
    conn = op.get_bind()
    for name, pct in _RATES.items():
        conn.execute(
            sa.text(
                "UPDATE diseases SET medical_contraindication_pct = :pct WHERE name = :name"
            ),
            {"pct": pct, "name": name},
        )


def downgrade() -> None:
    op.drop_column("diseases", "medical_contraindication_pct")
