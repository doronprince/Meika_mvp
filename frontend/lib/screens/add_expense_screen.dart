import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/format/currency.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/expense_category.dart';
import '../data/repositories/expense_repository.dart';
import '../providers/currency_providers.dart';

class AddExpenseScreen extends ConsumerStatefulWidget {
  const AddExpenseScreen({super.key});

  @override
  ConsumerState<AddExpenseScreen> createState() => _AddExpenseScreenState();
}

class _AddExpenseScreenState extends ConsumerState<AddExpenseScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _amountController = TextEditingController();
  final _storeController = TextEditingController();
  final _notesController = TextEditingController();

  ExpenseCategory _category = ExpenseCategory.groceries;
  DateTime _occurredOn = DateTime.now();
  bool _inForeignCurrency = false;
  String _foreignCurrency = 'USD';
  bool _isSubmitting = false;
  String? _error;

  @override
  void dispose() {
    _titleController.dispose();
    _amountController.dispose();
    _storeController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _occurredOn,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _occurredOn = picked);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _isSubmitting = true;
      _error = null;
    });

    final amount = double.parse(_amountController.text);
    try {
      await ref.read(expenseRepositoryProvider).createExpense(
            title: _titleController.text.trim(),
            category: _category,
            occurredOn: _occurredOn,
            amountKrw: _inForeignCurrency ? null : amount,
            foreignAmount: _inForeignCurrency ? amount : null,
            foreignCurrency: _inForeignCurrency ? _foreignCurrency : null,
            storeName: _storeController.text.trim(),
            notes: _notesController.text.trim(),
          );
      if (mounted) Navigator.of(context).pop(true);
    } on Exception catch (e) {
      setState(() => _error = 'Could not save this expense. $e');
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final preferredCurrency = ref.watch(preferredCurrencyProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Add Expense')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextFormField(
                controller: _titleController,
                decoration: const InputDecoration(labelText: 'Title'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<ExpenseCategory>(
                initialValue: _category,
                decoration: const InputDecoration(labelText: 'Category'),
                items: ExpenseCategory.values
                    .map((c) => DropdownMenuItem(value: c, child: Text(c.displayName)))
                    .toList(),
                onChanged: (v) => setState(() => _category = v!),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _amountController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                        labelText: _inForeignCurrency ? 'Amount ($_foreignCurrency)' : 'Amount (KRW)',
                      ),
                      validator: (v) {
                        final parsed = double.tryParse(v ?? '');
                        if (parsed == null || parsed <= 0) return 'Enter a positive amount';
                        return null;
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  if (_inForeignCurrency)
                    DropdownButton<String>(
                      value: _foreignCurrency,
                      items: supportedCurrencies
                          .where((c) => c != 'KRW')
                          .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                          .toList(),
                      onChanged: (v) => setState(() => _foreignCurrency = v!),
                    ),
                ],
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Paid in a foreign currency?',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
                  ),
                  Switch(
                    value: _inForeignCurrency,
                    onChanged: (v) => setState(() {
                      _inForeignCurrency = v;
                      if (v && _foreignCurrency == preferredCurrency && preferredCurrency == 'KRW') {
                        _foreignCurrency = 'USD';
                      }
                    }),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _storeController,
                decoration: const InputDecoration(labelText: 'Store (optional)'),
              ),
              const SizedBox(height: 16),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Date'),
                subtitle: Text('${_occurredOn.year}-${_occurredOn.month.toString().padLeft(2, '0')}-${_occurredOn.day.toString().padLeft(2, '0')}'),
                trailing: const Icon(Icons.calendar_today_outlined),
                onTap: _pickDate,
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _notesController,
                decoration: const InputDecoration(labelText: 'Notes (optional)'),
                maxLines: 2,
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Color(0xFFC1543C))),
              ],
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _isSubmitting ? null : _submit,
                  child: _isSubmitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Save Expense'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
