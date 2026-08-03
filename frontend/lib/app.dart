import 'package:flutter/material.dart';

import 'core/theme/zen_theme.dart';
import 'widgets/shell/app_shell.dart';

class MeikaApp extends StatelessWidget {
  const MeikaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Meika',
      debugShowCheckedModeBanner: false,
      theme: ZenTheme.light,
      home: const AppShell(),
    );
  }
}
