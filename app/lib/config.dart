import 'package:latlong2/latlong.dart';

/// API address. Normally read at runtime from the public Firestore doc `public/config`
/// (written by tools/serve_public.py when the tunnel starts), so a new tunnel URL needs no rebuild.
/// `--dart-define=API_BASE=...` pins it instead (e.g. local development).
const apiBaseOverride = String.fromEnvironment('API_BASE');
const apiBaseFallback = 'http://localhost:7860';
const publicConfigUrl =
    'https://firestore.googleapis.com/v1/projects/rastaai-e99f8/databases/(default)/documents/public/config';

/// Show "Try a sample photo" (staged dataset images) for the demo. Judges asked for demo
/// photos to be staged/dataset images, never photos of real people or vehicles.
const demoSamples = bool.fromEnvironment('DEMO_SAMPLES', defaultValue: true);

const maxUploadBytes = 8 * 1024 * 1024;
const overrideNoteMinChars = 15; // must match the API (override_note_min_chars)
const noteMaxChars = 200;
const goodAccuracyM = 50.0;

/// Manual-pin starting point when location is denied (Lahore city centre).
const defaultCenter = LatLng(31.5204, 74.3587);
