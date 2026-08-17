import 'package:intl/intl.dart';

final _krwFormat = NumberFormat.currency(locale: 'ko_KR', symbol: '₩', decimalDigits: 0);

String formatKrw(num value) => _krwFormat.format(value);
