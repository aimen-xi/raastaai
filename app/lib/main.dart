import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'firebase_options.dart';
import 'screens/home.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: firebaseOptions);
  // Anonymous identity: no citizen accounts (cut by the judges), but every request carries a
  // Firebase ID token so the server can rate-limit per device.
  if (FirebaseAuth.instance.currentUser == null) {
    FirebaseAuth.instance.signInAnonymously().ignore();
  }
  Api.instance.wake(); // start waking the free server while the user frames the photo
  runApp(const RaastaApp());
}

class RaastaApp extends StatelessWidget {
  const RaastaApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'RaastaAI',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        // Phone-width column even on a laptop browser (the demo runs as a web build).
        builder: (context, child) => ColoredBox(
          color: const Color(0xFFE9E8E3),
          child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 480), child: child)),
        ),
        home: const HomeScreen(),
      );
}
