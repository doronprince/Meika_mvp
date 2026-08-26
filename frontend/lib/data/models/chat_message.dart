class XaiFactor {
  final String label;
  final String detail;

  const XaiFactor({required this.label, required this.detail});

  factory XaiFactor.fromJson(Map<String, dynamic> json) {
    return XaiFactor(label: json['label'] as String, detail: json['detail'] as String);
  }
}

enum ChatRole {
  user,
  assistant;

  static ChatRole fromJson(String value) => value == 'user' ? ChatRole.user : ChatRole.assistant;
}

class ChatMessage {
  final String id;
  final ChatRole role;
  final String content;
  final List<XaiFactor> xaiFactors;
  final DateTime createdAt;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.xaiFactors,
    required this.createdAt,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as String,
      role: ChatRole.fromJson(json['role'] as String),
      content: json['content'] as String,
      xaiFactors: (json['xai_factors'] as List? ?? [])
          .map((f) => XaiFactor.fromJson(f as Map<String, dynamic>))
          .toList(),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  factory ChatMessage.pending(String id, String content) {
    return ChatMessage(
      id: id,
      role: ChatRole.user,
      content: content,
      xaiFactors: const [],
      createdAt: DateTime.now(),
    );
  }
}
