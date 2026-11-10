import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../api.dart';
import '../config.dart';
import '../flow.dart';
import '../theme.dart';
import '../widgets.dart';
import 'analysing.dart';
import 'my_reports.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _myCount = 0;
  bool _picking = false;

  @override
  void initState() {
    super.initState();
    _refreshCount();
  }

  Future<void> _refreshCount() async {
    final ids = await LocalReports.list();
    if (mounted) setState(() => _myCount = ids.length);
  }

  Future<void> _pick(ImageSource source) async {
    if (_picking) return;
    setState(() => _picking = true);
    try {
      // Resize on the device first: fast upload, and a phone's 20 MB original fits the 8 MB limit.
      final x = await ImagePicker().pickImage(source: source, maxWidth: 2560, maxHeight: 2560, imageQuality: 88);
      if (x == null) return;
      final bytes = await x.readAsBytes();
      if (!mounted) return;
      if (bytes.length > maxUploadBytes) {
        await showApiError(context, ApiException(413, 'file_too_large', 'Photo is larger than 8 MB.'));
        return;
      }
      await _start(ReportDraft(bytes: bytes, filename: x.name.isEmpty ? 'photo.jpg' : x.name));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open the camera or gallery.')));
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _sample(String name) async {
    final data = await rootBundle.load('assets/samples/$name.jpg');
    await _start(ReportDraft(bytes: data.buffer.asUint8List(), filename: '$name.jpg', isSample: true));
  }

  Future<void> _start(ReportDraft d) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => AnalysingScreen(draft: d)));
    _refreshCount();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
              child: Row(children: [
                Text.rich(TextSpan(style: heading(24), children: [
                  const TextSpan(text: 'Raasta'),
                  WidgetSpan(
                    alignment: PlaceholderAlignment.baseline,
                    baseline: TextBaseline.alphabetic,
                    child: Container(
                      margin: const EdgeInsets.only(left: 2),
                      padding: const EdgeInsets.symmetric(horizontal: 5),
                      decoration: BoxDecoration(color: C.yellow, borderRadius: BorderRadius.circular(6)),
                      child: Text('AI', style: heading(24)),
                    ),
                  ),
                ])),
                const SizedBox(width: 8),
                Text('راستہ', style: urdu(15)),
                const Spacer(),
                const Pill('Pilot concept'),
              ]),
            ),
            Expanded(
              child: ListView(padding: const EdgeInsets.fromLTRB(20, 4, 20, 20), children: [
                const _Hero(),
                const SizedBox(height: 16),
                PrimaryButton('Take photo',
                    icon: Icons.photo_camera_outlined, trailingUrdu: 'تصویر لیں', busy: _picking, onPressed: () => _pick(ImageSource.camera)),
                const SizedBox(height: 10),
                OutlineBtn('Upload from gallery', icon: Icons.image_outlined, onPressed: _picking ? null : () => _pick(ImageSource.gallery)),
                const SizedBox(height: 6),
                const Text('JPG, PNG or WebP · up to 8 MB', textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: C.muted)),
                if (demoSamples) ...[
                  const SizedBox(height: 14),
                  _Samples(onPick: _sample),
                ],
                const SizedBox(height: 16),
                const _Privacy(),
                const SizedBox(height: 12),
                const Row(children: [
                  _Tip('Fill the frame', 'One issue per photo'),
                  SizedBox(width: 8),
                  _Tip('Daylight', 'Avoid blur and glare'),
                  SizedBox(width: 8),
                  _Tip('Stand safe', 'Stay off the road'),
                ]),
              ]),
            ),
            Container(
              decoration: const BoxDecoration(border: Border(top: BorderSide(color: C.line))),
              padding: const EdgeInsets.fromLTRB(20, 10, 12, 14),
              child: Row(children: [
                const Expanded(
                  child: Text('Pilot concept · not connected to any government authority',
                      style: TextStyle(fontSize: 13, color: C.muted, height: 1.4)),
                ),
                TextButton(
                  onPressed: () async {
                    await Navigator.push(context, MaterialPageRoute(builder: (_) => const MyReportsScreen()));
                    _refreshCount();
                  },
                  child: Text('My reports ($_myCount)', style: const TextStyle(fontWeight: FontWeight.w600, color: C.garbage)),
                ),
              ]),
            ),
          ]),
        ),
      );
}

class _Hero extends StatelessWidget {
  const _Hero();

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(color: C.asphalt, borderRadius: BorderRadius.circular(20)),
        clipBehavior: Clip.antiAlias,
        child: Stack(children: [
          Positioned(
            right: 34,
            top: -6,
            bottom: -6,
            child: Column(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
              for (var i = 0; i < 3; i++)
                Container(width: 14, height: 30, decoration: BoxDecoration(color: C.yellow, borderRadius: BorderRadius.circular(2))),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(22, 22, 90, 22),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Spotted a pothole or a garbage pile?', style: heading(25).copyWith(color: Colors.white, height: 1.15)),
              const SizedBox(height: 8),
              const Text('Take one photo. Our AI suggests what it sees — you decide what gets reported.',
                  style: TextStyle(color: C.border, fontSize: 15, height: 1.5)),
            ]),
          ),
        ]),
      );
}

class _Samples extends StatelessWidget {
  const _Samples({required this.onPick});
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) => CardBox(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Demo: try a staged dataset photo', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          const SizedBox(height: 8),
          Row(children: [
            for (final (key, label) in const [('pothole', 'Pothole'), ('garbage', 'Garbage'), ('road', 'Clean road')]) ...[
              Expanded(
                child: InkWell(
                  borderRadius: BorderRadius.circular(10),
                  onTap: () => onPick(key),
                  child: Column(children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: AspectRatio(aspectRatio: 1, child: Image.asset('assets/samples/$key.jpg', fit: BoxFit.cover)),
                    ),
                    const SizedBox(height: 4),
                    Text(label, style: const TextStyle(fontSize: 12, color: C.body)),
                  ]),
                ),
              ),
              if (key != 'road') const SizedBox(width: 8),
            ],
          ]),
        ]),
      );
}

class _Privacy extends StatelessWidget {
  const _Privacy();

  @override
  Widget build(BuildContext context) => const CardBox(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(Icons.shield_outlined, size: 20, color: C.garbage),
            SizedBox(width: 8),
            Text('Your privacy', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
          ]),
          SizedBox(height: 10),
          _Bullet('No account needed — reporting is anonymous.'),
          _Bullet('Hidden location data (EXIF) is removed from your photo before it is stored.'),
          _Bullet('Please don’t photograph people’s faces or number plates.'),
        ]),
      );
}

class _Bullet extends StatelessWidget {
  const _Bullet(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('•  ', style: TextStyle(color: C.body)),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 14, height: 1.45, color: C.body))),
        ]),
      );
}

class _Tip extends StatelessWidget {
  const _Tip(this.title, this.body);
  final String title, body;

  @override
  Widget build(BuildContext context) => Expanded(
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(color: Colors.white, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
            Text(body, style: const TextStyle(fontSize: 12, color: C.body, height: 1.4)),
          ]),
        ),
      );
}
