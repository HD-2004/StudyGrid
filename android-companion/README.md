# StudyGrid Android Companion

Android 9+ companion for the Phase 6 Health Connect MVP. It pairs to one
anonymous StudyGrid plan, reads only sleep, resting heart rate, and HRV, and
sends daily aggregates rather than raw samples.

## Run

1. Open `android-companion/` in Android Studio.
2. Run the `app` configuration on an Android 9+ phone with Health Connect.
3. Enter the HTTPS StudyGrid API address and the one-time code shown in the
   web Progress screen.
4. Grant the requested Health Connect permissions, then choose **Sync now**.

For the Android emulator, a debug build may use `http://10.0.2.2:8000` to reach
a backend on the host. Release builds do not allow cleartext traffic. A default
URL can be injected without changing source:

```powershell
.\gradlew.bat :app:assembleDebug -PSTUDYGRID_API_URL=https://studygrid.example.com
```

The bearer token is encrypted with an Android Keystore key. Disconnecting from
the web app revokes it and deletes the server-side health summaries.
