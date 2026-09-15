(function () {
  'use strict';

  var stage = document.querySelector('[data-flipnote-player]');
  if (!stage) return;

  var source = stage.getAttribute('data-source');
  var mount = stage.querySelector('.flipnote-player-canvas');
  var fallback = stage.querySelector('.flipnote-player-fallback');
  var status = stage.querySelector('[data-display="status"]');
  var bigPlay = stage.querySelector('[data-action="big-play"]');
  var controls = stage.parentNode.querySelector('.flipnote-controls');
  var playButton = controls.querySelector('[data-action="play"]');
  var muteButton = controls.querySelector('[data-action="mute"]');
  var loopButton = controls.querySelector('[data-action="loop"]');
  var progress = controls.querySelector('[data-control="progress"]');
  var time = controls.querySelector('[data-display="time"]');
  var controlButtons = controls.querySelectorAll('button');
  var seeking = false;
  var hasPlayed = false;
  var player;

  function setControlsEnabled(enabled) {
    for (var i = 0; i < controlButtons.length; i++) {
      controlButtons[i].disabled = !enabled;
    }
    progress.disabled = !enabled;
  }

  function setPlayState(playing) {
    playButton.textContent = playing ? 'Pause' : 'Play';
    bigPlay.hidden = playing;
    stage.classList.toggle('is-playing', playing);
    if (playing) hasPlayed = true;
  }

  function updateTime() {
    if (!player || !player.isNoteLoaded) return;
    time.textContent = player.getTimeCounter();
  }

  function updateProgress(value) {
    if (seeking) return;
    var amount = Number(value);
    if (!isFinite(amount)) amount = player && player.isNoteLoaded ? player.getProgress() : 0;
    progress.value = String(Math.max(0, Math.min(1000, Math.round(amount * 10))));
    updateTime();
  }

  function updateVolume() {
    if (!player || !player.isNoteLoaded) return;
    var muted = player.getMuted();
    muteButton.textContent = muted ? 'Muted' : 'Sound';
    muteButton.setAttribute('aria-pressed', muted ? 'true' : 'false');
  }

  function updateLoop() {
    if (!player || !player.isNoteLoaded) return;
    var looped = player.getLoop();
    loopButton.classList.toggle('is-active', looped);
    loopButton.setAttribute('aria-pressed', looped ? 'true' : 'false');
  }

  function showError(message) {
    stage.classList.add('has-player-error');
    stage.classList.remove('is-ready');
    fallback.hidden = false;
    bigPlay.hidden = true;
    status.hidden = false;
    status.textContent = message;
    setControlsEnabled(false);
  }

  if (!window.flipnote || !window.flipnote.Player) {
    showError('Playback unavailable — showing the first frame.');
    return;
  }

  try {
    player = new window.flipnote.Player(mount, 320, 240);
  } catch (err) {
    showError('Playback is not supported by this browser.');
    return;
  }

  player.on('ready', function () {
    stage.classList.add('is-ready');
    stage.classList.remove('has-player-error');
    fallback.hidden = true;
    status.hidden = true;
    bigPlay.hidden = false;
    setControlsEnabled(true);
    setPlayState(false);
    updateProgress(0);
    updateVolume();
    updateLoop();
  });

  player.on('play', function () {
    setPlayState(true);
  });

  player.on('pause', function () {
    setPlayState(false);
  });

  player.on('ended', function () {
    setPlayState(false);
    updateProgress(100);
  });

  player.on('progress', function (value) {
    updateProgress(value);
  });

  player.on('timeupdate', function () {
    updateTime();
  });

  player.on('volumechange', function () {
    updateVolume();
  });

  player.on('error', function () {
    showError('Could not play this Flipnote — showing the first frame.');
  });

  function togglePlay() {
    if (!player || !player.isNoteLoaded) return;
    player.togglePlay();
  }

  playButton.addEventListener('click', togglePlay);
  bigPlay.addEventListener('click', togglePlay);

  mount.addEventListener('click', function () {
    if (hasPlayed) togglePlay();
  });

  muteButton.addEventListener('click', function () {
    if (!player || !player.isNoteLoaded) return;
    player.toggleMuted();
    updateVolume();
  });

  loopButton.addEventListener('click', function () {
    if (!player || !player.isNoteLoaded) return;
    player.toggleLoop();
    updateLoop();
  });

  function beginSeek() {
    if (!player || !player.isNoteLoaded || seeking) return;
    seeking = true;
    player.startSeek();
  }

  function moveSeek() {
    if (!player || !player.isNoteLoaded) return;
    if (!seeking) beginSeek();
    player.seek(Number(progress.value) / 1000);
    updateTime();
  }

  function finishSeek() {
    if (!player || !player.isNoteLoaded || !seeking) return;
    player.seek(Number(progress.value) / 1000);
    player.endSeek();
    seeking = false;
    updateProgress(player.getProgress());
  }

  progress.addEventListener('pointerdown', beginSeek);
  progress.addEventListener('input', moveSeek);
  progress.addEventListener('change', finishSeek);
  progress.addEventListener('pointerup', finishSeek);
  progress.addEventListener('keyup', finishSeek);

  player.load(source).catch(function () {
    showError('Could not play this Flipnote — showing the first frame.');
  });
}());
