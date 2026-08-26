import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../core/config/api_config.dart';
import '../../core/network/api_client.dart';
import '../models/chat_message.dart';

class ChatRepository {
  final Dio _dio;

  ChatRepository(this._dio);

  Future<List<ChatMessage>> fetchHistory() async {
    final response = await _dio.get('/copilot/history');
    return (response.data as List)
        .map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
        .toList();
  }

  WebSocketChannel connect() {
    final uri = Uri.parse('${ApiConfig.wsBaseUrl}/copilot?user_id=${ApiConfig.devUserId}');
    return WebSocketChannel.connect(uri);
  }

  void send(WebSocketChannel channel, String content) {
    channel.sink.add(jsonEncode({'content': content}));
  }
}

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepository(ref.watch(dioProvider));
});
