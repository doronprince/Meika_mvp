import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../data/models/chat_message.dart';
import '../data/repositories/chat_repository.dart';

class ChatUiState {
  final List<ChatMessage> messages;
  final bool isLoadingHistory;
  final bool isWaitingForReply;
  final String? error;

  const ChatUiState({
    this.messages = const [],
    this.isLoadingHistory = true,
    this.isWaitingForReply = false,
    this.error,
  });

  ChatUiState copyWith({
    List<ChatMessage>? messages,
    bool? isLoadingHistory,
    bool? isWaitingForReply,
    String? error,
    bool clearError = false,
  }) {
    return ChatUiState(
      messages: messages ?? this.messages,
      isLoadingHistory: isLoadingHistory ?? this.isLoadingHistory,
      isWaitingForReply: isWaitingForReply ?? this.isWaitingForReply,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class ChatController extends StateNotifier<ChatUiState> {
  final ChatRepository _repo;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;

  ChatController(this._repo) : super(const ChatUiState()) {
    _init();
  }

  Future<void> _init() async {
    try {
      final history = await _repo.fetchHistory();
      state = state.copyWith(messages: history, isLoadingHistory: false, clearError: true);
      _connect();
    } catch (e) {
      state = state.copyWith(isLoadingHistory: false, error: e.toString());
    }
  }

  void _connect() {
    try {
      _channel = _repo.connect();
    } catch (e) {
      state = state.copyWith(error: 'Could not connect to the Wise Guide: $e');
      return;
    }

    _subscription = _channel!.stream.listen(
      (raw) {
        try {
          final decoded = jsonDecode(raw as String) as Map<String, dynamic>;
          if (decoded['type'] == 'message') {
            final message = ChatMessage.fromJson(decoded['message'] as Map<String, dynamic>);
            state = state.copyWith(messages: [...state.messages, message], isWaitingForReply: false);
          } else if (decoded['type'] == 'error') {
            state = state.copyWith(isWaitingForReply: false, error: decoded['detail'] as String?);
          }
        } catch (_) {
          state = state.copyWith(isWaitingForReply: false, error: 'Received an unreadable reply.');
        }
      },
      onError: (_) => state = state.copyWith(isWaitingForReply: false, error: 'Connection to the Wise Guide dropped.'),
      onDone: () => state = state.copyWith(isWaitingForReply: false),
    );
  }

  void sendMessage(String content) {
    final trimmed = content.trim();
    if (trimmed.isEmpty || _channel == null) return;

    final optimistic = ChatMessage.pending('local-${DateTime.now().microsecondsSinceEpoch}', trimmed);
    state = state.copyWith(messages: [...state.messages, optimistic], isWaitingForReply: true, clearError: true);
    _repo.send(_channel!, trimmed);
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}

final chatControllerProvider = StateNotifierProvider.autoDispose<ChatController, ChatUiState>((ref) {
  return ChatController(ref.watch(chatRepositoryProvider));
});
