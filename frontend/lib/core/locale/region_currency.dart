/// Best-effort country → currency mapping, used only to pick a sensible
/// *default* for a first-time user — never silently overrides an explicit
/// choice already saved to their profile. Limited to codes the backend's
/// fx_service.SUPPORTED_CURRENCIES actually has live rates for.
const Map<String, String> _countryToCurrency = {
  'KR': 'KRW',
  'US': 'USD',
  'GB': 'GBP',
  'JP': 'JPY',
  'CN': 'CNY',
  'IN': 'INR',
  'CA': 'CAD',
  'AU': 'AUD',
  'NZ': 'NZD',
  'CH': 'CHF',
  'SE': 'SEK',
  'NO': 'NOK',
  'DK': 'DKK',
  'HK': 'HKD',
  'SG': 'SGD',
  'MY': 'MYR',
  'TH': 'THB',
  'PH': 'PHP',
  'ID': 'IDR',
  'IL': 'ILS',
  'MX': 'MXN',
  'BR': 'BRL',
  'ZA': 'ZAR',
  'TR': 'TRY',
  'PL': 'PLN',
  'CZ': 'CZK',
  'HU': 'HUF',
  'RO': 'RON',
  'IS': 'ISK',
  // Eurozone.
  'DE': 'EUR', 'FR': 'EUR', 'ES': 'EUR', 'IT': 'EUR', 'NL': 'EUR',
  'BE': 'EUR', 'AT': 'EUR', 'PT': 'EUR', 'IE': 'EUR', 'FI': 'EUR',
  'GR': 'EUR', 'LU': 'EUR', 'SK': 'EUR', 'SI': 'EUR', 'LT': 'EUR',
  'LV': 'EUR', 'EE': 'EUR', 'CY': 'EUR', 'MT': 'EUR', 'HR': 'EUR',
};

String currencyForCountryCode(String? countryCode) {
  if (countryCode == null) return 'USD';
  return _countryToCurrency[countryCode.toUpperCase()] ?? 'USD';
}
