document.addEventListener("DOMContentLoaded", () => {
  // UI要素の取得
  const promptInput = document.getElementById("prompt-input");
  const tempoSlider = document.getElementById("tempo-slider");
  const tempoValue = document.getElementById("tempo-value");
  const durationSlider = document.getElementById("duration-slider");
  const durationValue = document.getElementById("duration-value");
  
  const keyMajorBtn = document.getElementById("key-major-btn");
  const keyMinorBtn = document.getElementById("key-minor-btn");

  // New parameter sliders
  const brightnessSlider = document.getElementById("brightness-slider");
  const brightnessValue = document.getElementById("brightness-value");
  const energySlider = document.getElementById("energy-slider");
  const energyValue = document.getElementById("energy-value");
  const densitySlider = document.getElementById("density-slider");
  const densityValue = document.getElementById("density-value");
  const reverbSlider = document.getElementById("reverb-slider");
  const reverbValue = document.getElementById("reverb-value");

  // Instrument sliders
  const instPiano = document.getElementById("inst-piano");
  const instPianoValue = document.getElementById("inst-piano-value");
  const instGuitar = document.getElementById("inst-guitar");
  const instGuitarValue = document.getElementById("inst-guitar-value");
  const instDrums = document.getElementById("inst-drums");
  const instDrumsValue = document.getElementById("inst-drums-value");
  const instPad = document.getElementById("inst-pad");
  const instPadValue = document.getElementById("inst-pad-value");
  const instBass = document.getElementById("inst-bass");
  const instBassValue = document.getElementById("inst-bass-value");
  
  const composeBtn = document.getElementById("compose-btn");
  const btnSpinner = document.getElementById("btn-spinner");
  
  const statusPlaceholder = document.getElementById("status-placeholder");
  const statusContent = document.getElementById("status-content");
  
  const resTempo = document.getElementById("res-tempo");
  const resKey = document.getElementById("res-key");
  const resDuration = document.getElementById("res-duration");
  const tracksList = document.getElementById("tracks-list");
  const audioPreview = document.getElementById("audio-preview");

  let keyMode = "major";

  // スライダーの値表示のリアルタイム更新
  tempoSlider.addEventListener("input", (e) => {
    tempoValue.textContent = e.target.value;
  });

  durationSlider.addEventListener("input", (e) => {
    durationValue.textContent = parseFloat(e.target.value).toFixed(1);
  });

  brightnessSlider.addEventListener("input", (e) => {
    brightnessValue.textContent = parseFloat(e.target.value).toFixed(1);
  });

  energySlider.addEventListener("input", (e) => {
    energyValue.textContent = parseFloat(e.target.value).toFixed(1);
  });

  densitySlider.addEventListener("input", (e) => {
    densityValue.textContent = parseFloat(e.target.value).toFixed(1);
  });

  reverbSlider.addEventListener("input", (e) => {
    reverbValue.textContent = parseFloat(e.target.value).toFixed(1);
  });

  // 楽器スライダー
  instPiano.addEventListener("input", (e) => {
    instPianoValue.textContent = parseFloat(e.target.value).toFixed(1);
  });
  instGuitar.addEventListener("input", (e) => {
    instGuitarValue.textContent = parseFloat(e.target.value).toFixed(1);
  });
  instDrums.addEventListener("input", (e) => {
    instDrumsValue.textContent = parseFloat(e.target.value).toFixed(1);
  });
  instPad.addEventListener("input", (e) => {
    instPadValue.textContent = parseFloat(e.target.value).toFixed(1);
  });
  instBass.addEventListener("input", (e) => {
    instBassValue.textContent = parseFloat(e.target.value).toFixed(1);
  });

  // キー（Major/Minor）トグルボタンの挙動
  keyMajorBtn.addEventListener("click", () => {
    keyMajorBtn.classList.add("active");
    keyMinorBtn.classList.remove("active");
    keyMode = "major";
  });

  keyMinorBtn.addEventListener("click", () => {
    keyMinorBtn.classList.add("active");
    keyMajorBtn.classList.remove("active");
    keyMode = "minor";
  });

  // 作曲・プレビュー実行アクション
  composeBtn.addEventListener("click", async () => {
    const description = promptInput.value.trim();
    if (!description) {
      alert("BGMの雰囲気や展開などの指示テキストを入力してください。");
      return;
    }

    const tempo = parseInt(tempoSlider.value);
    const duration = parseFloat(durationSlider.value);
    const brightness = parseFloat(brightnessSlider.value);
    const energy = parseFloat(energySlider.value);
    const density = parseFloat(densitySlider.value);
    const reverbSpace = parseFloat(reverbSlider.value);

    // 楽器バランス辞書の構築
    const instruments = {
      piano: parseFloat(instPiano.value),
      guitar: parseFloat(instGuitar.value),
      drums: parseFloat(instDrums.value),
      pad: parseFloat(instPad.value),
      bass: parseFloat(instBass.value)
    };

    // 処理中のローディング状態に変更
    composeBtn.disabled = true;
    btnSpinner.classList.remove("hidden");
    
    // pywebview APIブリッジの存在確認
    if (typeof pywebview === "undefined" || !pywebview.api) {
      alert("Python API がロードされていません。デスクトップアプリから実行していることを確認してください。");
      composeBtn.disabled = false;
      btnSpinner.classList.add("hidden");
      return;
    }

    try {
      // Python側の API を呼び出す（拡張パラメータをすべて引き渡す）
      const response = await pywebview.api.compose_and_preview(
        description,
        tempo,
        keyMode,
        duration,
        brightness,
        energy,
        density,
        reverbSpace,
        instruments
      );
      
      if (response.status === "success") {
        // プレースホルダーを隠し、生成結果を表示
        statusPlaceholder.classList.add("hidden");
        statusContent.classList.remove("hidden");
        
        // メタデータの更新
        resTempo.textContent = `${response.tempo_bpm} BPM`;
        resKey.textContent = response.key_mode === "major" ? "Major (明るい)" : "Minor (切ない)";
        resDuration.textContent = `${response.duration_minutes} 分`;
        
        // トラックリストのクリアと再構築
        tracksList.innerHTML = "";
        response.tracks.forEach(track => {
          const li = document.createElement("li");
          
          const nameBadge = document.createElement("span");
          nameBadge.className = "track-name-badge";
          nameBadge.innerHTML = `🎹 ${track.track_name} <span class="track-inst">${track.instrument}</span>`;
          
          const notesCount = document.createElement("span");
          notesCount.className = "track-notes-count";
          notesCount.textContent = `${track.notes_count} 音`;
          
          li.appendChild(nameBadge);
          li.appendChild(notesCount);
          tracksList.appendChild(li);
        });

        // プレビューオーディオのロードと再生
        // キャッシュによる古い音声の再生を防ぐため、ランダムタイムスタンプを付加 (cache busting)
        const cacheBuster = `?t=${Date.now()}`;
        audioPreview.src = response.audio_url + cacheBuster;
        audioPreview.load();
        
        // 音声を再生（ブラウザポリシーに引っかかった場合はエラー出力を無視）
        audioPreview.play().catch(e => console.log("Autoplay was prevented:", e));
      } else {
        alert(`プレビューの生成中にエラーが発生しました:\n${response.message}`);
      }
    } catch (err) {
      alert(`API接続エラーが発生しました:\n${err}`);
    } finally {
      // ローディング状態の解除
      composeBtn.disabled = false;
      btnSpinner.classList.add("hidden");
    }
  });

  // PCのスペック情報を取得・UIに反映する関数
  async function initHardwareSpecs() {
    if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.get_hardware_specs) {
      try {
        const specs = await pywebview.api.get_hardware_specs();
        updateHardwareUI(specs);
      } catch (err) {
        console.error("Failed to get hardware specs:", err);
      }
    } else {
      // APIブリッジがまだロードされていない場合はイベントを待機する
      window.addEventListener("pywebviewready", initHardwareSpecs, { once: true });
    }
  }

  function updateHardwareUI(specs) {
    const specText = document.getElementById("spec-text");
    if (!specText) return;
    
    specText.innerHTML = `検出スペック: <strong>${specs.cpu_brand} (${specs.memory_gb}GB RAM)</strong> → 推奨: <strong>${specs.recommended_model_tier}</strong> / 最大長: <strong>${specs.max_duration_minutes}分</strong>`;
    
    // 曲の長さスライダーの最大値をスペック上限に変更
    const maxDur = specs.max_duration_minutes;
    durationSlider.max = maxDur;
    
    // 現在値が上限を超えている場合は強制調整
    if (parseFloat(durationSlider.value) > maxDur) {
      durationSlider.value = maxDur;
      durationValue.textContent = parseFloat(maxDur).toFixed(1);
    }
  }

  // アプリ起動時にスペック検出を実行
  initHardwareSpecs();
});

