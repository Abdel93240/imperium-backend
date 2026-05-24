# 22 - Backup Execution Layer

## Purpose

Provide an executable backup and restore-drill layer for:

```text
imperium_core
```

This is not documentation-only.
The scripts are VPS-ready and live in:

```text
ops/backup/imperium_core_backup.sh
ops/backup/imperium_core_restore_drill.sh
ops/systemd/imperium-core-backup.service
ops/systemd/imperium-core-backup.timer
```

## Safety Rules

- Back up `imperium_core` only.
- Never target `n8n_db`.
- Store backups outside the app directory.
- Encrypt every backup.
- Do restore drills into a sandbox database only.
- Do not print database passwords or encryption passphrases.

## VPS Packages

Install required tools:

```bash
apt-get update
apt-get install -y postgresql-client gnupg coreutils
```

## Install Scripts

From the uploaded project directory on the VPS:

```bash
install -o root -g root -m 0750 ops/backup/imperium_core_backup.sh /usr/local/sbin/imperium_core_backup.sh
install -o root -g root -m 0750 ops/backup/imperium_core_restore_drill.sh /usr/local/sbin/imperium_core_restore_drill.sh
install -o root -g root -m 0644 ops/systemd/imperium-core-backup.service /etc/systemd/system/imperium-core-backup.service
install -o root -g root -m 0644 ops/systemd/imperium-core-backup.timer /etc/systemd/system/imperium-core-backup.timer
```

Create secure directories:

```bash
mkdir -p /etc/imperium
mkdir -p /var/backups/imperium/postgres
chmod 700 /etc/imperium
chmod 700 /var/backups/imperium
chmod 700 /var/backups/imperium/postgres
```

## Create Secret Files

Database password file:

```bash
cat > /etc/imperium/imperium-db-backup.pass <<'EOF'
REPLACE_WITH_IMPERIUM_RUNTIME_OR_BACKUP_DB_PASSWORD
EOF
chmod 600 /etc/imperium/imperium-db-backup.pass
```

Admin password file for restore drills:

```bash
cat > /etc/imperium/imperium-db-admin.pass <<'EOF'
REPLACE_WITH_IMPERIUM_ADMIN_DB_PASSWORD
EOF
chmod 600 /etc/imperium/imperium-db-admin.pass
```

Backup encryption passphrase file:

```bash
cat > /etc/imperium/imperium-backup-gpg.pass <<'EOF'
REPLACE_WITH_LONG_BACKUP_ENCRYPTION_PASSPHRASE
EOF
chmod 600 /etc/imperium/imperium-backup-gpg.pass
```

Do not store either file in the repository.

## Create Backup Config

```bash
cat > /etc/imperium/imperium-backup.env <<'EOF'
IMPERIUM_DB_HOST=31.97.52.42
IMPERIUM_DB_PORT=5432
IMPERIUM_DB_NAME=imperium_core
IMPERIUM_BACKUP_USER=imperium_user
IMPERIUM_BACKUP_PASSWORD_FILE=/etc/imperium/imperium-db-backup.pass
IMPERIUM_ADMIN_USER=imperium_admin
IMPERIUM_ADMIN_PASSWORD_FILE=/etc/imperium/imperium-db-admin.pass
IMPERIUM_RESTORE_USER=imperium_user
IMPERIUM_RESTORE_PASSWORD_FILE=/etc/imperium/imperium-db-backup.pass
IMPERIUM_RESTORE_DB=imperium_restore_drill
IMPERIUM_BACKUP_DIR=/var/backups/imperium/postgres
IMPERIUM_BACKUP_RETENTION_DAYS=14
IMPERIUM_BACKUP_GPG_PASSPHRASE_FILE=/etc/imperium/imperium-backup-gpg.pass

# Optional future off-host hook.
# Example later:
# IMPERIUM_OFFHOST_SYNC_COMMAND='rsync -a "$IMPERIUM_LATEST_BACKUP" "$IMPERIUM_LATEST_BACKUP_SHA256" backup-user@backup-host:/secure/imperium/'
IMPERIUM_OFFHOST_SYNC_COMMAND=
EOF
chmod 600 /etc/imperium/imperium-backup.env
```

`imperium_admin` is required for restore drills because the drill database must create extensions:

```text
vector
pgcrypto
```

`imperium_user` may remain the backup/runtime role.
Do not use `n8n_db`.

## Exact Backup Command

Manual backup:

```bash
IMPERIUM_BACKUP_CONFIG=/etc/imperium/imperium-backup.env /usr/local/sbin/imperium_core_backup.sh
```

Expected output:

```text
Backup created: /var/backups/imperium/postgres/imperium_core_YYYYMMDDTHHMMSSZ.dump.gpg
Checksum: /var/backups/imperium/postgres/imperium_core_YYYYMMDDTHHMMSSZ.dump.gpg.sha256
```

Backup format:

```text
pg_dump custom format, compressed, encrypted with GPG AES256
```

## Exact Restore Drill Command

Restore the latest backup into a sandbox database:

```bash
IMPERIUM_BACKUP_CONFIG=/etc/imperium/imperium-backup.env /usr/local/sbin/imperium_core_restore_drill.sh
```

Restore a specific backup:

```bash
IMPERIUM_BACKUP_CONFIG=/etc/imperium/imperium-backup.env /usr/local/sbin/imperium_core_restore_drill.sh /var/backups/imperium/postgres/imperium_core_YYYYMMDDTHHMMSSZ.dump.gpg
```

The script drops and recreates a sandbox database named:

```text
imperium_restore_drill
```

Flow:

1. Drop/create `imperium_restore_drill` using `IMPERIUM_ADMIN_USER`.
2. Create extensions `vector` and `pgcrypto` using `IMPERIUM_ADMIN_USER`.
3. Filter extension creation entries out of the `pg_restore` list.
4. Restore the dump into `imperium_restore_drill` using `IMPERIUM_RESTORE_USER`.
5. Verify the restored data.
6. Drop `imperium_restore_drill` unless `KEEP_DRILL_DB=true`.

It verifies:

- current database name
- canonical user count
- events count
- auth events count
- Alembic version

By default, the sandbox database is dropped after the drill.

To keep the sandbox database for manual inspection:

```bash
KEEP_DRILL_DB=true IMPERIUM_BACKUP_CONFIG=/etc/imperium/imperium-backup.env /usr/local/sbin/imperium_core_restore_drill.sh
```

Drop it manually afterward:

```bash
PGPASSWORD="$(cat /etc/imperium/imperium-db-admin.pass)" dropdb --if-exists --host=31.97.52.42 --username=imperium_admin imperium_restore_drill
```

## Enable Daily systemd Timer

```bash
systemctl daemon-reload
systemctl enable --now imperium-core-backup.timer
systemctl list-timers --all | grep imperium-core-backup
```

Run immediately:

```bash
systemctl start imperium-core-backup.service
```

Check logs:

```bash
journalctl -u imperium-core-backup.service -n 100 --no-pager
```

## Retention Cleanup

The backup script deletes encrypted backup files and checksum files older than:

```text
IMPERIUM_BACKUP_RETENTION_DAYS
```

Default:

```text
14 days
```

## Off-Host Strategy

No paid cloud storage is required for V1.

The backup script supports a future off-host command:

```bash
IMPERIUM_OFFHOST_SYNC_COMMAND='rsync -a "$IMPERIUM_LATEST_BACKUP" "$IMPERIUM_LATEST_BACKUP_SHA256" backup-user@backup-host:/secure/imperium/'
```

When set, the script exports:

```text
IMPERIUM_LATEST_BACKUP
IMPERIUM_LATEST_BACKUP_SHA256
```

and runs the sync command after encryption/checksum succeeds.

Recommended future options:

- rsync to a second VPS
- encrypted external disk
- S3-compatible storage with client-side encryption
- Borg/restic repository

## Verification Checklist

```bash
ls -lh /var/backups/imperium/postgres
gpg --batch --yes --decrypt --passphrase-file /etc/imperium/imperium-backup-gpg.pass --output /tmp/imperium_restore_check.dump /var/backups/imperium/postgres/imperium_core_*.dump.gpg
rm -f /tmp/imperium_restore_check.dump
```

Preferred verification:

```bash
IMPERIUM_BACKUP_CONFIG=/etc/imperium/imperium-backup.env /usr/local/sbin/imperium_core_restore_drill.sh
```

## Failure Cases

### Wrong Database

If `IMPERIUM_DB_NAME` is not `imperium_core`, the backup script refuses to run.

### Missing Encryption Passphrase

If `/etc/imperium/imperium-backup-gpg.pass` is missing, the backup script refuses to run.

### Missing DB Password

If `/etc/imperium/imperium-db-backup.pass` is missing, the backup and restore drill refuse to run.

### Restore Role Cannot Create Database

If restore drill fails at `createdb` or extension creation, verify:

```text
IMPERIUM_ADMIN_USER
IMPERIUM_ADMIN_PASSWORD_FILE
```

Do not restore into `imperium_core` directly during a drill.
