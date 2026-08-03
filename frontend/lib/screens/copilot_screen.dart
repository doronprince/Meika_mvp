import 'package:flutter/material.dart';

import '../widgets/coming_soon.dart';

class CopilotScreen extends StatelessWidget {
  const CopilotScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ComingSoon(
      title: 'Wise Guide Copilot',
      subtitle: 'XAI chat with live reasoning panels — arrives in Phase 7.',
    );
  }
}
