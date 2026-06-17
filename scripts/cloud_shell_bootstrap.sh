#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT:?set GCP_PROJECT to an existing project id}"
: "${GCP_ZONE:=us-central1-a}"
: "${GCP_REGION:=us-central1}"
: "${VM_NAME:=codexlav-vm}"
: "${VM_MACHINE_TYPE:=e2-micro}"
: "${VM_IMAGE_FAMILY:=debian-12}"
: "${VM_IMAGE_PROJECT:=debian-cloud}"

gcloud config set project "$GCP_PROJECT"
gcloud config set compute/region "$GCP_REGION"
gcloud config set compute/zone "$GCP_ZONE"

gcloud services enable \
  compute.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  storage.googleapis.com

if ! gcloud compute instances describe "$VM_NAME" --zone="$GCP_ZONE" >/dev/null 2>&1; then
  gcloud compute instances create "$VM_NAME" \
    --zone="$GCP_ZONE" \
    --machine-type="$VM_MACHINE_TYPE" \
    --image-family="$VM_IMAGE_FAMILY" \
    --image-project="$VM_IMAGE_PROJECT" \
    --scopes=cloud-platform \
    --tags=codexlav
fi

gcloud compute instances describe "$VM_NAME" \
  --zone="$GCP_ZONE" \
  --format='table(name,zone.basename(),machineType.basename(),networkInterfaces[0].accessConfigs[0].natIP,serviceAccounts[0].email)'

echo "next:"
echo "gcloud compute ssh $VM_NAME --zone=$GCP_ZONE"
