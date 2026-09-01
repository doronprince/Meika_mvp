import 'package:intl/intl.dart';

final _krwFormat = NumberFormat.currency(locale: 'ko_KR', symbol: '₩', decimalDigits: 0);

String formatKrw(num value) => _krwFormat.format(value);

/// Matches the backend's fx_service.SUPPORTED_CURRENCIES exactly — every
/// code here is guaranteed a real rate from GET /fx/rates.
const supportedCurrencies = {
  'AUD', 'BRL', 'CAD', 'CHF', 'CNY', 'CZK', 'DKK', 'EUR', 'GBP', 'HKD',
  'HUF', 'IDR', 'ILS', 'INR', 'ISK', 'JPY', 'KRW', 'MXN', 'MYR', 'NOK',
  'NZD', 'PHP', 'PLN', 'RON', 'SEK', 'SGD', 'THB', 'TRY', 'USD', 'ZAR',
};

const _zeroDecimalCurrencies = {'JPY', 'KRW', 'ISK'};

const _symbols = {
  'USD': '\$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'KRW': '₩', 'CNY': '¥',
  'INR': '₹', 'AUD': 'A\$', 'CAD': 'C\$', 'NZD': 'NZ\$', 'HKD': 'HK\$',
  'SGD': 'S\$', 'CHF': 'CHF ', 'SEK': 'kr ', 'NOK': 'kr ', 'DKK': 'kr ',
};

/// Formats an amount already converted into [currencyCode]. Use
/// [formatKrw] when the figure is specifically KRW and currency-neutral
/// display is intended (e.g. Price-Finder's underlying sticker prices are
/// always genuinely KRW transactions in Seoul).
String formatCurrency(num value, String currencyCode) {
  final symbol = _symbols[currencyCode] ?? '$currencyCode ';
  final decimalDigits = _zeroDecimalCurrencies.contains(currencyCode) ? 0 : 2;
  return NumberFormat.currency(symbol: symbol, decimalDigits: decimalDigits).format(value);
}
