import 'package:dio/dio.dart';

/// The most useful human-readable message from a failed API call: FastAPI's
/// `detail` string, the first validation message of a 422, or the raw error.
String apiErrorMessage(Object error) {
  if (error is DioException) {
    final data = error.response?.data;
    final detail = data is Map ? data['detail'] : null;
    if (detail is String) return detail;
    if (detail is List && detail.isNotEmpty && detail.first is Map) {
      final msg = (detail.first as Map)['msg'];
      if (msg != null) return msg.toString().replaceFirst('Value error, ', '');
    }
    return error.message ?? 'Request failed';
  }
  return error.toString();
}
