variable "subscription_id" {
  description = "Azure subscription id used only at apply time."
  type        = string
}

variable "tenant_id" {
  description = "Microsoft Entra tenant id."
  type        = string
}

variable "location" {
  description = "Azure region for the foundation resources."
  type        = string
  default     = "francecentral"
}

variable "prefix" {
  description = "Short globally-unique workload prefix."
  type        = string
  default     = "tradeops"
}

variable "environment" {
  type    = string
  default = "lab"
  validation {
    condition     = contains(["lab", "dev", "preprod", "prod"], var.environment)
    error_message = "environment must be lab, dev, preprod or prod"
  }
}

variable "cost_center" {
  type    = string
  default = "architecture-lab"
}

variable "data_classification" {
  type    = string
  default = "confidential"
}
