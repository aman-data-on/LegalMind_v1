"""AB-12 — departments, archive semantics, and the role/permission rename

Revision ID: b7c3d9e1f2a4
Revises: a3d5f9c17b46
Create Date: 2026-09-05

The owner's 2026-09-05 RBAC redesign (lock record AB-12 in `all_lock.md`).
Four things, each traceable to a term of that record:

1. **`departments` + `users.department_id`** (r3). The boundary a Department
   Lead's oversight is scoped to. Nullable: nobody is placed in a department by
   this migration, because inventing the department's name would be inventing
   data. Until an administrator creates one and assigns people, every account —
   Lead included — sees exactly its own deals, which is the safe direction.

2. **`contracts.deleted_at` → `archived_at`** (r6). The same column AM-37 added,
   renamed to say what it now means: an archived contract is hidden from the
   working lists and read-only, and NOTHING about it is destroyed. The 4 rows
   the development instance already carries keep their timestamps — a contract
   soft-deleted under AM-37 is simply an archived contract now.

3. **Role codes** (r1, r2). `LEGAL_ADMIN` becomes `DEPARTMENT_LEAD` and
   `SUPER_ADMIN` becomes `PLATFORM_ADMIN` — the same rows, so every existing
   assignment survives; only `code`/`name` change. `USER` is displayed as
   "Department User". `LEGAL_REVIEWER` and `LEGAL_DECISION_AUTHORITY` are kept
   as retained-for-future roles (r10) and untouched here.

4. **Permissions** (r4–r7, r12). `contract.delete` is renamed `contract.archive`
   (r6, same row). `department.view` (r3) and `contract.transfer` (r5) are
   added. Then the grants are reconciled to the code's `DEFAULT_ROLE_GRANTS`:
   missing defaults are added for every role, and three grants are REMOVED —
   `legal.review` from the Lead (it is GLOBAL legal scope, the thing r3
   forbids) and `legal.decision` / `legal.approve_customization` from
   DEVELOPER (r12: a debugging role holds no legal authority).

Only the grants the record names are removed; nothing an administrator added
beyond the defaults is touched. On a fresh database this migration runs before
`security.seed.bootstrap`, finds no roles, and the grant section is a no-op —
the seed then creates everything from the same `DEFAULT_ROLE_GRANTS`.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from legalmind.security import permissions as P

revision = 'b7c3d9e1f2a4'
down_revision = 'a3d5f9c17b46'
branch_labels = None
depends_on = None


_ROLE_RENAMES = (
    # (old code, new code, new display name)
    ("LEGAL_ADMIN", P.ROLE_DEPARTMENT_LEAD, P.ROLE_NAMES[P.ROLE_DEPARTMENT_LEAD]),
    ("SUPER_ADMIN", P.ROLE_PLATFORM_ADMIN, P.ROLE_NAMES[P.ROLE_PLATFORM_ADMIN]),
)
_REMOVED_GRANTS = (
    (P.ROLE_DEPARTMENT_LEAD, P.LEGAL_REVIEW),
    (P.ROLE_DEVELOPER, P.LEGAL_DECISION),
    (P.ROLE_DEVELOPER, P.LEGAL_APPROVE_CUSTOMIZATION),
)


def _grant(role_code: str, permission: str) -> None:
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
         WHERE r.code = :role AND p.name = :perm
           AND NOT EXISTS (SELECT 1 FROM role_permissions rp
                            WHERE rp.role_id = r.id AND rp.permission_id = p.id)
    """).bindparams(role=role_code, perm=permission))


def _revoke(role_code: str, permission: str) -> None:
    op.execute(sa.text("""
        DELETE FROM role_permissions rp
         USING roles r, permissions p
         WHERE rp.role_id = r.id AND rp.permission_id = p.id
           AND r.code = :role AND p.name = :perm
    """).bindparams(role=role_code, perm=permission))


def upgrade() -> None:
    # 1. The department boundary.
    op.create_table(
        'departments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_departments')),
        sa.UniqueConstraint('code', name=op.f('uq_departments_code')),
    )
    op.add_column('users', sa.Column('department_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_users_department_id'), 'users', 'departments',
                          ['department_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_users_department_id', 'users', ['department_id'])

    # 2. Archive, not delete.
    op.drop_index('ix_contracts_deleted_at', table_name='contracts')
    op.alter_column('contracts', 'deleted_at', new_column_name='archived_at')
    op.create_index('ix_contracts_archived_at', 'contracts', ['archived_at'],
                    postgresql_where=sa.text('archived_at IS NULL'))

    # 3. Role codes say what the person does.
    for old, new, name in _ROLE_RENAMES:
        op.execute(sa.text("UPDATE roles SET code = :new, name = :name WHERE code = :old")
                   .bindparams(old=old, new=new, name=name))
    op.execute(sa.text("UPDATE roles SET name = :name WHERE code = :code")
               .bindparams(code=P.ROLE_USER, name=P.ROLE_NAMES[P.ROLE_USER]))

    # 4. Permissions and grants.
    op.execute(sa.text("UPDATE permissions SET name = :new WHERE name = :old")
               .bindparams(old="contract.delete", new=P.CONTRACT_ARCHIVE))
    for group, names in P.CATALOGUE.items():
        for name in names:
            op.execute(sa.text("""
                INSERT INTO permissions (id, name, permission_group, created_at)
                VALUES (gen_random_uuid(), :name, :grp, now())
                ON CONFLICT (name) DO NOTHING
            """).bindparams(name=name, grp=group))
    for role_code, grants in P.DEFAULT_ROLE_GRANTS.items():
        for permission in grants:
            _grant(role_code, permission)
    for role_code, permission in _REMOVED_GRANTS:
        _revoke(role_code, permission)


def downgrade() -> None:
    for role_code, permission in _REMOVED_GRANTS:
        _grant(role_code, permission)
    op.execute(sa.text("DELETE FROM permissions WHERE name IN (:a, :b)")
               .bindparams(a=P.DEPARTMENT_VIEW, b=P.CONTRACT_TRANSFER))
    op.execute(sa.text("UPDATE permissions SET name = :old WHERE name = :new")
               .bindparams(old="contract.delete", new=P.CONTRACT_ARCHIVE))
    for old, new, _ in _ROLE_RENAMES:
        op.execute(sa.text("UPDATE roles SET code = :old WHERE code = :new")
                   .bindparams(old=old, new=new))

    op.drop_index('ix_contracts_archived_at', table_name='contracts')
    op.alter_column('contracts', 'archived_at', new_column_name='deleted_at')
    op.create_index('ix_contracts_deleted_at', 'contracts', ['deleted_at'],
                    postgresql_where=sa.text('deleted_at IS NULL'))

    op.drop_index('ix_users_department_id', table_name='users')
    op.drop_constraint(op.f('fk_users_department_id'), 'users', type_='foreignkey')
    op.drop_column('users', 'department_id')
    op.drop_table('departments')
