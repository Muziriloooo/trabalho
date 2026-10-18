"""verification prototype operational analytics and reports

Revision ID: da64a0b27c33
Revises: 0e0fdb6387b6
Create Date: 2026-10-18 01:14:46.306675

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da64a0b27c33'
down_revision = '0e0fdb6387b6'
branch_labels = None
depends_on = None


def upgrade():
    # Alvos das FKs compostas precisam existir antes das tabelas filhas.
    with op.batch_alter_table('access_credential', schema=None) as batch_op:
        batch_op.create_index('uq_credential_id_org', ['id', 'organization_id'], unique=True)

    with op.batch_alter_table('access_event', schema=None) as batch_op:
        batch_op.create_index('uq_access_event_id_org_site', ['id', 'organization_id', 'site_id'], unique=True)

    op.create_table('organization_branding',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('logo_png', sa.LargeBinary(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_organization_branding_organization_id_organization')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organization_branding')),
    sa.UniqueConstraint('organization_id', name=op.f('uq_organization_branding_organization_id'))
    )
    op.create_table('verification_policy',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('purpose', sa.String(length=500), nullable=False),
    sa.Column('controller', sa.String(length=120), nullable=False),
    sa.Column('legal_review', sa.String(length=500), nullable=False),
    sa.Column('risk_review', sa.String(length=500), nullable=False),
    sa.Column('necessity_review', sa.String(length=500), nullable=False),
    sa.Column('workplace_review', sa.String(length=500), nullable=False),
    sa.Column('alternative', sa.String(length=500), nullable=False),
    sa.Column('retention_days', sa.Integer(), nullable=False),
    sa.Column('model_version', sa.String(length=40), nullable=False),
    sa.Column('threshold', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('retention_days >= 1 AND retention_days <= 30', name=op.f('ck_verification_policy_verification_retention')),
    sa.CheckConstraint('threshold >= 0.5 AND threshold <= 1', name=op.f('ck_verification_policy_verification_threshold')),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_verification_policy_organization_id_organization')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_verification_policy')),
    sa.UniqueConstraint('organization_id', name=op.f('uq_verification_policy_organization_id'))
    )
    op.create_table('report_run',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('identifier', sa.String(length=32), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('generated_by', sa.Integer(), nullable=False),
    sa.Column('organization_name', sa.String(length=120), nullable=False),
    sa.Column('generator_name', sa.String(length=254), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('purpose', sa.String(length=240), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('source', sa.String(length=24), nullable=False),
    sa.Column('site_ids', sa.JSON(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('logo_png', sa.LargeBinary(), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['generated_by'], ['user.id'], name=op.f('fk_report_run_generated_by_user')),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_report_run_organization_id_organization')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_run')),
    sa.UniqueConstraint('identifier', name=op.f('uq_report_run_identifier'))
    )
    with op.batch_alter_table('report_run', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_report_run_organization_id'), ['organization_id'], unique=False)

    op.create_table('verification_enrollment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('policy_version', sa.Integer(), nullable=False),
    sa.Column('model_version', sa.String(length=40), nullable=False),
    sa.Column('ciphertext', sa.LargeBinary(), nullable=True),
    sa.Column('authorization_reference', sa.String(length=240), nullable=False),
    sa.Column('enrolled_by', sa.Integer(), nullable=False),
    sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['enrolled_by'], ['user.id'], name=op.f('fk_verification_enrollment_enrolled_by_user')),
    sa.ForeignKeyConstraint(['subject_id', 'organization_id'], ['access_subject.id', 'access_subject.organization_id'], name=op.f('fk_verification_enrollment_subject_id_access_subject')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_verification_enrollment')),
    sa.UniqueConstraint('subject_id', name=op.f('uq_verification_enrollment_subject_id'))
    )
    op.create_table('verification_challenge',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('point_id', sa.Integer(), nullable=False),
    sa.Column('credential_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['user.id'], name=op.f('fk_verification_challenge_actor_id_user')),
    sa.ForeignKeyConstraint(['credential_id', 'organization_id'], ['access_credential.id', 'access_credential.organization_id'], name=op.f('fk_verification_challenge_credential_id_access_credential')),
    sa.ForeignKeyConstraint(['point_id', 'organization_id'], ['access_point.id', 'access_point.organization_id'], name=op.f('fk_verification_challenge_point_id_access_point')),
    sa.ForeignKeyConstraint(['site_id', 'organization_id'], ['site.id', 'site.organization_id'], name=op.f('fk_verification_challenge_site_id_site')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_verification_challenge'))
    )
    op.create_table('verification_record',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=False),
    sa.Column('access_event_id', sa.Integer(), nullable=False),
    sa.Column('credential_id', sa.Integer(), nullable=True),
    sa.Column('outcome', sa.String(length=32), nullable=False),
    sa.Column('model_version', sa.String(length=40), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['access_event_id', 'organization_id', 'site_id'], ['access_event.id', 'access_event.organization_id', 'access_event.site_id'], name=op.f('fk_verification_record_access_event_id_access_event')),
    sa.ForeignKeyConstraint(['credential_id', 'organization_id'], ['access_credential.id', 'access_credential.organization_id'], name=op.f('fk_verification_record_credential_id_access_credential')),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_verification_record_organization_id_organization')),
    sa.ForeignKeyConstraint(['site_id', 'organization_id'], ['site.id', 'site.organization_id'], name=op.f('fk_verification_record_site_id_site')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_verification_record')),
    sa.UniqueConstraint('access_event_id', name=op.f('uq_verification_record_access_event_id'))
    )
    with op.batch_alter_table('verification_record', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_verification_record_organization_id'), ['organization_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('verification_record', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_verification_record_organization_id'))

    op.drop_table('verification_record')
    op.drop_table('verification_challenge')
    op.drop_table('verification_enrollment')
    with op.batch_alter_table('report_run', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_report_run_organization_id'))

    op.drop_table('report_run')
    op.drop_table('verification_policy')
    op.drop_table('organization_branding')
    with op.batch_alter_table('access_event', schema=None) as batch_op:
        batch_op.drop_index('uq_access_event_id_org_site')

    with op.batch_alter_table('access_credential', schema=None) as batch_op:
        batch_op.drop_index('uq_credential_id_org')

    # ### end Alembic commands ###
