import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/network/api_error.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/expense_category.dart';
import '../data/models/goal.dart';
import '../data/repositories/goal_repository.dart';
import '../widgets/bounded_content.dart';
import 'goals_screen.dart' show entryCurrency;

class AddGoalScreen extends ConsumerStatefulWidget {
  const AddGoalScreen({super.key});

  @override
  ConsumerState<AddGoalScreen> createState() => _AddGoalScreenState();
}

class _AddGoalScreenState extends ConsumerState<AddGoalScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _target = TextEditingController();
  final _starting = TextEditingController();
  GoalType _type = GoalType.savings;
  ExpenseCategory? _category;
  DateTime _targetDate = DateTime.now().add(const Duration(days: 30));
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _target.dispose();
    _starting.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _targetDate,
      firstDate: DateTime(now.year, now.month, now.day),
      lastDate: DateTime(now.year + 10),
    );
    if (picked != null) setState(() => _targetDate = picked);
  }

  String? _validateAmount(String? value, {required bool required}) {
    final text = value?.trim() ?? '';
    if (text.isEmpty) return required ? 'Required' : null;
    final parsed = double.tryParse(text);
    if (parsed == null) return 'Enter a number';
    if (required ? parsed <= 0 : parsed < 0) return required ? 'Must be greater than zero' : 'Cannot be negative';
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final currency = entryCurrency(ref);
    double toKrw(String text) => (double.tryParse(text.trim()) ?? 0) / currency.rateFromKrw;

    setState(() => _saving = true);
    try {
      await ref.read(goalRepositoryProvider).createGoal(
            name: _name.text.trim(),
            goalType: _type,
            targetAmountKrw: toKrw(_target.text),
            startingAmountKrw: _type == GoalType.savings ? toKrw(_starting.text) : 0,
            category: _type == GoalType.spendingCap ? _category : null,
            targetDate: _targetDate,
          );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final currencyCode = entryCurrency(ref).code;
    final isSavings = _type == GoalType.savings;
    final amountFormatter = FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}'));

    return Scaffold(
      appBar: AppBar(title: const Text('New goal')),
      body: BoundedContent(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SegmentedButton<GoalType>(
                segments: const [
                  ButtonSegment(value: GoalType.savings, label: Text('Save toward'), icon: Icon(Icons.savings_outlined)),
                  ButtonSegment(value: GoalType.spendingCap, label: Text('Cap spending'), icon: Icon(Icons.speed_rounded)),
                ],
                selected: {_type},
                onSelectionChanged: (selection) => setState(() => _type = selection.first),
              ),
              const SizedBox(height: 12),
              Text(
                isSavings
                    ? 'Log contributions as you save. Meika projects whether your real saving pace reaches the '
                        'target by the date, and what daily change would fix it if not.'
                    : 'Meika tracks the expenses you log (including transit) against this cap and tells you how '
                        'much you can still spend per day.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65)),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _name,
                maxLength: 120,
                decoration: InputDecoration(labelText: isSavings ? 'Goal name (e.g. Winter trip)' : 'Cap name (e.g. Coffee this month)'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              TextFormField(
                controller: _target,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [amountFormatter],
                decoration: InputDecoration(labelText: '${isSavings ? 'Target amount' : 'Spending cap'} ($currencyCode)'),
                validator: (v) => _validateAmount(v, required: true),
              ),
              const SizedBox(height: 12),
              if (isSavings)
                TextFormField(
                  controller: _starting,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  inputFormatters: [amountFormatter],
                  decoration: InputDecoration(
                    labelText: 'Already saved ($currencyCode, optional)',
                    helperText: 'Counts toward progress, but not toward your saving pace',
                  ),
                  validator: (v) => _validateAmount(v, required: false),
                )
              else
                DropdownButtonFormField<ExpenseCategory?>(
                  initialValue: _category,
                  decoration: const InputDecoration(labelText: 'Category'),
                  items: [
                    const DropdownMenuItem<ExpenseCategory?>(value: null, child: Text('All spending')),
                    ...ExpenseCategory.values.map(
                      (c) => DropdownMenuItem<ExpenseCategory?>(value: c, child: Text(c.displayName)),
                    ),
                  ],
                  onChanged: (c) => setState(() => _category = c),
                ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Target date: ${DateFormat.yMMMd().format(_targetDate)}',
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.calendar_today_rounded, size: 16),
                    label: const Text('Change'),
                    onPressed: _pickDate,
                  ),
                ],
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _saving ? null : _submit,
                child: _saving
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Create goal'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
