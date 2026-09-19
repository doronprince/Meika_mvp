// Renders the tax & compliance foresight screen against engine output
// (test/fixtures/compliance_*.json, produced by the backend's own
// compliance_engine.evaluate_ledger — the same serialization the API
// returns) at a phone width. A RenderFlex overflow or any exception during
// build fails the test.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meika/data/models/compliance_foresight.dart';
import 'package:meika/data/models/user_profile.dart';
import 'package:meika/data/repositories/compliance_repository.dart';
import 'package:meika/providers/currency_providers.dart';
import 'package:meika/screens/compliance_screen.dart';

dynamic fixture(String name) => jsonDecode(File('test/fixtures/$name.json').readAsStringSync());

Future<void> pumpCompliance(WidgetTester tester, String fixtureName) async {
  // Phone width; tall enough that the lazy ListView builds every flag card.
  tester.view.physicalSize = const Size(390 * 2, 12000 * 2);
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        userProfileProvider.overrideWith(
          (ref) async => UserProfile.fromJson(fixture('user_profile') as Map<String, dynamic>),
        ),
        fxRatesProvider.overrideWith((ref) async => <String, double>{}),
        complianceForesightProvider.overrideWith(
          (ref) async => ComplianceForesight.fromJson(fixture(fixtureName) as Map<String, dynamic>),
        ),
      ],
      child: const MaterialApp(home: ComplianceScreen()),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 200));
}

void main() {
  testWidgets('flags render with their question, figure and referral', (tester) async {
    await pumpCompliance(tester, 'compliance_foresight');
    final data = ComplianceForesight.fromJson(fixture('compliance_foresight') as Map<String, dynamic>);

    expect(find.text('Tax & compliance foresight'), findsOneWidget);
    expect(find.textContaining('not a tax adviser'), findsOneWidget);
    // The coverage card's title, plus the same-named coverage factor that
    // each flag carries in its explanation.
    final coverageFactors = data.flags.where((f) => f.factors.any((x) => x.label == 'What Meika can see')).length;
    expect(find.text('What Meika can see'), findsNWidgets(1 + coverageFactors));
    expect(data.flags, isNotEmpty);
    for (final flag in data.flags) {
      expect(find.text(flag.question), findsOneWidget);
    }
    // Every flag ends with the referral; the screen shows each one.
    expect(find.text('Confirm this with a qualified professional'), findsNWidgets(data.flags.length));
    expect(find.textContaining("Meika's default — unverified"), findsWidgets);
    expect(find.textContaining('Rules with nothing to flag'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('an empty ledger says so instead of showing an all-clear', (tester) async {
    await pumpCompliance(tester, 'compliance_empty');

    expect(find.textContaining('Meika has no expenses to look at yet'), findsOneWidget);
    expect(find.text('No expenses yet'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
