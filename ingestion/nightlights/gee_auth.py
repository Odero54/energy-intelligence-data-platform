"""Google Earth Engine authentication helper.

Supports two modes (checked in order):
  1. Service account — set GEE_SERVICE_ACCOUNT and GEE_PRIVATE_KEY_FILE in .env
  2. Default credentials — run `earthengine authenticate` once, then leave envs unset
"""

import os

import ee
from dotenv import load_dotenv

load_dotenv()


def authenticate() -> None:
    service_account = os.environ.get("GEE_SERVICE_ACCOUNT")
    key_file = os.environ.get("GEE_PRIVATE_KEY_FILE")

    if service_account and key_file:
        credentials = ee.ServiceAccountCredentials(service_account, key_file)
        ee.Initialize(credentials)
        print(f"  GEE authenticated via service account: {service_account}")
    else:
        # Falls back to credentials stored by `earthengine authenticate`
        ee.Initialize()
        print("  GEE authenticated via default credentials")
