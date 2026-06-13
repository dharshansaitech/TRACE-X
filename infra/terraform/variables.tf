# infra/terraform/variables.tf
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore location"
  type        = string
  default     = "us-central"
}

variable "gemini_model" {
  description = "Vertex AI Gemini model ID"
  type        = string
  default     = "gemini-2.0-flash-001"
}

variable "api_key" {
  description = "TRACE-X API key (store in Secret Manager)"
  type        = string
  sensitive   = true
  default     = "change-me-in-production"
}

variable "arize_api_key" {
  description = "Arize API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Must be development, staging, or production."
  }
}
