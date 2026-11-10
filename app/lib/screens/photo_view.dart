import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../api.dart';
import '../theme.dart';

/// The citizen's photo with the AI's detections outlined (pothole = orange, garbage = blue).
class PhotoWithBoxes extends StatefulWidget {
  const PhotoWithBoxes({super.key, required this.bytes, this.boxes = const [], this.maxHeight = 300, this.label});
  final Uint8List bytes;
  final List<DetBox> boxes;
  final double maxHeight;
  final String? label;

  @override
  State<PhotoWithBoxes> createState() => _PhotoWithBoxesState();
}

class _PhotoWithBoxesState extends State<PhotoWithBoxes> {
  double? _aspect;

  @override
  void initState() {
    super.initState();
    ui.instantiateImageCodec(widget.bytes).then((codec) => codec.getNextFrame()).then((f) {
      if (mounted) setState(() => _aspect = f.image.width / f.image.height);
    }, onError: (_) {});
  }

  @override
  Widget build(BuildContext context) {
    final aspect = _aspect ?? 4 / 3;
    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: widget.maxHeight),
      child: Center(
        child: AspectRatio(
          aspectRatio: aspect,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Stack(fit: StackFit.expand, children: [
              Image.memory(widget.bytes, fit: BoxFit.fill, gaplessPlayback: true,
                  errorBuilder: (_, _, _) => const ColoredBox(color: C.greyBg, child: Icon(Icons.broken_image_outlined))),
              if (widget.boxes.isNotEmpty) CustomPaint(painter: _BoxPainter(widget.boxes)),
              if (widget.label != null)
                Positioned(
                  left: 10,
                  top: 10,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: Colors.black.withValues(alpha: .6), borderRadius: BorderRadius.circular(999)),
                    child: Text(widget.label!, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
                  ),
                ),
            ]),
          ),
        ),
      ),
    );
  }
}

class _BoxPainter extends CustomPainter {
  _BoxPainter(this.boxes);
  final List<DetBox> boxes;

  @override
  void paint(Canvas canvas, Size size) {
    for (final b in boxes.take(25)) {
      final color = b.cls == 'garbage' ? const Color(0xFF3B82F6) : const Color(0xFFF97316);
      final r = Rect.fromLTRB(b.l * size.width, b.t * size.height, b.r * size.width, b.b * size.height);
      final rr = RRect.fromRectAndRadius(r, const Radius.circular(6));
      canvas.drawRRect(rr, Paint()..color = color.withValues(alpha: .18));
      canvas.drawRRect(rr, Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5);
    }
  }

  @override
  bool shouldRepaint(_BoxPainter old) => old.boxes != boxes;
}
