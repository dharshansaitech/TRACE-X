# infra/terraform/main.tf
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    bucket = "tracex-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── APIs ──────────────────────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "firestore.googleapis.com",
    "bigquery.googleapis.com",
    "pubsub.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ── Artifact Registry ─────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "tracex" {
  location      = var.region
  repository_id = "tracex"
  description   = "TRACE-X Docker images"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# ── Firestore ─────────────────────────────────────────────────────────────────
resource "google_firestore_database" "tracex" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

# ── BigQuery ──────────────────────────────────────────────────────────────────
resource "google_bigquery_dataset" "tracex" {
  dataset_id  = "tracex_analytics"
  description = "TRACE-X analytics and long-term trace storage"
  location    = var.region
  depends_on  = [google_project_service.apis]
}

# ── Pub/Sub Topics ────────────────────────────────────────────────────────────
resource "google_pubsub_topic" "traces" {
  name = "tracex-traces"
  message_retention_duration = "86600s"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "events" {
  name = "tracex-events"
  message_retention_duration = "86600s"
}

resource "google_pubsub_topic" "repairs" {
  name = "tracex-repairs"
  message_retention_duration = "86600s"
}

resource "google_pubsub_subscription" "traces_sub" {
  name  = "tracex-traces-sub"
  topic = google_pubsub_topic.traces.name
  ack_deadline_seconds = 60
  message_retention_duration = "86400s"

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "events_sub" {
  name  = "tracex-events-sub"
  topic = google_pubsub_topic.events.name
  ack_deadline_seconds = 30
}

# ── Service Accounts ──────────────────────────────────────────────────────────
resource "google_service_account" "backend" {
  account_id   = "tracex-backend"
  display_name = "TRACE-X Backend Service Account"
}

resource "google_project_iam_member" "backend_roles" {
  for_each = toset([
    "roles/datastore.user",
    "roles/bigquery.dataEditor",
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.backend.email}"
}

# ── Cloud Run: Backend ────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "backend" {
  name     = "tracex-backend"
  location = var.region

  template {
    service_account = google_service_account.backend.email

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/tracex/backend:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.tracex,
  ]
}

# Cloud Run backend IAM — public access
resource "google_cloud_run_v2_service_iam_member" "backend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Cloud Run: Frontend ───────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "frontend" {
  name     = "tracex-frontend"
  location = var.region

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/tracex/frontend:latest"

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "${google_cloud_run_v2_service.backend.uri}/api/v1"
      }
      env {
        name  = "NEXT_PUBLIC_WS_URL"
        value = replace("${google_cloud_run_v2_service.backend.uri}/ws", "https://", "wss://")
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_cloud_run_v2_service.backend]
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
