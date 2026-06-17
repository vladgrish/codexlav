#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

: "${GCP_PROJECT:?set GCP_PROJECT}"
: "${GCP_REGION:=us-central1}"
: "${GCP_ZONE:=us-central1-a}"
: "${GCS_ARTIFACT_BUCKET:?set GCS_ARTIFACT_BUCKET}"
: "${GCS_SIGNING_SERVICE_ACCOUNT:?set GCS_SIGNING_SERVICE_ACCOUNT}"
: "${GCS_ARTIFACT_RETENTION_DAYS:=7}"

gcloud config set project "$GCP_PROJECT"
gcloud config set compute/region "$GCP_REGION"
gcloud config set compute/zone "$GCP_ZONE"

gcloud services enable \
  compute.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  storage.googleapis.com

if ! gcloud storage buckets describe "gs://$GCS_ARTIFACT_BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$GCS_ARTIFACT_BUCKET" --location="$GCP_REGION" --uniform-bucket-level-access
fi

gcloud storage buckets update "gs://$GCS_ARTIFACT_BUCKET" --uniform-bucket-level-access

LIFECYCLE_FILE="$(mktemp)"
cat >"$LIFECYCLE_FILE" <<JSON
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": $GCS_ARTIFACT_RETENTION_DAYS}
    }
  ]
}
JSON
gcloud storage buckets update "gs://$GCS_ARTIFACT_BUCKET" --lifecycle-file="$LIFECYCLE_FILE"
rm -f "$LIFECYCLE_FILE"

gcloud storage buckets add-iam-policy-binding "gs://$GCS_ARTIFACT_BUCKET" \
  --member="serviceAccount:$GCS_SIGNING_SERVICE_ACCOUNT" \
  --role="roles/storage.objectAdmin"

gcloud iam service-accounts add-iam-policy-binding "$GCS_SIGNING_SERVICE_ACCOUNT" \
  --member="serviceAccount:$GCS_SIGNING_SERVICE_ACCOUNT" \
  --role="roles/iam.serviceAccountTokenCreator" || true

echo "gcp bootstrap done"
