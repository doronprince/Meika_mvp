import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_token_provider.dart';
import '../config/api_config.dart';

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      // A free hosted instance sleeps when idle and takes ~30-60s to wake,
      // so the first request after a pause must be allowed to wait for it.
      // At 15s every cold start showed up as "couldn't reach the backend".
      connectTimeout: const Duration(seconds: 90),
      // Price-Finder's live search can wait up to 20s on SerpApi
      // (live_price_service.py) before falling back to the seed catalog —
      // this must stay comfortably above that or a slow-but-successful
      // live search fails on the client side before the backend even
      // finishes.
      receiveTimeout: const Duration(seconds: 30),
    ),
  );

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        final token = ref.read(authTokenProvider);
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
    ),
  );

  return dio;
});
