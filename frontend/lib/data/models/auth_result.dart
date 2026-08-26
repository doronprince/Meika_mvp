class AuthResult {
  final String accessToken;
  final String userId;

  const AuthResult({required this.accessToken, required this.userId});

  factory AuthResult.fromJson(Map<String, dynamic> json) {
    return AuthResult(
      accessToken: json['access_token'] as String,
      userId: json['user_id'] as String,
    );
  }
}
