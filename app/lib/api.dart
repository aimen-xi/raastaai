import 'dart:async';
import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'config.dart';

/// Every failure the UI can show. `status == 0` means the server could not be reached.
class ApiException implements Exception {
  ApiException(this.status, this.code, this.message, {this.field, this.retryAfterS});
  final int status;
  final String code;
  final String message;
  final String? field;
  final int? retryAfterS;

  bool get isNetwork => status == 0;
  bool get isTimeout => code == 'timeout';
  @override
  String toString() => 'ApiException($status $code: $message)';
}

class DetBox {
  DetBox(this.cls, this.conf, this.l, this.t, this.r, this.b);
  final String cls;
  final double conf;
  final double l, t, r, b; // fractions of the image size
}

class Classification {
  Classification({required this.outcome, this.category, required this.confidence, required this.reason,
      required this.boxes, this.ticket});
  final String outcome; // issue | uncertain | not_issue
  final String? category; // pothole | garbage
  final double confidence;
  final String reason;
  final List<DetBox> boxes;
  final String? ticket;

  factory Classification.fromJson(Map<String, dynamic> j) => Classification(
        outcome: j['outcome'] as String,
        category: j['category'] as String?,
        confidence: (j['confidence'] as num).toDouble(),
        reason: j['reason'] as String,
        ticket: j['ticket'] as String?,
        boxes: [
          for (final b in (j['boxes'] as List? ?? const []))
            DetBox(b['cls'] as String, (b['conf'] as num).toDouble(), (b['box'][0] as num).toDouble(),
                (b['box'][1] as num).toDouble(), (b['box'][2] as num).toDouble(), (b['box'][3] as num).toDouble()),
        ],
      );
}

class SubmitResult {
  SubmitResult(this.json);
  final Map<String, dynamic> json;
  String get reportId => json['reportId'] as String;
  bool get merged => json['merged'] == true;
  int get clusterReportCount => (json['clusterReportCount'] as num?)?.toInt() ?? 1;
  bool get hotspot => json['hotspot'] == true;
  String get verification => json['verification'] as String? ?? 'unverified';
}

class ReportStatus {
  ReportStatus(this.json);
  final Map<String, dynamic> json;
  String get category => json['category'] as String;
  String get status => json['status'] as String;
  int get clusterReportCount => (json['clusterReportCount'] as num?)?.toInt() ?? 1;
}

class Api {
  Api({http.Client? client, String? base, Future<String?> Function()? token})
      : _http = client ?? http.Client(),
        _fixedBase = base ?? (apiBaseOverride.isNotEmpty ? apiBaseOverride : null),
        _token = token ?? _firebaseToken;
  final http.Client _http;
  final String? _fixedBase;
  final Future<String?> Function() _token;
  String? _resolved;

  static final instance = Api();

  /// The API address: pinned at build time, or read from the public config doc (cached until a
  /// network error, so a restarted tunnel is picked up on the next try).
  Future<String> _baseUrl() async {
    if (_fixedBase != null) return _fixedBase;
    if (_resolved != null) return _resolved!;
    try {
      final r = await _http.get(Uri.parse(publicConfigUrl)).timeout(const Duration(seconds: 8));
      final v = (jsonDecode(r.body) as Map<String, dynamic>)['fields']?['apiBase']?['stringValue'] as String?;
      if (r.statusCode == 200 && v != null && v.startsWith('http')) return _resolved = v.replaceAll(RegExp(r'/+$'), '');
    } catch (_) {}
    return apiBaseFallback;
  }

  Future<Uri> _u(String path) async => Uri.parse('${await _baseUrl()}$path');

  static Future<String?> _firebaseToken() async {
    final auth = FirebaseAuth.instance;
    final user = auth.currentUser ?? (await auth.signInAnonymously()).user!;
    return user.getIdToken();
  }

  Future<Map<String, String>> _auth() async {
    try {
      return {'Authorization': 'Bearer ${await _token()}'};
    } catch (_) {
      throw ApiException(0, 'network', 'Could not sign in anonymously. Check your connection.');
    }
  }

  /// Resolves the API address and warms the server up while the user frames the photo.
  Future<void> wake() async {
    try {
      await _http.get(await _u('/health')).timeout(const Duration(seconds: 30));
    } catch (_) {}
  }

  Future<Classification> classify(Uint8List bytes, String filename, {Duration timeout = const Duration(seconds: 20)}) async {
    final req = http.MultipartRequest('POST', await _u('/classify'))
      ..headers.addAll(await _auth())
      ..files.add(http.MultipartFile.fromBytes('image', bytes, filename: filename, contentType: _type(filename)));
    return Classification.fromJson(await _send(req, timeout));
  }

  Future<SubmitResult> submit({
    required Uint8List bytes,
    required String filename,
    required String category,
    required double lat,
    required double lng,
    double? accuracyM,
    required String locationSource,
    String note = '',
    String? ticket,
  }) async {
    final req = http.MultipartRequest('POST', await _u('/reports'))
      ..headers.addAll(await _auth())
      ..fields.addAll({
        'category': category,
        'lat': lat.toStringAsFixed(6),
        'lng': lng.toStringAsFixed(6),
        'locationSource': locationSource,
        if (accuracyM != null) 'accuracyM': accuracyM.toStringAsFixed(1),
        if (note.trim().isNotEmpty) 'note': note.trim(),
        'aiTicket': ?ticket,
      })
      ..files.add(http.MultipartFile.fromBytes('image', bytes, filename: filename, contentType: _type(filename)));
    return SubmitResult(await _send(req, const Duration(seconds: 30)));
  }

  Future<ReportStatus> status(String id) async {
    try {
      final r = await _http.get(await _u('/reports/${Uri.encodeComponent(id)}')).timeout(const Duration(seconds: 20));
      return ReportStatus(_decode(r.statusCode, r.body, r.headers));
    } on ApiException {
      rethrow;
    } catch (e) {
      throw _network(e);
    }
  }

  Future<Map<String, dynamic>> _send(http.MultipartRequest req, Duration timeout) async {
    try {
      final streamed = await _http.send(req).timeout(timeout);
      final r = await http.Response.fromStream(streamed).timeout(timeout);
      return _decode(r.statusCode, r.body, r.headers);
    } on ApiException {
      rethrow;
    } catch (e) {
      throw _network(e);
    }
  }

  ApiException _network(Object e) {
    _resolved = null; // the tunnel may have restarted with a new address: re-read config next time
    return e is TimeoutException
        ? ApiException(0, 'timeout', 'The server took too long to answer.')
        : ApiException(0, 'network', 'Could not reach the RaastaAI server.');
  }

  Map<String, dynamic> _decode(int code, String body, Map<String, String> headers) {
    Map<String, dynamic>? j;
    try {
      j = jsonDecode(body) as Map<String, dynamic>;
    } catch (_) {}
    if (code >= 200 && code < 300 && j != null) return j;
    throw ApiException(code, j?['error'] as String? ?? 'http_$code', j?['message'] as String? ?? 'Something went wrong ($code).',
        field: j?['field'] as String?, retryAfterS: int.tryParse(headers['retry-after'] ?? ''));
  }

  static MediaType _type(String name) {
    final n = name.toLowerCase();
    if (n.endsWith('.png')) return MediaType('image', 'png');
    if (n.endsWith('.webp')) return MediaType('image', 'webp');
    return MediaType('image', 'jpeg');
  }
}
