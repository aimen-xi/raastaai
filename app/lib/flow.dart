import 'package:flutter/foundation.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

/// One report being prepared: photo -> AI suggestion -> category -> pin -> note -> submit.
class ReportDraft {
  ReportDraft({required this.bytes, required this.filename, this.isSample = false});
  final Uint8List bytes; // exactly what was analysed (the AI ticket is bound to these bytes)
  final String filename;
  final bool isSample;

  Classification? ai; // null = analysis failed / skipped
  String? category; // what the CITIZEN chose
  LatLng? point;
  double? accuracyM;
  String locationSource = 'manual_pin'; // gps | manual_pin
  String note = '';

  bool serverNeedsNote = false; // the server's own AI check found nothing (phone couldn't reach the AI)

  bool get aiAgrees => ai != null && ai!.outcome == 'issue' && ai!.category == category;

  /// Blank photo, or a photo of a person/animal: cannot be reported at all (retake only).
  bool get hardRejected =>
      ai != null && ai!.outcome == 'not_issue' && (ai!.reason == 'blank_image' || ai!.reason == 'person_or_animal');

  /// "AI found nothing, report anyway": allowed, but only with a short description (anti-spam).
  bool get noteRequired => serverNeedsNote || (ai != null && ai!.outcome == 'not_issue');
}

/// Report IDs submitted from this device (anonymous: there is no account to list them from).
class LocalReports {
  static const _key = 'raasta.reports.v1';

  static Future<List<String>> list() async {
    try {
      final p = await SharedPreferences.getInstance();
      return p.getStringList(_key) ?? <String>[];
    } catch (_) {
      return <String>[];
    }
  }

  static Future<void> add(String id) async {
    try {
      final p = await SharedPreferences.getInstance();
      final ids = p.getStringList(_key) ?? <String>[];
      if (!ids.contains(id)) await p.setStringList(_key, [id, ...ids].take(50).toList());
    } catch (_) {}
  }
}

const categoryLabel = {'pothole': 'Pothole', 'garbage': 'Garbage'};
const categoryUrdu = {'pothole': 'گڑھا', 'garbage': 'کچرا'};
const statusLabel = {'pending': 'Pending', 'in_progress': 'In progress', 'resolved': 'Resolved'};
