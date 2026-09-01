import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/format/currency.dart';
import '../core/theme/zen_theme.dart';
import '../data/repositories/user_repository.dart';
import '../providers/currency_providers.dart';

Future<void> showCurrencyPicker(BuildContext context, WidgetRef ref) async {
  final current = ref.read(preferredCurrencyProvider);
  final selected = await showDialog<String>(
    context: context,
    builder: (context) => _CurrencyPickerDialog(current: current),
  );
  if (selected == null || selected == current) return;

  try {
    await ref.read(userRepositoryProvider).updatePreferredCurrency(selected);
    ref.invalidate(userProfileProvider);
  } catch (_) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't update your currency — try again.")),
      );
    }
  }
}

class _CurrencyPickerDialog extends StatelessWidget {
  final String current;

  const _CurrencyPickerDialog({required this.current});

  @override
  Widget build(BuildContext context) {
    final currencies = supportedCurrencies.toList()..sort();
    return AlertDialog(
      title: const Text('Display currency'),
      content: SizedBox(
        width: 320,
        height: 420,
        child: ListView.builder(
          itemCount: currencies.length,
          itemBuilder: (context, index) {
            final code = currencies[index];
            final isSelected = code == current;
            return ListTile(
              title: Text(code),
              trailing: isSelected ? const Icon(Icons.check_rounded, color: ZenColors.matcha) : null,
              onTap: () => Navigator.of(context).pop(code),
            );
          },
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
      ],
    );
  }
}
