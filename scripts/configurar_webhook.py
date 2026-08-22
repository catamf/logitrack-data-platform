"""Guarda el webhook de notificaciones directamente en Azure Key Vault."""
from __future__ import annotations

import argparse
import getpass

from azure.identity import AzureCliCredential
from azure.keyvault.secrets import SecretClient

SECRET_NAME = "notification-webhook-url"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guarda el webhook LogiTrack sin escribirlo en archivos, Git o Terraform state."
    )
    parser.add_argument(
        "--vault-url",
        required=True,
        help="URI del Key Vault, por ejemplo https://kv-logitrack.vault.azure.net/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    webhook = getpass.getpass("Webhook de Teams/Slack (entrada oculta): ").strip()
    if not webhook.startswith("https://"):
        raise ValueError("El webhook debe comenzar por https://")

    client = SecretClient(vault_url=args.vault_url, credential=AzureCliCredential())
    client.set_secret(SECRET_NAME, webhook)
    print(f"Secreto '{SECRET_NAME}' guardado en Key Vault.")


if __name__ == "__main__":
    main()
