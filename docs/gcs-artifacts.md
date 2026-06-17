# GCS Artifacts

Codexlav sends small artifacts directly to Telegram. Larger files are uploaded to Google Cloud Storage and returned as signed URLs.

## Flow

1. Bot detects an artifact path in Codex output.
2. If the file is larger than `TELEGRAM_ARTIFACT_MAX_BYTES`, bot uploads it to GCS.
3. Bot creates a signed PUT URL with `gcloud storage sign-url`.
4. Bot uploads the file with `curl`.
5. Bot creates a signed GET URL and sends it to Telegram.

## Required Environment

- `GCS_ARTIFACT_BUCKET`
- `GCS_ARTIFACT_PREFIX`
- `GCS_ARTIFACT_RETENTION_DAYS`
- `GCS_SIGNED_URL_DURATION`
- `GCS_SIGNING_SERVICE_ACCOUNT`

## Bucket Setup

[`scripts/bootstrap_gcp.sh`](../scripts/bootstrap_gcp.sh) configures:

- required Google APIs
- artifact bucket creation
- uniform bucket-level access
- lifecycle deletion after `GCS_ARTIFACT_RETENTION_DAYS`
- `roles/storage.objectAdmin` on the bucket for `GCS_SIGNING_SERVICE_ACCOUNT`
- best-effort `roles/iam.serviceAccountTokenCreator` self-binding for signing

## Signing Permissions

`gcloud storage sign-url --impersonate-service-account` needs `iam.serviceAccounts.signBlob`.

If signing fails, grant token creator on the signing service account to the principal running the bot:

```bash
gcloud iam service-accounts add-iam-policy-binding "$GCS_SIGNING_SERVICE_ACCOUNT" \
  --member="serviceAccount:$GCS_SIGNING_SERVICE_ACCOUNT" \
  --role="roles/iam.serviceAccountTokenCreator"
```

For a different VM service account, use that account in the `--member` value.

## Retention

Default retention is lifecycle deletion after 7 days:

```env
GCS_ARTIFACT_RETENTION_DAYS=7
```

This is not a bucket retention lock. It is a cleanup policy so generated artifacts do not live forever.
