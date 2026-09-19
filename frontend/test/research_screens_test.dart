// Renders the Foresight research screens against real API responses
// (test/fixtures, captured from the running backend and the backend's own
// services) at a phone width. A RenderFlex overflow or any exception during
// build fails the test, which is the point: these screens are dense and the
// browser pane can't always be driven.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meika/data/models/exposure.dart';
import 'package:meika/data/models/income_stream.dart';
import 'package:meika/data/models/survival_report.dart';
import 'package:meika/data/models/user_profile.dart';
import 'package:meika/data/models/vulnerability_report.dart';
import 'package:meika/data/repositories/exposure_repository.dart';
import 'package:meika/data/repositories/vulnerability_repository.dart';
import 'package:meika/providers/currency_providers.dart';
import 'package:meika/providers/survival_providers.dart';
import 'package:meika/screens/exposure_screen.dart';
import 'package:meika/screens/research_hub_screen.dart';
import 'package:meika/screens/survival_screen.dart';
import 'package:meika/screens/vulnerability_screen.dart';

dynamic fixture(String name) => jsonDecode(File('test/fixtures/$name.json').readAsStringSync());

Future<void> pumpScreen(WidgetTester tester, Widget screen, List<Override> overrides) async {
  // Phone width; tall enough that the whole ListView is built and checked.
  tester.view.physicalSize = const Size(390 * 2, 3200 * 2);
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    ProviderScope(
      overrides: overrides,
      child: MaterialApp(home: screen),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 200));
}

List<Override> commonOverrides() => [
      userProfileProvider.overrideWith(
        (ref) async => UserProfile.fromJson(fixture('user_profile') as Map<String, dynamic>),
      ),
      fxRatesProvider.overrideWith((ref) async => <String, double>{}),
    ];

void main() {
  testWidgets('early warning renders a computed report', (tester) async {
    final report = LeadingIndicatorReport.fromJson(fixture('vulnerability_computed') as Map<String, dynamic>);
    await pumpScreen(tester, const VulnerabilityScreen(), [
      ...commonOverrides(),
      leadingIndicatorsProvider.overrideWith((ref, asOf) async => report),
    ]);

    expect(tester.takeException(), isNull);
    expect(find.text('Early-warning pressure'), findsOneWidget);
    expect(find.text('${report.score}'), findsOneWidget);
    expect(find.text('Lead time'), findsOneWidget);
    expect(find.text('Signals'), findsOneWidget);
    // Every component gets a row labelled by its factor.
    for (final factor in report.factors.sublist(1, report.factors.length - 1)) {
      expect(find.text(factor.label), findsWidgets);
    }
  });

  testWidgets('early warning shows the blackout state instead of a score', (tester) async {
    final report = LeadingIndicatorReport.fromJson(fixture('vulnerability_blackout') as Map<String, dynamic>);
    await pumpScreen(tester, const VulnerabilityScreen(), [
      ...commonOverrides(),
      leadingIndicatorsProvider.overrideWith((ref, asOf) async => report),
    ]);

    expect(tester.takeException(), isNull);
    expect(find.text('No early-warning score yet'), findsOneWidget);
    expect(find.text('Day ${report.readiness.daysOfHistory} of 84 of history'), findsOneWidget);
    expect(find.text('Early-warning pressure'), findsNothing);
  });

  List<Override> survivalOverrides(String reportFixture) => [
        ...commonOverrides(),
        incomeStreamsProvider.overrideWith(
          (ref) async => (fixture('income_streams') as List)
              .map((e) => IncomeStream.fromJson(e as Map<String, dynamic>))
              .toList(),
        ),
        shockPresetsProvider.overrideWith(
          (ref) async => (fixture('survival_presets') as List)
              .map((e) => ShockPreset.fromJson(e as Map<String, dynamic>))
              .toList(),
        ),
        survivalReportProvider.overrideWith(
          (ref, requestJson) async => SurvivalReport.fromJson(fixture(reportFixture) as Map<String, dynamic>),
        ),
      ];

  testWidgets('survival renders runway, attribution and factors, and presets toggle', (tester) async {
    await pumpScreen(tester, const SurvivalScreen(), survivalOverrides('survival_report'));

    expect(tester.takeException(), isNull);
    expect(find.text('Liquid savings'), findsOneWidget);
    expect(find.text('Monthly income'), findsOneWidget);
    expect(find.text('Runway'), findsOneWidget);
    expect(find.text('Which shock does the damage'), findsOneWidget);
    expect(find.text('Why these numbers'), findsOneWidget);

    final firstPreset = ShockPreset.fromJson((fixture('survival_presets') as List).first as Map<String, dynamic>);
    await tester.tap(find.widgetWithText(FilterChip, firstPreset.title));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    expect(tester.takeException(), isNull);
    // Selecting a shock reveals its severity slider.
    expect(find.byType(Slider), findsNWidgets(2));
  });

  testWidgets('survival without savings asks for them instead of inventing a runway', (tester) async {
    await pumpScreen(tester, const SurvivalScreen(), survivalOverrides('survival_needs_savings'));

    expect(tester.takeException(), isNull);
    expect(find.text('Add your savings to see a runway'), findsOneWidget);
    expect(find.text('Runway'), findsNothing);
  });

  testWidgets('hub opens the early warning module', (tester) async {
    final report = LeadingIndicatorReport.fromJson(fixture('vulnerability_computed') as Map<String, dynamic>);
    tester.view.physicalSize = const Size(390 * 2, 844 * 2);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          ...commonOverrides(),
          leadingIndicatorsProvider.overrideWith((ref, asOf) async => report),
        ],
        child: const MaterialApp(home: Scaffold(body: ResearchHubScreen())),
      ),
    );
    await tester.tap(find.text('Early warning'));
    await tester.pumpAndSettle();
    expect(find.text('Early-warning pressure'), findsOneWidget);
  });

  List<Override> exposureOverrides(String insightsFixture) => [
        ...commonOverrides(),
        exposureInsightsProvider.overrideWith(
          (ref) async => ExposureInsightReport.fromJson(fixture(insightsFixture) as Map<String, dynamic>),
        ),
        exposureSessionsProvider.overrideWith(
          (ref) async => (fixture('exposure_sessions') as List)
              .map((s) => ExposureSessionEntry.fromJson(s as Map<String, dynamic>))
              .toList(),
        ),
      ];

  testWidgets('exposure renders the association, effect and exploratory breakdown', (tester) async {
    final report = ExposureInsightReport.fromJson(fixture('exposure_insights') as Map<String, dynamic>);
    await pumpScreen(tester, const ExposureScreen(), exposureOverrides('exposure_insights'));

    expect(tester.takeException(), isNull);
    expect(find.text(report.associationFound ? 'Screen time lines up with your spending' : 'No clear link found'),
        findsWidgets);
    expect(find.text('Exploratory breakdown'), findsOneWidget);
    expect(find.text('Recent screen time'), findsOneWidget);
    if (report.effect != null) {
      expect(find.text('Discretionary spending that day and the next'), findsOneWidget);
    }
    expect(find.text(report.intervention.triggered ? 'Pause before you buy' : 'No nudge today'), findsWidgets);
  });

  testWidgets('exposure with too little data reports that instead of a correlation', (tester) async {
    await pumpScreen(tester, const ExposureScreen(), exposureOverrides('exposure_insufficient'));

    expect(tester.takeException(), isNull);
    expect(find.text('Not enough data yet'), findsOneWidget);
    expect(find.text('Exploratory breakdown'), findsNothing);
  });
}
