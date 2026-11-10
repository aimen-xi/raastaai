# What you need to do (accounts & credentials)

I can install tools, but I can't create accounts, type your passwords, or click "accept" on sign-in pages for you. Each step below takes a few minutes. Everything uses **free plans only**: never click "Upgrade to Blaze" or add a card.

When a step produces a secret, **do not paste it into the chat**. Save it to the file path given.

---

## 1. Firebase project (Spark / free)

1. Open https://console.firebase.google.com and sign in with your Google account.
2. **Add project**:
   - Name it `raastaai`. If the ID is taken, Firebase adds a suffix; note the final ID.
   - **Turn Google Analytics off**.
   - Click Create.
3. **Build → Authentication → Get started → Sign-in method**. Enable:
   - **Anonymous**
   - **Email/Password** (first toggle only)
4. **Build → Firestore Database → Create database**:
   - Edition: Standard.
   - Location: **asia-south1 (Mumbai)**. This is the closest to Pakistan and can't be changed later.
   - Choose **Start in production mode**. Our security rules will replace the defaults.
5. **Project settings (⚙) → General → Your apps → Web (`</>`)**:
   - Nickname `admin-dashboard`. Leave Hosting unticked; I'll set it up.
   - Copy the `firebaseConfig` block. It's public by design, so pasting it in chat is fine.
6. **Project settings → Service accounts → Generate new private key**:
   - Save the downloaded JSON as:
     `C:\Users\Zia Laptop\Desktop\rastaai\secrets\firebase-admin.json`
   - ⚠️ This file is a secret. It's git-ignored. Never share it or paste it in chat.
7. **Authentication → Users → Add user**:
   - Create your admin login: an email you control plus a strong password.
   - Tell me only the **email**. I'll run a script that gives it the `admin` role.

## 2. Firebase CLI login (after I confirm the CLI is installed)

Open a **new** PowerShell window (so it picks up the new PATH) and run:

```bash
firebase login
```

A browser window opens. Sign in with the same Google account and allow access.

## 3. Hugging Face (free hosting for the AI API)

1. Sign up at https://huggingface.co/join (free).
2. **Settings → Access Tokens → Create new token**:
   - Type: **Write**.
   - Name: `raastaai-deploy`.
3. Save the token in a file:
   `<project folder>\secrets\hf_token.txt`
4. Tell me your Hugging Face **username** (not the token).

## 4. GitHub (public repo, required by the AGPL licence)

1. Sign in at https://github.com. Create an **empty public repo** named `raastaai`. Don't add a README.
2. Send me the repo URL.

## 5. Phone for the demo (choose one, later)

- **Android phone:** Settings → About → tap Build number 7× → Developer options → **USB debugging ON**. Needs the Android command-line tools, about 3 GB. I'll install them when we reach Phase 4.
- **No phone:** we run the Flutter app as a web app in Chrome or Edge. No extra download.

> Disk space note: your C: drive has about **14 GB free**. Flutter needs about 3 GB and the Android toolchain about 3–4 GB. **Android Studio and the emulator (+10 GB) are skipped** for that reason.
