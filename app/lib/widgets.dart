import 'package:flutter/material.dart';

import 'api.dart';
import 'flow.dart';
import 'theme.dart';

class PrimaryButton extends StatelessWidget {
  const PrimaryButton(this.label, {super.key, this.onPressed, this.icon, this.trailingUrdu, this.busy = false});
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final String? trailingUrdu;
  final bool busy;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 56,
        width: double.infinity,
        child: FilledButton(
          style: FilledButton.styleFrom(
            backgroundColor: C.yellow,
            foregroundColor: C.asphalt,
            disabledBackgroundColor: C.greyBg,
            disabledForegroundColor: C.muted,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          onPressed: busy ? null : onPressed,
          child: busy
              ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
              : Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  if (icon != null) ...[Icon(icon, size: 20), const SizedBox(width: 10)],
                  Flexible(child: Text(label, overflow: TextOverflow.ellipsis)),
                  if (trailingUrdu != null) Text('  · $trailingUrdu', style: urdu(13, color: C.asphalt)),
                ]),
        ),
      );
}

class OutlineBtn extends StatelessWidget {
  const OutlineBtn(this.label, {super.key, this.onPressed, this.icon});
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 52,
        width: double.infinity,
        child: OutlinedButton(
          style: OutlinedButton.styleFrom(
            backgroundColor: Colors.white,
            foregroundColor: C.asphalt,
            side: const BorderSide(color: C.border, width: 1.5),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          onPressed: onPressed,
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            if (icon != null) ...[Icon(icon, size: 20), const SizedBox(width: 10)],
            Text(label),
          ]),
        ),
      );
}

class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.bg = C.greyBg, this.fg = C.body, this.icon});
  final String text;
  final Color bg, fg;
  final IconData? icon;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 14, color: fg), const SizedBox(width: 5)],
          Text(text, style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600)),
        ]),
      );
}

class InfoBanner extends StatelessWidget {
  const InfoBanner(this.text, {super.key, this.bg = C.infoBg, this.fg = C.infoFg, this.icon = Icons.info_outline});
  final String text;
  final Color bg, fg;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 18, color: fg),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(color: fg, fontSize: 13, height: 1.45))),
        ]),
      );
}

class CardBox extends StatelessWidget {
  const CardBox({super.key, required this.child, this.padding = const EdgeInsets.all(16)});
  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: padding,
        decoration: BoxDecoration(color: Colors.white, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(16)),
        child: child,
      );
}

/// Step header used on the 3-step report flow.
class StepHeader extends StatelessWidget implements PreferredSizeWidget {
  const StepHeader({super.key, required this.step, required this.title, this.onBack});
  final int step;
  final String title;
  final VoidCallback? onBack;

  @override
  Size get preferredSize => const Size.fromHeight(68);

  @override
  Widget build(BuildContext context) => AppBar(
        toolbarHeight: 68,
        leading: IconButton(tooltip: 'Back', icon: const Icon(Icons.arrow_back), onPressed: onBack ?? () => Navigator.maybePop(context)),
        titleSpacing: 0,
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('STEP $step OF 3', style: const TextStyle(fontSize: 12, color: C.muted, fontWeight: FontWeight.w600, letterSpacing: .4)),
          Text(title, style: heading(18)),
        ]),
      );
}

/// Pothole / Garbage segmented choice (the citizen always confirms or corrects the AI).
class CategoryPicker extends StatelessWidget {
  const CategoryPicker({super.key, required this.value, required this.onChanged});
  final String? value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => Row(children: [
        for (final c in const ['pothole', 'garbage']) ...[
          Expanded(
            child: Semantics(
              selected: value == c,
              button: true,
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: () => onChanged(c),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  height: 64,
                  decoration: BoxDecoration(
                    color: value == c ? C.cat(c).withValues(alpha: .08) : Colors.white,
                    border: Border.all(color: value == c ? C.cat(c) : C.border, width: value == c ? 2 : 1.5),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                          color: C.cat(c), shape: c == 'pothole' ? BoxShape.circle : BoxShape.rectangle,
                          borderRadius: c == 'pothole' ? null : BorderRadius.circular(2)),
                    ),
                    const SizedBox(width: 8),
                    Text(categoryLabel[c]!, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    const SizedBox(width: 6),
                    Text(categoryUrdu[c]!, style: urdu(12)),
                    if (value == c) ...[const SizedBox(width: 6), Icon(Icons.check_circle, size: 18, color: C.cat(c))],
                  ]),
                ),
              ),
            ),
          ),
          if (c == 'pothole') const SizedBox(width: 10),
        ],
      ]);
}

/// Full-screen-ish error sheet matching the ErrorStates mock. Returns true for the primary action.
Future<bool?> showApiError(BuildContext context, ApiException e, {String? retryLabel}) {
  late final IconData icon;
  late final Color bg, fg;
  late final String title, body;
  String? detail;
  var primary = retryLabel ?? 'OK';
  switch (e.status) {
    case 413:
      (icon, bg, fg) = (Icons.insert_drive_file_outlined, C.errBg, C.errFg);
      title = 'This photo is too large';
      body = 'Please choose a smaller photo or take a new one.';
      detail = 'Limit 8 MB';
      primary = 'Choose another photo';
    case 415:
      (icon, bg, fg) = (Icons.insert_drive_file_outlined, C.errBg, C.errFg);
      title = 'That file isn’t a photo';
      body = 'RaastaAI only accepts photos. PDFs, videos and documents can’t be analysed.';
      detail = 'Accepted: JPG, PNG, WebP · checked by file content, not name';
      primary = 'Choose a photo';
    case 429:
      (icon, bg, fg) = (Icons.schedule, C.warnBg, C.warnFg);
      title = 'Please wait a few minutes';
      body = 'To keep the pilot fair and spam-free, each phone can send 5 reports every 10 minutes.';
      final mins = ((e.retryAfterS ?? 60) / 60).ceil();
      detail = 'You can report again in $mins minute${mins == 1 ? '' : 's'}. Your report is still on this screen.';
      primary = 'OK';
    case 409:
      (icon, bg, fg) = (Icons.content_copy, C.warnBg, C.warnFg);
      title = e.code == 'duplicate_report' ? 'Already reported' : 'This photo was already used';
      body = e.message;
      primary = 'OK';
    case 422:
      (icon, bg, fg) = (Icons.no_photography_outlined, C.errBg, C.errFg);
      title = 'Not a road photo';
      body = e.message;
      primary = 'Take a new photo';
    case 0:
      (icon, bg, fg) = (Icons.wifi_off, C.infoBg, C.infoFg);
      title = e.isTimeout ? 'The server is slow to answer' : 'Couldn’t reach RaastaAI';
      body = 'Check your connection. The free server may also be waking up — try again in a few seconds. Nothing you entered is lost.';
      primary = retryLabel ?? 'Try again';
    default:
      (icon, bg, fg) = (Icons.error_outline, C.errBg, C.errFg);
      title = e.status == 400 ? 'Please check your report' : 'Something went wrong';
      body = e.message;
  }
  return showModalBottomSheet<bool>(
    context: context,
    showDragHandle: true,
    backgroundColor: Colors.white,
    builder: (ctx) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          CircleAvatar(radius: 26, backgroundColor: bg, child: Icon(icon, color: fg)),
          const SizedBox(height: 14),
          Text(title, style: heading(20)),
          const SizedBox(height: 6),
          Text(body, style: const TextStyle(fontSize: 15, height: 1.45, color: C.body)),
          if (detail != null) ...[
            const SizedBox(height: 10),
            Text(detail, style: const TextStyle(fontSize: 13, color: C.muted)),
          ],
          const SizedBox(height: 18),
          PrimaryButton(primary, onPressed: () => Navigator.pop(ctx, true)),
          const SizedBox(height: 8),
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Close')),
        ]),
      ),
    ),
  );
}
