import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';
import 'my_reports.dart';

class ReceiptScreen extends StatelessWidget {
  const ReceiptScreen({super.key, required this.draft, required this.result});
  final ReportDraft draft;
  final SubmitResult result;

  @override
  Widget build(BuildContext context) {
    final cat = draft.category!;
    final others = result.clusterReportCount - 1;
    return Scaffold(
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.fromLTRB(20, 32, 20, 20), children: [
          const CircleAvatar(radius: 32, backgroundColor: C.okBg, child: Icon(Icons.check_rounded, size: 36, color: C.okFg)),
          const SizedBox(height: 16),
          Text('Report submitted', textAlign: TextAlign.center, style: heading(26)),
          const SizedBox(height: 6),
          const Text('Thanks — a pilot admin will review it.', textAlign: TextAlign.center, style: TextStyle(fontSize: 15, color: C.body)),
          const SizedBox(height: 20),
          CardBox(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Report ID', style: TextStyle(fontSize: 13, color: C.muted)),
              Row(children: [
                SelectableText(result.reportId, style: heading(24).copyWith(letterSpacing: 1)),
                const Spacer(),
                TextButton.icon(
                  icon: const Icon(Icons.copy, size: 16),
                  label: const Text('Copy'),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: result.reportId));
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Report ID copied')));
                  },
                ),
              ]),
              const SizedBox(height: 10),
              Wrap(spacing: 8, runSpacing: 8, children: [
                Pill('● ${categoryLabel[cat]}', bg: C.cat(cat).withValues(alpha: .1), fg: C.cat(cat)),
                const Pill('Status: Pending', bg: C.warnBg, fg: C.warnFg),
                Pill(result.verification == 'verified' ? 'AI-suggested · you confirmed' : 'Chosen by you · unverified',
                    bg: result.verification == 'verified' ? C.okBg : C.greyBg, fg: result.verification == 'verified' ? C.okFg : C.body),
              ]),
            ]),
          ),
          if (result.merged) ...[
            const SizedBox(height: 12),
            InfoBanner(
              'Grouped with $others nearby report${others == 1 ? '' : 's'}. A ${cat == 'pothole' ? 'pothole' : 'garbage pile'} was already '
              'reported within 25 m in the last 7 days, so your report adds weight to that spot instead of creating a duplicate.',
              icon: Icons.layers_outlined,
            ),
          ],
          if (result.hotspot) ...[
            const SizedBox(height: 12),
            const InfoBanner('This area is now a hotspot: 3 or more reports within 50 m in the last 30 days.',
                bg: C.warnBg, fg: C.warnFg, icon: Icons.local_fire_department_outlined),
          ],
          const SizedBox(height: 12),
          const Text(
            'Your report ID is saved on this phone only. RaastaAI is a pilot concept — reports are not sent to any government authority.',
            style: TextStyle(fontSize: 13, color: C.muted, height: 1.45),
          ),
          const SizedBox(height: 24),
          PrimaryButton('Report another issue', onPressed: () => Navigator.popUntil(context, (r) => r.isFirst)),
          const SizedBox(height: 8),
          OutlineBtn('My reports on this phone',
              onPressed: () => Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const MyReportsScreen()))),
        ]),
      ),
    );
  }
}
