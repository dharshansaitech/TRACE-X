# infra/terraform/outputs.tf
output "backend_url" {
  description = "TRACE-X backend Cloud Run URL"
  value       = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  description = "TRACE-X frontend Cloud Run URL"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "backend_api_url" {
  description = "TRACE-X backend API URL"
  value       = "${google_cloud_run_v2_service.backend.uri}/api/v1"
}

output "websocket_url" {
  description = "WebSocket URL"
  value       = "${replace(google_cloud_run_v2_service.backend.uri, "https://", "wss://")}/ws"
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.tracex.name
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.tracex.dataset_id
}

output "artifact_registry" {
  description = "Artifact Registry repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/tracex"
}

output "backend_service_account" {
  description = "Backend service account email"
  value       = google_service_account.backend.email
}
