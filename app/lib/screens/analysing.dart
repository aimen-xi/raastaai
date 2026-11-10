import 'package:flutter/material.dart';

import '../api.dart';
import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';
import 'photo_view.dart';
import 'result.dart';

/// Step 1a: send the photo to the AI. Bad files go back home; AI failures continue to the
/// result screen in "choose it yourself" mode (judges: classification failure must not block reporting).
class AnalysingScreen extends StatefulWidget {
  const AnalysingScreen({super.key, required this.draft});
  final ReportDraft draft;

  @override
  State<AnalysingScreen> createState() => _AnalysingScreenState();
}

class _AnalysingScreenState extends State<AnalysingScreen> {
  bool _cancelled = false;
  bool _slow = false;

  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(seconds: 6), () {
      if (mounted) setState(() => _slow = true);
    });
    _run();
  }

  Future<void> _run() async {
    final d = widget.draft;
    try {
      d.ai = await Api.instance.classify(d.bytes, d.filename);
      d.category = d.ai!.outcome == 'issue' ? d.ai!.category : null; // only a confident result is pre-selected
    } on ApiException catch (e) {
      if (_cancelled || !mounted) return;
      if (const {400, 413, 415}.contains(e.status)) {
        await showApiError(context, e);
        if (mounted) Navigator.pop(context);
        return;
      }
      d.ai = null; // 429 / 503 / timeout / offline -> manual category
    }
    if (_cancelled || !mounted) return;
    Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => ResultScreen(draft: d)));
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.draft;
    final kb = d.bytes.length / 1024;
    final size = kb > 1024 ? '${(kb / 1024).toStringAsFixed(1)} MB' : '${kb.round()} KB';
    return Scaffold(
      appBar: const StepHeader(step: 1, title: 'Checking your photo'),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        PhotoWithBoxes(bytes: d.bytes, label: d.isSample ? 'Staged dataset image' : null),
        const SizedBox(height: 16),
        CardBox(
          child: Column(children: [
            _Line(done: true, text: 'Image checked · $size'),
            const _Line(text: 'Looking for potholes…'),
            const _Line(text: 'Looking for garbage…'),
          ]),
        ),
        const SizedBox(height: 12),
        InfoBanner(
          _slow
              ? 'The free AI server may be waking up — this can take up to 20 s. If it doesn’t answer, you can choose the category yourself.'
              : 'Usually 3–5 seconds.',
          bg: _slow ? C.warnBg : C.infoBg,
          fg: _slow ? C.warnFg : C.infoFg,
          icon: Icons.hourglass_top,
        ),
      ]),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: OutlineBtn('Cancel', onPressed: () {
            _cancelled = true;
            Navigator.pop(context);
          }),
        ),
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({required this.text, this.done = false});
  final String text;
  final bool done;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          SizedBox(
            width: 20,
            height: 20,
            child: done ? const Icon(Icons.check_circle, color: C.okFg, size: 20) : const CircularProgressIndicator(strokeWidth: 2.2),
          ),
          const SizedBox(width: 12),
          Text(text, style: const TextStyle(fontSize: 15)),
        ]),
      );
}
