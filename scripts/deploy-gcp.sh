#!/usr/bin/env bash
set -euo pipefail

required_vars=(
  FOURPROOF_PROJECT_ID
  FOURPROOF_REGION
  FOURPROOF_SERVICE_NAME
  FOURPROOF_RUNTIME_SA
  FOURPROOF_HARD_COST_CAP_USD
  FOURPROOF_MAX_LIVE_MISSIONS
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    exit 2
  fi
done

ack_value="I_CONFIRM_USER_AUTHORIZED_BILLABLE_GCP_CHANGES"
if [[ "${FOURPROOF_BILLABLE_ACTION_ACK:-}" != "${ack_value}" ]]; then
  echo "Deployment changes billable GCP resources. Set FOURPROOF_BILLABLE_ACTION_ACK only after action-time user authorization." >&2
  exit 4
fi

export CLOUDSDK_CORE_DISABLE_PROMPTS=1

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
if [[ -z "${active_account}" ]]; then
  echo "No active gcloud account. The applicant must authenticate and choose the account." >&2
  exit 3
fi

project_id="${FOURPROOF_PROJECT_ID}"
region="${FOURPROOF_REGION}"
service_name="${FOURPROOF_SERVICE_NAME}"
runtime_sa_name="${FOURPROOF_RUNTIME_SA}"
hard_cost_cap_usd="${FOURPROOF_HARD_COST_CAP_USD}"
max_live_missions="${FOURPROOF_MAX_LIVE_MISSIONS}"
runtime_sa_email="${runtime_sa_name}@${project_id}.iam.gserviceaccount.com"
topic_name="${FOURPROOF_PUBSUB_TOPIC:-fourproof-missions}"
subscription_name="${FOURPROOF_PUBSUB_SUBSCRIPTION:-fourproof-missions-push}"
firestore_location="${FOURPROOF_FIRESTORE_LOCATION:-${region}}"
git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
git_sha="$(git rev-parse HEAD 2>/dev/null || true)"

if [[ "${git_root}" != "$(pwd -P)" ]] || [[ ! "${git_sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Run this script from the root of the committed FourProof Fleet repository." >&2
  exit 5
fi
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  echo "Refusing to deploy an uncommitted worktree; commit and verify the exact source first." >&2
  exit 6
fi
if [[ ! "${project_id}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]]; then
  echo "Invalid FOURPROOF_PROJECT_ID." >&2
  exit 7
fi
if [[ ! "${region}" =~ ^[a-z0-9-]+$ ]] || [[ ! "${service_name}" =~ ^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
  echo "Invalid region or Cloud Run service name." >&2
  exit 8
fi
if [[ ! "${runtime_sa_name}" =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]]; then
  echo "Invalid runtime service-account name." >&2
  exit 9
fi
if [[ ! "${hard_cost_cap_usd}" =~ ^[1-9][0-9]*([.][0-9]{1,2})?$ ]]; then
  echo "FOURPROOF_HARD_COST_CAP_USD must be the applicant-approved USD ceiling." >&2
  exit 13
fi
hard_cost_whole="${hard_cost_cap_usd%%.*}"
if (( 10#${hard_cost_whole} < 5 )); then
  echo "FOURPROOF_HARD_COST_CAP_USD must be at least 5.00 for the documented conservative deployment envelope." >&2
  exit 15
fi
if [[ "${max_live_missions}" != "8" ]]; then
  echo "FOURPROOF_MAX_LIVE_MISSIONS must be exactly 8 for the documented proof and recording envelope." >&2
  exit 14
fi
for resource_name in "${topic_name}" "${subscription_name}" "${firestore_location}"; do
  if [[ ! "${resource_name}" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "Invalid Pub/Sub or Firestore resource name: ${resource_name}" >&2
    exit 10
  fi
done

project_state="$(gcloud projects describe "${project_id}" --format='value(lifecycleState)' 2>/dev/null || true)"
billing_enabled="$(gcloud billing projects describe "${project_id}" --format='value(billingEnabled)' 2>/dev/null || true)"
if [[ "${project_state}" != "ACTIVE" ]]; then
  echo "Selected project is missing or not ACTIVE; no resources were changed." >&2
  exit 11
fi
if [[ "${billing_enabled}" != "True" && "${billing_enabled}" != "true" ]]; then
  echo "Selected project does not have billing enabled; no resources were changed." >&2
  exit 12
fi

echo "Active account: ${active_account}"
echo "Project: ${project_id}"
echo "Region: ${region}"
echo "Service: ${service_name}"
echo "Git commit: ${git_sha}"
echo "Applicant-authorized cost ceiling: USD ${hard_cost_cap_usd} (authorization limit, not an automatic billing stop)"
echo "Per-revision Gemini mission ceiling: ${max_live_missions}"
echo "Per-mission Gemini ceiling: 8 model calls, 2048 output tokens per call"
echo "This operation creates or changes billable Google Cloud resources and IAM bindings."
echo "Continue only after the applicant has reviewed the account, project, billing, and cost boundary."

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com \
  --project="${project_id}"

# Provision the Pub/Sub service agent before granting it token-creation rights.
gcloud beta services identity create \
  --service=pubsub.googleapis.com \
  --project="${project_id}" \
  >/dev/null

if ! gcloud iam service-accounts describe "${runtime_sa_email}" --project="${project_id}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${runtime_sa_name}" \
    --display-name="FourProof Fleet runtime" \
    --project="${project_id}"
fi

project_number="$(gcloud projects describe "${project_id}" --format='value(projectNumber)')"
pubsub_service_agent="service-${project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud iam service-accounts add-iam-policy-binding "${runtime_sa_email}" \
  --member="serviceAccount:${pubsub_service_agent}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project="${project_id}"

for role_name in \
  roles/datastore.user \
  roles/pubsub.publisher \
  roles/aiplatform.user \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${project_id}" \
    --member="serviceAccount:${runtime_sa_email}" \
    --role="${role_name}" \
    --condition=None \
    --project="${project_id}"
done

if ! gcloud firestore databases describe --database='(default)' --project="${project_id}" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --database='(default)' \
    --location="${firestore_location}" \
    --type=firestore-native \
    --project="${project_id}"
fi

if ! gcloud pubsub topics describe "${topic_name}" --project="${project_id}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${topic_name}" --project="${project_id}"
fi

gcloud run deploy "${service_name}" \
  --source=. \
  --region="${region}" \
  --service-account="${runtime_sa_email}" \
  --no-allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --cpu=1 \
  --memory=1Gi \
  --timeout=300 \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${project_id},GOOGLE_CLOUD_LOCATION=global,FIRESTORE_ENABLED=1,FIRESTORE_COLLECTION=fourproof_missions,PUBSUB_TOPIC=${topic_name},PUBSUB_SERVICE_ACCOUNT_EMAIL=${runtime_sa_email},APP_GIT_SHA=${git_sha},LIVE_MISSION_TOTAL_LIMIT=${max_live_missions},MISSION_LIMIT_PER_HOUR=${max_live_missions}" \
  --project="${project_id}"

service_url="$(gcloud run services describe "${service_name}" --region="${region}" --project="${project_id}" --format='value(status.url)')"
service_host="${service_url#https://}"

gcloud run services add-iam-policy-binding "${service_name}" \
  --region="${region}" \
  --member="serviceAccount:${runtime_sa_email}" \
  --role="roles/run.invoker" \
  --project="${project_id}"

gcloud run services update "${service_name}" \
  --region="${region}" \
  --update-env-vars="PUBSUB_AUDIENCE=${service_url},ALLOWED_LIVE_HOSTS=${service_host}" \
  --project="${project_id}"

push_endpoint="${service_url}/api/internal/pubsub"
if gcloud pubsub subscriptions describe "${subscription_name}" --project="${project_id}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "${subscription_name}" \
    --push-endpoint="${push_endpoint}" \
    --push-auth-service-account="${runtime_sa_email}" \
    --push-auth-token-audience="${service_url}" \
    --ack-deadline=600 \
    --min-retry-delay=10s \
    --max-retry-delay=60s \
    --project="${project_id}"
else
  gcloud pubsub subscriptions create "${subscription_name}" \
    --topic="${topic_name}" \
    --push-endpoint="${push_endpoint}" \
    --push-auth-service-account="${runtime_sa_email}" \
    --push-auth-token-audience="${service_url}" \
    --ack-deadline=600 \
    --min-retry-delay=10s \
    --max-retry-delay=60s \
    --project="${project_id}"
fi

public_ack_value="I_CONFIRM_USER_AUTHORIZED_PUBLIC_CLOUD_RUN_DEMO"
if [[ "${FOURPROOF_PUBLIC_DEMO_ACK:-}" == "${public_ack_value}" ]]; then
  gcloud run services add-iam-policy-binding "${service_name}" \
    --region="${region}" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --project="${project_id}"
  echo "Public Cloud Run demo authorized and enabled: ${service_url}"
else
  echo "Cloud Run remains private. A separate action-time public-demo authorization is required before live proof or judging."
fi

echo "Deployment requested: ${service_url}"
echo "Do not claim completion until docs/cloud-proof-checklist.md is verified with live evidence."
