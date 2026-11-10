// Public Firebase client configs (not secrets: access is enforced by Security Rules and the API).
// Web: config/firebase-web.json. Android: config/google-services.json (firebase apps:sdkconfig).
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

FirebaseOptions get firebaseOptions =>
    (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) ? _android : _web;

const _web = FirebaseOptions(
  apiKey: 'AIzaSyC0J8U-rJTaQIxPgxyNsFAuqJ9ikHN_Iyo',
  appId: '1:1046611325526:web:687e00e46f936b61d481f7',
  messagingSenderId: '1046611325526',
  projectId: 'rastaai-e99f8',
  authDomain: 'rastaai-e99f8.firebaseapp.com',
  storageBucket: 'rastaai-e99f8.firebasestorage.app',
);

const _android = FirebaseOptions(
  apiKey: 'AIzaSyDrYzuL0gXCqJnE5dopYqulUgWcYlNdj0E',
  appId: '1:1046611325526:android:9f31fe4ca2bf8349d481f7',
  messagingSenderId: '1046611325526',
  projectId: 'rastaai-e99f8',
  storageBucket: 'rastaai-e99f8.firebasestorage.app',
);
