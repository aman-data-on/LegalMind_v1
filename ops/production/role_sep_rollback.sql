-- Rollback for role_sep.sql. Returns ownership and DDL to the runtime role.
REASSIGN OWNED BY legalmind_migrate TO legalmind;
GRANT CREATE ON SCHEMA public TO legalmind;
GRANT CREATE ON SCHEMA assist TO legalmind;
DROP OWNED BY legalmind_migrate;
DROP ROLE legalmind_migrate;
