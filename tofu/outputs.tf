output "url" {
  description = "URL for the storage-ui UI once DNS/hosts is configured."
  value       = "https://${var.ingress_hostname}"
}
