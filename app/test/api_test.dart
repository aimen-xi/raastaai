import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:raasta_app/api.dart';

Api apiWith(Future<http.Response> Function(http.Request r) handler) =>
    Api(client: MockClient(handler), base: 'http://api.test', token: () async => 'tok');

final img = Uint8List.fromList([0xff, 0xd8, 0xff, 0x00]);

void main() {
  test('classify parses the suggestion, boxes and ticket, and sends the token', () async {
    final api = apiWith((r) async {
      expect(r.url.path, '/classify');
      expect(r.headers['Authorization'], 'Bearer tok');
      return http.Response(
          jsonEncode({
            'outcome': 'issue', 'category': 'pothole', 'confidence': 0.82, 'reason': 'pothole_detected',
            'scores': {}, 'boxes': [{'cls': 'pothole', 'conf': 0.8, 'box': [0.1, 0.2, 0.5, 0.6]}], 'ticket': 'abc.def',
          }),
          200);
    });
    final c = await api.classify(img, 'p.jpg');
    expect(c.outcome, 'issue');
    expect(c.category, 'pothole');
    expect(c.boxes.single.r, 0.5);
    expect(c.ticket, 'abc.def');
  });

  test('server errors become ApiException with code, field and Retry-After', () async {
    final api = apiWith((r) async => http.Response(
        jsonEncode({'error': 'rate_limited', 'message': 'Too many', 'field': null}), 429,
        headers: {'retry-after': '420'}));
    await expectLater(
      api.submit(bytes: img, filename: 'p.jpg', category: 'pothole', lat: 31.5, lng: 74.3, locationSource: 'gps'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 429).having((e) => e.retryAfterS, 'retry', 420)),
    );
  });

  test('a non-JSON error page still maps to a clean ApiException', () async {
    final api = apiWith((r) async => http.Response('<html>502 Bad Gateway</html>', 502));
    await expectLater(api.status('RA-X'), throwsA(isA<ApiException>().having((e) => e.code, 'code', 'http_502')));
  });

  test('offline maps to a network error (status 0)', () async {
    final api = apiWith((r) async => throw http.ClientException('offline'));
    await expectLater(api.classify(img, 'p.jpg'), throwsA(isA<ApiException>().having((e) => e.isNetwork, 'network', true)));
  });

  test('manual pin submit omits accuracy and ticket; note is trimmed', () async {
    late String body;
    final api = apiWith((r) async {
      body = latin1.decode(r.bodyBytes); // multipart with binary photo bytes
      return http.Response(jsonEncode({'reportId': 'RA-ABCDEF', 'merged': true, 'clusterReportCount': 3, 'verification': 'unverified'}), 201);
    });
    final res = await api.submit(
        bytes: img, filename: 'p.jpg', category: 'garbage', lat: 31.52, lng: 74.35, locationSource: 'manual_pin', note: '  near gate  ');
    expect(res.reportId, 'RA-ABCDEF');
    expect(res.merged, isTrue);
    expect(res.clusterReportCount, 3);
    expect(body, contains('name="locationSource"\r\n\r\nmanual_pin'));
    expect(body, contains('name="note"\r\n\r\nnear gate\r\n'));
    expect(body, isNot(contains('accuracyM')));
    expect(body, isNot(contains('aiTicket')));
  });
}
