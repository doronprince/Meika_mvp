import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/zen_theme.dart';
import '../data/models/chat_message.dart';
import '../providers/chat_providers.dart';
import '../widgets/bounded_content.dart';
import '../widgets/enso_mark.dart';

class CopilotScreen extends ConsumerStatefulWidget {
  const CopilotScreen({super.key});

  @override
  ConsumerState<CopilotScreen> createState() => _CopilotScreenState();
}

class _CopilotScreenState extends ConsumerState<CopilotScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  void _send() {
    final text = _controller.text;
    if (text.trim().isEmpty) return;
    ref.read(chatControllerProvider.notifier).sendMessage(text);
    _controller.clear();
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatControllerProvider);
    ref.listen(chatControllerProvider, (previous, next) {
      if (previous == null || next.messages.length != previous.messages.length) {
        _scrollToBottom();
      }
    });

    return BoundedContent(
      child: Column(
        children: [
          if (state.error != null)
            Container(
              width: double.infinity,
              color: const Color(0xFFFBEAE6),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                state.error!,
                style: const TextStyle(color: Color(0xFFC1543C), fontSize: 13),
              ),
            ),
          Expanded(
            child: state.isLoadingHistory
                ? const Center(child: CircularProgressIndicator(color: ZenColors.matcha))
                : state.messages.isEmpty
                    ? _EmptyState(onSuggestionTap: (text) {
                        _controller.text = text;
                        _send();
                      })
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                        itemCount: state.messages.length + (state.isWaitingForReply ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index >= state.messages.length) {
                            return const _ThinkingBubble();
                          }
                          return _MessageBubble(message: state.messages[index]);
                        },
                      ),
          ),
          _Composer(controller: _controller, onSend: _send),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final ValueChanged<String> onSuggestionTap;

  const _EmptyState({required this.onSuggestionTap});

  static const _suggestions = [
    'How is my budget doing this month?',
    'How much does Rice cost?',
    'Is my spending on track?',
  ];

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const EnsoMark(size: 48),
            const SizedBox(height: 16),
            Text(
              'Ask the Wise Guide',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Text(
              'Every answer is grounded in your real numbers — never a bare directive.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
            ),
            const SizedBox(height: 20),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _suggestions
                  .map((s) => ActionChip(
                        label: Text(s),
                        backgroundColor: ZenColors.matchaLight,
                        onPressed: () => onSuggestionTap(s),
                      ))
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _ThinkingBubble extends StatelessWidget {
  const _ThinkingBubble();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: ZenColors.cardBg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: ZenColors.sandBorder),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(strokeWidth: 2, color: ZenColors.matcha),
            ),
            const SizedBox(width: 8),
            Text('The Wise Guide is thinking…', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;

  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == ChatRole.user;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: isUser ? ZenColors.matcha : ZenColors.cardBg,
            borderRadius: BorderRadius.circular(14),
            border: isUser ? null : Border.all(color: ZenColors.sandBorder),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                message.content,
                style: TextStyle(color: isUser ? Colors.white : ZenColors.sumi),
              ),
              if (message.xaiFactors.isNotEmpty) ...[
                const SizedBox(height: 8),
                _WhyPanel(factors: message.xaiFactors),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _WhyPanel extends StatefulWidget {
  final List<XaiFactor> factors;

  const _WhyPanel({required this.factors});

  @override
  State<_WhyPanel> createState() => _WhyPanelState();
}

class _WhyPanelState extends State<_WhyPanel> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lightbulb_outline_rounded, size: 14, color: ZenColors.matchaDark),
              const SizedBox(width: 4),
              Text(
                _expanded ? 'Hide the numbers' : 'Why?',
                style: const TextStyle(color: ZenColors.matchaDark, fontWeight: FontWeight.w600, fontSize: 12),
              ),
            ],
          ),
        ),
        if (_expanded)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: widget.factors
                  .map((f) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(
                          '${f.label} — ${f.detail}',
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65)),
                        ),
                      ))
                  .toList(),
            ),
          ),
      ],
    );
  }
}

class _Composer extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onSend;

  const _Composer({required this.controller, required this.onSend});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: ZenColors.sandBorder)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => onSend(),
              decoration: InputDecoration(
                hintText: 'Ask about your budget or a price…',
                filled: true,
                fillColor: ZenColors.washi,
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: ZenColors.sandBorder),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            onPressed: onSend,
            icon: const Icon(Icons.arrow_upward_rounded),
            style: IconButton.styleFrom(backgroundColor: ZenColors.matcha, foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }
}
