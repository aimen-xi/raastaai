import 'package:flutter/material.dart';

import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';
import 'analysing.dart';
import 'location.dart';
import 'photo_view.dart';

/// Step 1b: show the AI's suggestion; the citizen confirms or corrects it (AI never auto-reports).
class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key, required this.draft});
  final ReportDraft draft;

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  ReportDraft get d => widget.draft;

  @override
  void initState() {
    super.initState();
    // Blank / person / animal photos can't be reported: say why, straight away, in a dialog.
    if (d.hardRejected) WidgetsBinding.instance.addPostFrameCallback((_) => _explainRetake());
  }

  Future<void> _explainRetake() async {
    if (!mounted) return;
    final blank = d.ai?.reason == 'blank_image';
    final retake = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        icon: Icon(blank ? Icons.hide_image_outlined : Icons.no_photography_outlined, color: C.errFg, size: 36),
        title: Text(blank ? 'This photo looks blank' : 'This photo shows a person or an animal'),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(
            blank
                ? 'Our AI couldn’t see anything in it. This usually happens when the camera is covered, the photo is '
                    'very dark, or it shows a plain wall or sky.'
                : 'RaastaAI only accepts photos of the road problem itself. To protect people’s privacy, photos of '
                    'people or animals are never stored or reported.',
            style: const TextStyle(fontSize: 15, height: 1.45, color: C.body),
          ),
          const SizedBox(height: 12),
          const Text('Please retake the photo:', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          const Text('• Point the camera at the pothole or garbage\n• Stand 1–3 m away, in good light\n'
              '• Keep people and animals out of the frame', style: TextStyle(fontSize: 14, height: 1.5, color: C.body)),
          const SizedBox(height: 10),
          const Text('Nothing has been reported.', style: TextStyle(fontSize: 13, color: C.muted)),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('See the photo')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Retake photo')),
        ],
      ),
    );
    if (retake == true && mounted) Navigator.popUntil(context, (r) => r.isFirst);
  }

  ({String chip, Color bg, Color fg, String body, String prompt, String foot}) _state() {
    final ai = d.ai;
    final pct = ai == null ? '' : '${(ai.confidence * 100).round()}%';
    if (ai == null) {
      return (
        chip: 'Couldn’t analyse the photo',
        bg: C.infoBg,
        fg: C.infoFg,
        body: 'The AI service did not respond. You can still report — just choose the category yourself.',
        prompt: 'Choose the category',
        foot: 'A manual report is saved as unverified',
      );
    }
    switch (ai.outcome) {
      case 'issue':
        final what = categoryLabel[ai.category]!.toLowerCase();
        return (
          chip: 'Likely $what',
          bg: ai.category == 'garbage' ? const Color(0xFFDBEAFE) : const Color(0xFFFFEDD5),
          fg: ai.category == 'garbage' ? const Color(0xFF1E40AF) : const Color(0xFF9A3412),
          body: 'The outlined area looks like ${ai.category == 'garbage' ? 'a garbage pile' : 'a pothole'}. Is that right?',
          prompt: 'Confirm or change the category',
          foot: 'Saved as AI-suggested + confirmed by you',
        );
      case 'uncertain':
        final guess = ai.category == null ? '' : ' Best guess: ${categoryLabel[ai.category]!.toLowerCase()} ($pct).';
        return (
          chip: 'Uncertain — please choose',
          bg: C.warnBg,
          fg: C.warnFg,
          body: 'We are not sure what this shows.$guess Tell us what you see, or retake a clearer photo.',
          prompt: 'What do you see?',
          foot: 'Will be marked “unverified” for admins',
        );
      default:
        final why = switch (ai.reason) {
          'blank_image' => 'This photo looks blank.',
          'person_or_animal' => 'This photo seems to show a person or an animal, not a road problem.',
          _ => 'We couldn’t find a pothole or garbage in this photo.',
        };
        if (d.hardRejected) {
          return (
            chip: 'Not a road photo',
            bg: C.errBg,
            fg: C.errFg,
            body: '$why It can’t be reported. Please take a photo of the pothole or garbage itself.',
            prompt: '',
            foot: 'Nothing has been reported',
          );
        }
        return (
          chip: 'No road issue detected',
          bg: C.greyBg,
          fg: C.body,
          body: '$why Nothing has been reported. A clearer, closer photo usually helps.',
          prompt: 'Still see a problem? Choose it yourself',
          foot: 'You’ll need to describe the problem · sent as “AI found nothing”, lowest priority for admins',
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _state();
    final ai = d.ai;
    return Scaffold(
      appBar: const StepHeader(step: 1, title: 'Check the result'),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        PhotoWithBoxes(
          bytes: d.bytes,
          boxes: ai?.outcome == 'not_issue' ? const [] : (ai?.boxes ?? const []),
          label: d.isSample ? 'Staged dataset image' : null,
        ),
        const SizedBox(height: 14),
        Align(alignment: Alignment.centerLeft, child: Pill(s.chip, bg: s.bg, fg: s.fg)),
        const SizedBox(height: 8),
        Text(s.body, style: const TextStyle(fontSize: 15, height: 1.45, color: C.body)),
        if (ai != null && ai.outcome != 'not_issue') ...[
          const SizedBox(height: 12),
          _Confidence(ai.confidence, C.cat(ai.category)),
        ],
        if (!d.hardRejected) ...[
          const SizedBox(height: 18),
          Text(s.prompt, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
          const SizedBox(height: 8),
          CategoryPicker(value: d.category, onChanged: (c) => setState(() => d.category = c)),
        ],
        const SizedBox(height: 10),
        Text(d.category != null && d.aiAgrees ? 'Saved as AI-suggested + confirmed by you' : s.foot,
            textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: C.muted)),
      ]),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            if (d.hardRejected)
              PrimaryButton('Take a new photo', onPressed: () => Navigator.popUntil(context, (r) => r.isFirst))
            else
            PrimaryButton(
              d.category == null ? 'Choose a category to continue' : 'Confirm & set location',
              onPressed: d.category == null
                  ? null
                  : () => Navigator.push(context, MaterialPageRoute(builder: (_) => LocationScreen(draft: d))),
            ),
            const SizedBox(height: 8),
            if (d.hardRejected)
              const SizedBox.shrink()
            else if (ai == null)
              OutlineBtn('Try analysis again',
                  onPressed: () => Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => AnalysingScreen(draft: d))))
            else
              OutlineBtn('Retake photo', onPressed: () => Navigator.popUntil(context, (r) => r.isFirst)),
          ]),
        ),
      ),
    );
  }
}

class _Confidence extends StatelessWidget {
  const _Confidence(this.value, this.color);
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Text('AI confidence', style: TextStyle(fontSize: 13, color: C.muted)),
          const Spacer(),
          Text('${(value * 100).round()}%', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(value: value.clamp(0, 1), minHeight: 8, color: color, backgroundColor: C.line),
        ),
        const SizedBox(height: 6),
        const Text('AI can be wrong — please check.', style: TextStyle(fontSize: 12, color: C.muted)),
      ]);
}
