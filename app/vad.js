// Mandarin Tutor — Voice Activity Detection (near-live, $0, browser-native).
// Monitors mic RMS volume via Web Audio API. Detects when the user starts
// speaking and auto-fires onSilence after a sustained pause, so there's no
// hold-to-talk button. Reused by both the chat mic and the drill recorder.
(function () {
  // attach(stream, opts) -> detach()
  //   opts.onSpeechStart()  fired once when speech is first detected
  //   opts.onSilence()      fired when silence persists after speech
  //   opts.threshold        RMS gate (0..1), default 0.015
  //   opts.silenceMs        pause length that ends a turn, default 1000ms
  //   opts.maxMs            hard cap so it can't run forever, default 12000ms
  //   opts.minSpeechMs      ignore blips shorter than this, default 250ms
  function attach(stream, opts) {
    opts = opts || {};
    const threshold = opts.threshold ?? 0.015;
    const silenceMs = opts.silenceMs ?? 1000;
    const maxMs = opts.maxMs ?? 12000;
    const minSpeechMs = opts.minSpeechMs ?? 250;

    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) { return () => {}; } // no Web Audio -> caller keeps manual stop

    const ctx = new AC();
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser);
    const buf = new Float32Array(analyser.fftSize);

    let raf = null;
    let stopped = false;
    let speechStarted = false;
    let speechStartAt = 0;
    let lastLoudAt = 0;
    const startedAt = performance.now();

    function rms() {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      return Math.sqrt(sum / buf.length);
    }

    function fire(cb) { try { if (typeof cb === "function") cb(); } catch (e) {} }

    function finish() {
      if (stopped) return;
      stopped = true;
      if (raf) cancelAnimationFrame(raf);
      try { src.disconnect(); } catch (e) {}
      try { ctx.close(); } catch (e) {}
      fire(opts.onSilence);
    }

    function tick() {
      if (stopped) return;
      const now = performance.now();
      const level = rms();

      if (level >= threshold) {
        lastLoudAt = now;
        if (!speechStarted) {
          speechStarted = true;
          speechStartAt = now;
          fire(opts.onSpeechStart);
        }
      }

      // End the turn once we've had real speech followed by a quiet gap.
      if (speechStarted && (now - speechStartAt) >= minSpeechMs &&
          (now - lastLoudAt) >= silenceMs) {
        finish();
        return;
      }
      // Hard safety cap.
      if ((now - startedAt) >= maxMs) { finish(); return; }

      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);

    // detach() lets the caller cancel without firing onSilence (e.g. manual stop)
    return function detach() {
      if (stopped) return;
      stopped = true;
      if (raf) cancelAnimationFrame(raf);
      try { src.disconnect(); } catch (e) {}
      try { ctx.close(); } catch (e) {}
    };
  }

  window.MTVad = { attach };
})();
