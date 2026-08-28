# External Supabase Storage backup commands

Phase 6 stores encrypted backup artifacts in the private Supabase Storage bucket `z-platform-backups`. The repository-controlled script `scripts/backup/external-supabase-restore.sh` exports application state, encrypts it with PBKDF2-protected AES-256-CBC, uploads the ciphertext and manifest, restores into the configured isolated staging endpoint, and requires an explicit verification response.

Required protected inputs are `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_BACKUP_BUCKET`, `SUPABASE_BACKUP_PREFIX`, `BACKUP_ENCRYPTION_KEY`, `BACKUP_SOURCE_URL`, `BACKUP_RESTORE_URL`, and `BACKUP_VERIFY_URL`. The bucket must remain private; credentials and keys must not appear in command strings or evidence.
