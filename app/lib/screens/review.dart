import 'package:flutter/material.dart';

import '../api.dart';
import '../config.dart';
import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';
import 'receipt.dart';

/// Step 3: review, optional note, submit. Errors keep everything on screen (nothing is lost).
class ReviewScreen extends StatefulWidget {
  const ReviewScreen({super.key, required this.draft});
  final ReportDraft draft;

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  late final _note = TextEditingController(text: widget.draft.note);
  bool _busy = false;

  ReportDraft get d => widget.draft;

  bool get _noteOk => !d.noteRequired || _note.text.trim().length >= overrideNoteMinChars;

  Future<void> _submit() async {
    if (!_noteOk) return;
    setState(() => _busy = true);
    d.note = _note.text;
    try {
      final r = await Api.instance.submit(
        bytes: d.bytes,
        filename: d.filename,
        category: d.category!,
        lat: d.point!.latitude,
        lng: d.point!.longitude,
        accuracyM: d.accuracyM,
        locationSource: d.locationSource,
        note: d.note,
        ticket: d.ai?.ticket,
      );
      await LocalReports.add(r.reportId);
      if (!mounted) return;
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(builder: (_) => ReceiptScreen(draft: d, result: r)),
        (route) => route.isFirst,
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        if (e.code == 'note_required') d.serverNeedsNote = true; // server's AI check found nothing
      });
      final again = await showApiError(context, e, retryLabel: 'Try again');
      if (!mounted) return;
      if (e.status == 409 || e.status == 422) {
        Navigator.popUntil(context, (r) => r.isFirst); // duplicate / reused / not a road photo: start over
      } else if (again == true && e.isNetwork) {
        _submit();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final ai = d.ai;
    final aiLine = ai == null
        ? 'AI unavailable · chosen by you'
        : d.aiAgrees
            ? 'AI: likely ${d.category} (${(ai.confidence * 100).round()}%) · you confirmed'
            : ai.outcome == 'issue'
                ? 'AI suggested ${ai.category} · you changed it'
                : ai.outcome == 'not_issue'
                    ? 'Chosen by you · AI found no issue'
                    : 'Chosen by you · AI was not sure';
    final p = d.point!;
    return Scaffold(
      appBar: const StepHeader(step: 3, title: 'Review your report'),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        CardBox(
          padding: EdgeInsets.zero,
          child: Column(children: [
            _Row(
              leading: ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Image.memory(d.bytes, width: 72, height: 72, fit: BoxFit.cover),
              ),
              label: 'Category',
              title: Row(children: [
                Container(width: 12, height: 12, decoration: BoxDecoration(color: C.cat(d.category), shape: BoxShape.circle)),
                const SizedBox(width: 8),
                Text(categoryLabel[d.category]!, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                const SizedBox(width: 8),
                Text(categoryUrdu[d.category]!, style: urdu(12)),
              ]),
              sub: aiLine,
              onEdit: () => Navigator.of(context)
                ..pop()
                ..pop(),
            ),
            const Divider(height: 1, color: Color(0xFFF0F1F3)),
            _Row(
              leading: Container(
                width: 72,
                height: 48,
                decoration: BoxDecoration(color: const Color(0xFFECEAE3), borderRadius: BorderRadius.circular(10)),
                child: const Icon(Icons.location_on_outlined),
              ),
              label: d.locationSource == 'gps' ? 'Location · GPS ±${d.accuracyM?.round()} m' : 'Location · pin placed by you',
              title: Text('${p.latitude.toStringAsFixed(5)}, ${p.longitude.toStringAsFixed(5)}',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, fontFeatures: [FontFeature.tabularFigures()])),
              onEdit: () => Navigator.pop(context),
            ),
          ]),
        ),
        const SizedBox(height: 16),
        if (d.noteRequired) ...[
          const InfoBanner(
            'Our AI didn’t find a pothole or garbage in this photo. You can still report it — '
            'describe what’s wrong so the admins can check. It will be marked “AI found nothing”.',
            icon: Icons.info_outline,
          ),
          const SizedBox(height: 10),
        ],
        Text.rich(TextSpan(children: [
          TextSpan(text: d.noteRequired ? 'Describe the problem ' : 'Add a note ', style: const TextStyle(fontWeight: FontWeight.w600)),
          TextSpan(
              text: d.noteRequired ? '(required, at least $overrideNoteMinChars characters)' : '(optional)',
              style: const TextStyle(color: C.muted)),
        ])),
        const SizedBox(height: 6),
        TextField(
          controller: _note,
          maxLines: 3,
          maxLength: noteMaxChars,
          onChanged: (v) => setState(() => d.note = v),
          decoration: InputDecoration(
            errorText: d.noteRequired && _note.text.trim().isNotEmpty && !_noteOk
                ? '${overrideNoteMinChars - _note.text.trim().length} more characters needed'
                : null,
            hintText: 'e.g. Left lane, about 1 m wide, near the bus stop',
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        const SizedBox(height: 4),
        const InfoBanner(
          'Before storing, we remove hidden data (EXIF, GPS tags, device info) from your photo. Only the pin above is saved.',
          icon: Icons.shield_outlined,
        ),
      ]),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            PrimaryButton('Submit report', trailingUrdu: 'جمع کرائیں', busy: _busy, onPressed: _noteOk ? _submit : null),
            const SizedBox(height: 8),
            const Text('Anonymous · reviewed by RaastaAI pilot admins', style: TextStyle(fontSize: 12, color: C.muted)),
          ]),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.leading, required this.label, required this.title, this.sub, required this.onEdit});
  final Widget leading;
  final String label;
  final Widget title;
  final String? sub;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          leading,
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(label, style: const TextStyle(fontSize: 13, color: C.muted)),
              const SizedBox(height: 2),
              title,
              if (sub != null) ...[const SizedBox(height: 2), Text(sub!, style: const TextStyle(fontSize: 13, color: C.body))],
            ]),
          ),
          TextButton(onPressed: onEdit, child: const Text('Edit', style: TextStyle(fontWeight: FontWeight.w600, color: C.garbage))),
        ]),
      );
}
