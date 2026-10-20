-- Droits du compte d'exécution de l'API (imperium_user) sur imperium_core — doc 21.
-- À relancer en imperium_admin après CHAQUE série de migrations (idempotent, aucun secret ici) :
--   psql "postgresql://imperium_admin@127.0.0.1:5432/imperium_core" -v ON_ERROR_STOP=1 -f ops/postgres/runtime_grants.sql
-- (mot de passe lu dans ~/.pgpass, jamais en clair dans une commande).
--
-- Règle : l'API lit, insère, modifie et supprime ses tables ; les registres en ajout seul ne se
-- modifient ni ne se suppriment (les déclencheurs append-only restent le second verrou) ; jamais de
-- TRUNCATE ; la table de version d'Alembic ne se touche qu'en migration.

GRANT USAGE ON SCHEMA public TO imperium_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO imperium_user;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO imperium_user;
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM imperium_user;

-- Registres en ajout seul.
REVOKE UPDATE, DELETE ON events, auth_events, imperium_events, imperium_vault_transactions,
    pressure_snapshots, parameters FROM imperium_user;
-- Versions du plan : jamais supprimées.
REVOKE DELETE ON plan_versions FROM imperium_user;
-- Version du schéma : migrations seulement.
REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM imperium_user;

-- Tables futures : lecture et insertion par défaut ; relancer ce script après les migrations.
ALTER DEFAULT PRIVILEGES FOR ROLE imperium_admin IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO imperium_user;
ALTER DEFAULT PRIVILEGES FOR ROLE imperium_admin IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO imperium_user;
