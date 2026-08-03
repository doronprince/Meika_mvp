import 'package:flutter/material.dart';

import '../widgets/coming_soon.dart';

class PriceFinderScreen extends StatelessWidget {
  const PriceFinderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ComingSoon(
      title: 'AI Price-Finder',
      subtitle: 'True Economic Cost comparisons across Seoul retailers — arrives in Phase 6.',
    );
  }
}
