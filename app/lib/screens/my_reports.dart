import 'package:flutter/material.dart';

import '../api.dart';
import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';

/// Report IDs stored on this device, with their live status (no accounts: judges cut them).
class MyReportsScreen extends StatefulWidget {
  const MyReportsScreen({super.key});

  @override
  State<MyReportsScreen> createState() => _MyReportsScreenState();
}

class _MyReportsScreenState extends State<MyReportsScreen> {
  late Future<List<String>> _ids = LocalReports.list();

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text('My reports', style: heading(18))),
        body: FutureBuilder<List<String>>(
          future: _ids,
          builder: (context, snap) {
            final ids = snap.data ?? const <String>[];
            if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (ids.isEmpty) {
              return const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text('No reports from this phone yet.', style: TextStyle(color: C.muted)),
                ),
              );
            }
            return RefreshIndicator(
              onRefresh: () async => setState(() => _ids = LocalReports.list()),
              child: ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: ids.length,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (_, i) => _ReportTile(id: ids[i]),
              ),
            );
          },
        ),
      );
}

class _ReportTile extends StatelessWidget {
  const _ReportTile({required this.id});
  final String id;

  @override
  Widget build(BuildContext context) => CardBox(
        padding: const EdgeInsets.all(14),
        child: FutureBuilder<ReportStatus>(
          future: Api.instance.status(id),
          builder: (context, snap) {
            final s = snap.data;
            return Row(children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(color: s == null ? C.border : C.cat(s.category), shape: BoxShape.circle),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(id, style: const TextStyle(fontWeight: FontWeight.w700, letterSpacing: .5)),
                  Text(
                    s == null
                        ? (snap.hasError ? 'Status unavailable (offline?)' : 'Loading…')
                        : '${categoryLabel[s.category]} · ${s.clusterReportCount} report${s.clusterReportCount == 1 ? '' : 's'} at this spot',
                    style: const TextStyle(fontSize: 13, color: C.muted),
                  ),
                ]),
              ),
              if (s != null)
                Pill(statusLabel[s.status] ?? s.status,
                    bg: s.status == 'resolved' ? C.okBg : s.status == 'in_progress' ? C.infoBg : C.warnBg,
                    fg: s.status == 'resolved' ? C.okFg : s.status == 'in_progress' ? C.infoFg : C.warnFg),
            ]);
          },
        ),
      );
}
