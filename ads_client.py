import os

from google.ads.googleads.client import GoogleAdsClient

_client = None


class AdsNotConfiguredError(Exception):
    """La cuenta de Google Ads todavia no tiene credenciales configuradas."""


def get_customer_id() -> str:
    customer_id = os.environ.get('GOOGLE_ADS_CUSTOMER_ID')
    if not customer_id:
        raise AdsNotConfiguredError('GOOGLE_ADS_CUSTOMER_ID no esta configurado.')
    return customer_id.replace('-', '')


def get_ads_client() -> GoogleAdsClient:
    global _client
    if _client is not None:
        return _client

    required = [
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'GOOGLE_ADS_CLIENT_ID',
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN',
        'GOOGLE_ADS_CUSTOMER_ID',
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise AdsNotConfiguredError(
            f"Faltan variables de entorno de Google Ads: {', '.join(missing)}"
        )

    config = {
        'developer_token': os.environ['GOOGLE_ADS_DEVELOPER_TOKEN'],
        'client_id': os.environ['GOOGLE_ADS_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_ADS_CLIENT_SECRET'],
        'refresh_token': os.environ['GOOGLE_ADS_REFRESH_TOKEN'],
        'login_customer_id': get_customer_id(),
        'use_proto_plus': True,
    }
    _client = GoogleAdsClient.load_from_dict(config)
    return _client
