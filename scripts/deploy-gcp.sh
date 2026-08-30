#!/usr/bin/env bash
set -euo pipefail

required_vars=(
  FOURPROOF_PROJECT_ID
  FOURPROOF_REGION
  FOURPROOF_SERVICE_NAME
  FOURPROOF_RUNTIME_SA
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 2
  fi
done

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
if [[ -z "${active_account}" ]]; then
  echo "No active gcloud account. The applicant must authenticate and choose the account." >&2
  exit 3
fi

project_id="${FOURPROOF_PROJECT_ID}"
region="${FOURPROOF_REGION}"
service_name="${FOURPROOF_SERVICE_NAME}"
runtime_sa_name="${FOURPROOF_RUNTIME_SA}"
runtime_sa_email="${runtime_sa_name}@${project_id}.iam.gserviceaccount.com"
topic_name="${FOURPROOF_PUBSUB_TOPIC:-fourproof-missions}"
subscription_name="${FOURPROOF_PUBSUB_SUBSCRIPTION:-fourproof-missions-push}"
firestore_location="${FOURPROOF_FIRESTORE_LOCATION:-${region}}"

echo "Active account: ${active_account}"
echo "Project: ${project_id}"
echo "Region: ${region}"
echo "Service: ${service_name}"
echo "This operation creates or changes billable Google Cloud resources and IAM bindings."
echo "Continue only after the applicant has reviewed the account, project, billing, and cost boundary."

gcloud config set project "${project_id}"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com

if ! gcloud iam service-accounts describe "${runtime_sa_email}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${runtime_sa_name}" \
    --display-name="FourProof Fleet runtime"
fi

project_number="$(gcloud projects describe "${project_id}" --format='value(projectNumber)')"
pubsub_service_agent="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding "${runtime_sa_email}" \
  --member="serviceAccount:${pubsub_service_agent}" \
  --role="roles/iam.serviceAccountTokenCreator"

for role_name in \
  roles/datastore.user \
  roles/pubsub.publisher \
  roles/aiplatform.user \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${project_id}" \
    --member="serviceAccount:${runtime_sa_email}" \
    --role="${role_name}" \
    --condition=None
done

if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  gcloud firestore databases create \
    --database='(default)' \
    --location="${firestore_location}" \
    --type=firestore-native
fi

if ! gcloud pubsub topics describe "${topic_name}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${topic_name}"
fi

gcloud run deploy "${service_name}" \
  --source=. \
  --region="${region}" \
  --service-account="${runtime_sa_email}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=2 \
  --cpu=1 \
  --memory=1Gi \
  --timeout=300 \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${project_id},GOOGLE_CLOUD_LOCATION=global,FIRESTORE_ENABLED=1,FIRESTORE_COLLECTION=fourproof_missions,PUBSUB_TOPIC=${topic_name},PUBSUB_SERVICE_ACCOUNT_EMAIL=${runtime_sa_email}"

service_url="$(gcloud run services describe "${service_name}" --region="${region}" --format='value(status.url)')"
service_host="${service_url#https://}"

gcloud run services update "${service_name}" \
  --region="${region}" \
  --update-env-vars="PUBSUB_AUDIENCE=${service_url},ALLOWED_LIVE_HOSTS=${service_host},MISSION_LIMIT_PER_HOUR=20"

push_endpoint="${service_url}/api/internal/pubsub"
if gcloud pubsub subscriptions describe "${subscription_name}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "${subscription_name}" \
    --push-endpoint="${push_endpoint}" \
    --push-auth-service-account="${runtime_sa_email}" \
    --push-auth-token-audience="${service_url}" \
    --ack-deadline=600 \
    --min-retry-delay=10s \
    --max-retry-delay=60s
else
  gcloud pubsub subscriptions create "${subscription_name}" \
    --topic="${topic_name}" \
    --push-endpoint="${push_endpoint}" \
    --push-auth-service-account="${runtime_sa_email}" \
    --push-auth-token-audience="${service_url}" \
    --ack-deadline=600 \
    --min-retry-delay=10s \
    --max-retry-delay=60s
fi

echo "Deployment requested: ${service_url}"
echo "Do not claim completion until docs/cloud-proof-checklist.md is verified with live evidence."
