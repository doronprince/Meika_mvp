import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/auth/auth_token_provider.dart';
import '../../core/config/api_config.dart';
import '../../core/network/api_client.dart';
import '../models/chat_message.dart';

class ChatRepository {
  final Dio _dio;
  final Ref _ref;

  ChatRepository(this._dio, this._ref);

  Future<List<ChatMessage>> fetchHistory() async {
    final response = await _dio.get('/copilot/history');
    return (response.data as List)
        .map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
        .toList();
  }

  WebSocketChannel connect() {
    final token = _ref.read(authTokenProvider);
    if (token == null) {
      throw StateError('Cannot open the Copilot connection while signed out.');
    }
    final uri = Uri.parse('${ApiConfig.wsBaseUrl}/copilot?token=$token');
    return WebSocketChannel.connect(uri);
  }

  void send(WebSocketChannel channel, String content) {
    channel.sink.add(jsonEncode({'content': content}));
  }
}

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepository(ref.watch(dioProvider), ref);
});
