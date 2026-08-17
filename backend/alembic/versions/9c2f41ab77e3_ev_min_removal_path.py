"""EV-MIN on the removal path

Closes `F-1`. Locked **AB-1.6 / D-3.4** requires every Finding to have at least one
Evaluation, and engineering resolution `F-5` chose a database trigger over a service
invariant precisely because "a migration or backfill can bypass service code".

The original trigger fires `AFTER INSERT ON findings` only, so it enforces the
invariant when a Finding is created and never again. Deleting the last Evaluation of
an existing Finding — or moving it to a different Finding — leaves the Finding
orphaned, and nothing notices. That is the exact bypass `F-5` intended to make
impossible.

Two things make an orphaned Finding worse than an ordinary data-integrity fault:

* `legal_decisions.evaluation_id` is NOT NULL (AM-1), so a Finding with no
  Evaluation is a Finding that can never be decided — it would stall Step 30 r7
  resolution permanently.
* the Finding's `classification` is a derived summary of its Evaluations (D-1.1).
  With none, the summary is a legal statement with nothing behind it, which is
  precisely what locked 49.7 r1 exists to prevent.

Revision ID: 9c2f41ab77e3
Revises: 721650d19741
"""

from alembic import op

revision = "9c2f41ab77e3"
down_revision = "721650d19741"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One function serves DELETE and UPDATE. `OLD.finding_id` is the Finding being
    # vacated in both cases.
    op.execute("""
        CREATE OR REPLACE FUNCTION legalmind_check_ev_min_vacated()
        RETURNS trigger AS $$
        BEGIN
            -- An UPDATE that does not move the Evaluation vacates nothing.
            IF TG_OP = 'UPDATE'
               AND OLD.finding_id IS NOT DISTINCT FROM NEW.finding_id THEN
                RETURN NULL;
            END IF;

            -- The Finding itself may have been deleted in the same transaction.
            -- EV-MIN says nothing about a Finding that no longer exists, and the
            -- check is DEFERRED so by COMMIT the row is genuinely gone.
            IF NOT EXISTS (SELECT 1 FROM findings WHERE id = OLD.finding_id) THEN
                RETURN NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM evaluations WHERE finding_id = OLD.finding_id
            ) THEN
                RAISE EXCEPTION
                    'EV-MIN violated: finding % would be left with no evaluation',
                    OLD.finding_id
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # DEFERRABLE INITIALLY DEFERRED, matching the INSERT-side trigger: a
    # transaction may legitimately delete an Evaluation and add a replacement in
    # either order, and only the state at COMMIT is the invariant.
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_evaluations_ev_min_delete
        AFTER DELETE ON evaluations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION legalmind_check_ev_min_vacated();
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_evaluations_ev_min_reparent
        AFTER UPDATE ON evaluations
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION legalmind_check_ev_min_vacated();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evaluations_ev_min_reparent ON evaluations")
    op.execute("DROP TRIGGER IF EXISTS trg_evaluations_ev_min_delete ON evaluations")
    op.execute("DROP FUNCTION IF EXISTS legalmind_check_ev_min_vacated()")
