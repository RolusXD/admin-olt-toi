"""backfill master catalogs

Revision ID: 0020_backfill_masters
Revises: 0019_master_catalogs
Create Date: 2026-06-17
"""

from alembic import op


revision = "0020_backfill_masters"
down_revision = "0019_master_catalogs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        insert into speed_profiles
            (olt_id, olt_code_snapshot, name, profile_code, upstream_profile_name, downstream_profile_name,
             upstream_kbps, downstream_kbps, technology, source, is_active)
        select
            up.olt_id,
            olts.olt_code,
            regexp_replace(up.name, '([-_]?UP)$', '', 'i') as name,
            upper(regexp_replace(up.name, '([-_]?UP)$', '', 'i')) as profile_code,
            up.name,
            down.name,
            up.upstream_rate,
            down.downstream_rate,
            'GPON',
            'imported',
            true
        from (
            select *, row_number() over (partition by olt_id order by name) as rn
            from gpon_profiles
            where profile_type = 'tcont'
        ) up
        join (
            select *, row_number() over (partition by olt_id order by name) as rn
            from gpon_profiles
            where profile_type = 'traffic'
        ) down on down.olt_id = up.olt_id and down.rn = up.rn
        join olts on olts.id = up.olt_id
        on conflict (olt_id, profile_code) do nothing
        """
    )
    op.execute(
        """
        insert into nap_ports (nap_id, port_number, label, status)
        select naps.id, generated.port_number, 'Puerto ' || generated.port_number, 'free'
        from naps
        cross join lateral generate_series(1, coalesce(nullif(naps.capacity, 0), 16)) as generated(port_number)
        on conflict (nap_id, port_number) do nothing
        """
    )
    op.execute(
        """
        update nap_ports
        set status = 'occupied',
            onu_id = onus.id,
            customer_name_snapshot = onus.customer_name
        from onus
        where nap_ports.nap_id = onus.nap_id
          and nap_ports.port_number = onus.nap_port
          and onus.nap_id is not null
          and onus.nap_port is not null
        """
    )


def downgrade() -> None:
    pass
