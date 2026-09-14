-- 55.2 — "The application role holds no DDL rights; migrations run under a
-- separate role." Not cosmetic: the point is that the runtime role cannot ALTER
-- or DROP the legal record, which requires moving OWNERSHIP, not just revoking
-- CREATE on the schema. An owner keeps full rights over what it owns.
--
-- After this: legalmind_migrate owns the objects and runs Alembic; legalmind
-- holds DML only and cannot change a single table definition.

CREATE ROLE legalmind_migrate NOLOGIN;

-- Ownership moves. This is what actually removes DDL power from the runtime role.
REASSIGN OWNED BY legalmind TO legalmind_migrate;

-- The runtime role now needs explicit rights, since it is no longer the owner.
GRANT USAGE ON SCHEMA public TO legalmind;
GRANT USAGE ON SCHEMA assist TO legalmind;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO legalmind;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA assist TO legalmind;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO legalmind;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assist TO legalmind;

-- And loses DDL.
REVOKE CREATE ON SCHEMA public FROM legalmind;
REVOKE CREATE ON SCHEMA assist FROM legalmind;

-- A future migration creates tables as legalmind_migrate; the runtime role must
-- get DML on them automatically or the next deploy breaks at runtime, not at
-- migration time, which is the worse place to find out.
ALTER DEFAULT PRIVILEGES FOR ROLE legalmind_migrate IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO legalmind;
ALTER DEFAULT PRIVILEGES FOR ROLE legalmind_migrate IN SCHEMA assist
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO legalmind;
ALTER DEFAULT PRIVILEGES FOR ROLE legalmind_migrate IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO legalmind;
ALTER DEFAULT PRIVILEGES FOR ROLE legalmind_migrate IN SCHEMA assist
  GRANT USAGE, SELECT ON SEQUENCES TO legalmind;

-- The assist grant boundary (AM-25 r2) must survive the ownership move.
GRANT USAGE ON SCHEMA assist TO legalmind_assist;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO legalmind_assist;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA assist TO legalmind_assist;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA assist TO legalmind_assist;
ALTER DEFAULT PRIVILEGES FOR ROLE legalmind_migrate IN SCHEMA assist
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO legalmind_assist;
ALTER DEFAULT PRIVILEGES FOR ROLE legalmind_migrate IN SCHEMA public
  GRANT SELECT ON TABLES TO legalmind_assist;
