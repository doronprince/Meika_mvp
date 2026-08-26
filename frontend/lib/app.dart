import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/auth/auth_token_provider.dart';
import 'core/theme/zen_theme.dart';
import 'screens/login_screen.dart';
import 'widgets/shell/app_shell.dart';

class MeikaApp extends ConsumerWidget {
  const MeikaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final token = ref.watch(authTokenProvider);

    return MaterialApp(
      title: 'Meika',
      debugShowCheckedModeBanner: false,
      theme: ZenTheme.light,
      home: token == null ? const LoginScreen() : const AppShell(),
    );
  }
}
