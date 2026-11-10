import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../config.dart';
import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';
import 'review.dart';

enum _Fix { locating, good, poor, denied, unavailable }

/// Step 2: where is it? GPS if allowed, always adjustable: the pin stays in the centre and the
/// citizen drags the map under it. Denied permission falls back to a manual pin (judge check).
class LocationScreen extends StatefulWidget {
  const LocationScreen({super.key, required this.draft});
  final ReportDraft draft;

  @override
  State<LocationScreen> createState() => _LocationScreenState();
}

class _LocationScreenState extends State<LocationScreen> {
  final _map = MapController();
  final _search = TextEditingController();
  _Fix _fix = _Fix.locating;
  LatLng _center = defaultCenter;
  double? _gpsAccuracy;
  LatLng? _gpsFix;
  bool _movedByUser = false;
  bool _searching = false;

  ReportDraft get d => widget.draft;

  @override
  void initState() {
    super.initState();
    if (d.point != null) {
      // coming back from Review: keep what the user chose
      _center = d.point!;
      _gpsAccuracy = d.accuracyM;
      if (d.locationSource == 'gps') _gpsFix = d.point;
      _movedByUser = d.locationSource == 'manual_pin';
      _fix = d.locationSource == 'gps' ? ((_gpsAccuracy ?? 999) <= goodAccuracyM ? _Fix.good : _Fix.poor) : _Fix.denied;
    } else {
      _locate();
    }
  }

  Future<void> _locate() async {
    setState(() => _fix = _Fix.locating);
    try {
      if (!await Geolocator.isLocationServiceEnabled()) throw const _NoGps(_Fix.unavailable);
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
      if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) throw const _NoGps(_Fix.denied);
      // Indoors a fresh high-accuracy fix can take a while: wait up to 30 s, then fall back to the
      // phone's last known position (Android/iOS only) instead of leaving the pin at the default city.
      Position? got;
      try {
        got = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 30)),
        );
      } on TimeoutException {
        if (!kIsWeb) got = await Geolocator.getLastKnownPosition();
      }
      final pos = got ?? (throw const _NoGps(_Fix.unavailable));
      final p = LatLng(pos.latitude, pos.longitude);
      if (!_valid(p)) throw const _NoGps(_Fix.unavailable);
      if (!mounted) return;
      setState(() {
        _center = p;
        _gpsFix = p;
        _gpsAccuracy = pos.accuracy;
        _movedByUser = false;
        _fix = pos.accuracy <= goodAccuracyM ? _Fix.good : _Fix.poor;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _map.move(p, pos.accuracy <= goodAccuracyM ? 18 : 16);
      });
    } on _NoGps catch (e) {
      if (mounted) setState(() => _fix = e.fix);
    } catch (_) {
      // permission dialog dismissed, timeout, browser blocked it...
      if (mounted) setState(() => _fix = _Fix.denied);
    }
  }

  bool _valid(LatLng p) =>
      p.latitude.isFinite && p.longitude.isFinite && p.latitude.abs() <= 90 && p.longitude.abs() <= 180 &&
      !(p.latitude == 0 && p.longitude == 0);

  Future<void> _doSearch() async {
    final q = _search.text.trim();
    if (q.isEmpty) return;
    setState(() => _searching = true);
    try {
      // OpenStreetMap Nominatim (free; light, user-initiated use only, per its usage policy)
      final uri = Uri.https('nominatim.openstreetmap.org', '/search', {'q': q, 'format': 'jsonv2', 'limit': '1', 'countrycodes': 'pk'});
      final r = await http.get(uri, headers: {'Accept-Language': 'en'}).timeout(const Duration(seconds: 10));
      final list = jsonDecode(r.body) as List;
      if (list.isEmpty) throw Exception('not found');
      final p = LatLng(double.parse(list.first['lat'] as String), double.parse(list.first['lon'] as String));
      _map.move(p, 17);
      setState(() {
        _center = p;
        _movedByUser = true;
      });
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Place not found. Try a nearby landmark or drag the map.')));
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  void _confirm() {
    if (!_valid(_center)) return;
    final usedGps = !_movedByUser && (_fix == _Fix.good || _fix == _Fix.poor);
    d.point = _center;
    d.locationSource = usedGps ? 'gps' : 'manual_pin';
    d.accuracyM = usedGps ? _gpsAccuracy : null;
    Navigator.push(context, MaterialPageRoute(builder: (_) => ReviewScreen(draft: d)));
  }

  @override
  Widget build(BuildContext context) {
    final acc = _gpsAccuracy?.round();
    final (banner, bg, fg) = switch (_fix) {
      _Fix.locating => ('Finding your location…', C.infoBg, C.infoFg),
      _Fix.good => ('We found your location. Check the pin is on the problem.', C.infoBg, C.infoFg),
      _Fix.poor => ('Location is approximate (±$acc m). Please drag the map so the pin sits on the exact spot.', C.warnBg, C.warnFg),
      _Fix.denied => ('Location access is off — that’s okay. Search or drag the map to place the pin yourself.', C.greyBg, C.body),
      _Fix.unavailable => ('Couldn’t get a GPS fix. Search or drag the map to place the pin yourself.', C.greyBg, C.body),
    };
    final (chip, cbg, cfg) = _movedByUser || _fix == _Fix.denied || _fix == _Fix.unavailable
        ? ('Manual pin', C.greyBg, C.body)
        : _fix == _Fix.good
            ? ('GPS · ±$acc m', C.infoBg, C.infoFg)
            : _fix == _Fix.poor
                ? ('GPS · ±$acc m · adjust pin', C.warnBg, C.warnFg)
                : ('Locating…', C.greyBg, C.body);
    final showSearch = _fix == _Fix.denied || _fix == _Fix.unavailable || _fix == _Fix.poor;

    return Scaffold(
      appBar: const StepHeader(step: 2, title: 'Where is it?'),
      body: Column(children: [
        Padding(padding: const EdgeInsets.fromLTRB(16, 4, 16, 8), child: InfoBanner(banner, bg: bg, fg: fg, icon: Icons.my_location)),
        if (showSearch)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: TextField(
              controller: _search,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _doSearch(),
              decoration: InputDecoration(
                hintText: 'Search area or landmark',
                filled: true,
                fillColor: Colors.white,
                isDense: true,
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searching
                    ? const Padding(padding: EdgeInsets.all(12), child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)))
                    : IconButton(icon: const Icon(Icons.arrow_forward), onPressed: _doSearch, tooltip: 'Search'),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: C.border)),
              ),
            ),
          ),
        Expanded(
          child: Stack(children: [
            FlutterMap(
              mapController: _map,
              options: MapOptions(
                initialCenter: _center,
                initialZoom: d.point != null ? 18 : 13,
                minZoom: 4,
                maxZoom: 19,
                onPositionChanged: (camera, hasGesture) {
                  setState(() {
                    _center = camera.center;
                    if (hasGesture) _movedByUser = true;
                  });
                },
              ),
              children: [
                TileLayer(
                  // Esri World Street Map: free, no API key, Google-like street style.
                  // (CARTO now needs a key; OpenStreetMap's own servers block app traffic.)
                  urlTemplate: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
                  fallbackUrl: 'https://tile.openstreetmap.de/{z}/{x}/{y}.png',
                  maxNativeZoom: 19,
                  userAgentPackageName: 'pk.raasta.raasta_app',
                ),
                if (_gpsAccuracy != null && _gpsFix != null && (_fix == _Fix.good || _fix == _Fix.poor))
                  CircleLayer(circles: [
                    CircleMarker(
                      point: _gpsFix!,
                      radius: _gpsAccuracy!,
                      useRadiusInMeter: true,
                      color: C.garbage.withValues(alpha: .12),
                      borderColor: C.garbage.withValues(alpha: .5),
                      borderStrokeWidth: 1.5,
                    ),
                  ]),
                const SimpleAttributionWidget(source: Text('Esri, HERE, Garmin, OpenStreetMap contributors')),
              ],
            ),
            IgnorePointer(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 40), // pin tip sits on the exact centre
                  child: Icon(Icons.location_on, size: 44, color: C.cat(d.category), shadows: const [Shadow(blurRadius: 6, color: Colors.black38)]),
                ),
              ),
            ),
            Positioned(
              right: 12,
              top: 12,
              child: FloatingActionButton.small(
                heroTag: 'gps',
                tooltip: 'Use my location',
                backgroundColor: Colors.white,
                onPressed: _locate,
                child: const Icon(Icons.gps_fixed, color: C.asphalt),
              ),
            ),
          ]),
        ),
        Container(
          color: Colors.white,
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          child: SafeArea(
            top: false,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Row(children: [
                Pill(chip, bg: cbg, fg: cfg),
                const Spacer(),
                Text('${_center.latitude.toStringAsFixed(5)}, ${_center.longitude.toStringAsFixed(5)}',
                    style: const TextStyle(fontSize: 13, fontFeatures: [FontFeature.tabularFigures()], color: C.body)),
              ]),
              const SizedBox(height: 6),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text('Drag the map to put the pin exactly on the problem.', style: TextStyle(fontSize: 12, color: C.muted)),
              ),
              if (_fix == _Fix.denied)
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text('To use GPS, allow location for this site in your browser or phone settings.',
                      style: TextStyle(fontSize: 12, color: C.muted)),
                ),
              const SizedBox(height: 10),
              PrimaryButton('Use this location', onPressed: _confirm),
            ]),
          ),
        ),
      ]),
    );
  }

}

class _NoGps implements Exception {
  const _NoGps(this.fix);
  final _Fix fix;
}
