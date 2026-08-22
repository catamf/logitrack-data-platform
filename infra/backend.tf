terraform {
  # Los valores reales se pasan con -backend-config=backend/backend-dev.hcl.
  # El state nunca debe confirmarse en Git.
  backend "azurerm" {}
}
