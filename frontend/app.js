document.addEventListener("DOMContentLoaded", () => {
  // UI要素の取得
  const promptInput = document.getElementById("prompt-input");
  
  // Ollama status elements
  const ollamaIndicator = document.getElementById("ollama-indicator");
  const ollamaStatusText = document.getElementById("ollama-status-text");
  const modelSelectionRow = document.getElementById("model-selection-row");
  const ollamaModelSelect = document.getElementById("ollama-model-select");
  const modelDownloadBar = document.getElementById("model-download-bar");
  const modelDownloadFill = document.getElementById("model-download-fill");
  const modelDownloadStatus = document.getElementById("model-download-status");
  const modelDownloadBtn = document.getElementById("model-download-btn");

  // Progress card elements
  const progressCard = document.getElementById("progress-card");
  const progressStatusText = document.getElementById("progress-status-text");
  const progressPercent = document.getElementById("progress-percent");
  const progressBarFill = document.getElementById("progress-bar-fill");
  const cancelRenderBtn = document.getElementById("cancel-render-btn");

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
      // プレースホルダーのリセットと進行状況カードの表示
      statusPlaceholder.classList.remove("hidden");
      statusContent.classList.add("hidden");
      progressCard.classList.remove("hidden");
      progressBarFill.style.width = "0%";
      progressPercent.textContent = "0%";
      progressStatusText.textContent = "MIDI生成要求の準備中...";

      const params = {
        description: description,
        tempo: tempo,
        key_mode: keyMode,
        duration: duration,
        brightness: brightness,
        energy: energy,
        density: density,
        reverb_space: reverbSpace,
        instruments: instruments,
        ollama_model: ollamaModelSelect.value,
        model_tier: "Lite",
        preview_only: false
      };

      // 非同期レンダリングをキック
      const response = await pywebview.api.start_render_async(params);
      if (response.status !== "success") {
        alert(`レンダリングの開始に失敗しました: ${response.message}`);
        progressCard.classList.add("hidden");
        composeBtn.disabled = false;
        btnSpinner.classList.add("hidden");
      }
    } catch (err) {
      alert(`API接続エラーが発生しました:\n${err}`);
      progressCard.classList.add("hidden");
      composeBtn.disabled = false;
      btnSpinner.classList.add("hidden");
    }
  });

  // キャンセルボタンのリスナー
  cancelRenderBtn.addEventListener("click", async () => {
    if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.cancel_render) {
      try {
        await pywebview.api.cancel_render();
        progressStatusText.textContent = "キャンセル要求送信中...";
      } catch (err) {
        console.error("Cancel failed:", err);
      }
    }
  });

  // 非同期レンダリングの進行状況コールバック
  window.updateRenderProgress = (val) => {
    const percent = Math.round(val * 100);
    progressBarFill.style.width = percent + "%";
    progressPercent.textContent = percent + "%";
  };

  window.updateRenderStatus = (msg) => {
    progressStatusText.textContent = msg;
  };

  window.onRenderComplete = (response) => {
    progressCard.classList.add("hidden");
    composeBtn.disabled = false;
    btnSpinner.classList.add("hidden");

    if (response.status === "success") {
      statusPlaceholder.classList.add("hidden");
      statusContent.classList.remove("hidden");
      
      resTempo.textContent = `${response.tempo_bpm} BPM`;
      resKey.textContent = response.key_mode === "major" ? "Major (明るい)" : "Minor (切ない)";
      resDuration.textContent = `${response.duration_minutes} 分`;
      
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

      const cacheBuster = `?t=${Date.now()}`;
      audioPreview.src = response.audio_url + cacheBuster;
      audioPreview.load();
      audioPreview.play().catch(e => console.log("Autoplay prevented:", e));
    } else {
      alert(`生成失敗: ${response.message}`);
    }
  };

  window.onRenderError = (err) => {
    progressCard.classList.add("hidden");
    composeBtn.disabled = false;
    btnSpinner.classList.add("hidden");
    alert(`エラーが発生しました:\n${err}`);
  };

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

  // Preset DOM elements
  const presetNameInput = document.getElementById("preset-name-input");
  const savePresetBtn = document.getElementById("save-preset-btn");
  const presetSelect = document.getElementById("preset-select");
  const loadPresetBtn = document.getElementById("load-preset-btn");
  const deletePresetBtn = document.getElementById("delete-preset-btn");

  // プリセット一覧を取得し選択肢を初期化する
  async function loadPresetList() {
    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.list_presets) {
      window.addEventListener("pywebviewready", loadPresetList, { once: true });
      return;
    }

    try {
      const list = await pywebview.api.list_presets();
      // デフォルト以外の選択肢をクリア
      presetSelect.innerHTML = '<option value="">-- 保存済みを選択 --</option>';
      
      list.forEach(preset => {
        const option = document.createElement("option");
        option.value = preset.key;
        option.textContent = preset.name;
        presetSelect.appendChild(option);
      });
    } catch (err) {
      console.error("Failed to load preset list:", err);
    }
  }

  // プリセット保存ボタンの処理
  savePresetBtn.addEventListener("click", async () => {
    const name = presetNameInput.value.trim();
    if (!name) {
      alert("保存するプリセット名を入力してください。");
      return;
    }

    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.save_preset) {
      alert("APIが利用できません。");
      return;
    }

    // パラメータの収集
    const params = {
      description: promptInput.value.trim(),
      tempo: parseInt(tempoSlider.value),
      key_mode: keyMode,
      duration: parseFloat(durationSlider.value),
      brightness: parseFloat(brightnessSlider.value),
      energy: parseFloat(energySlider.value),
      density: parseFloat(densitySlider.value),
      reverb_space: parseFloat(reverbSlider.value),
      instruments: {
        piano: parseFloat(instPiano.value),
        guitar: parseFloat(instGuitar.value),
        drums: parseFloat(instDrums.value),
        pad: parseFloat(instPad.value),
        bass: parseFloat(instBass.value)
      }
    };

    try {
      const response = await pywebview.api.save_preset(name, params);
      if (response.status === "success") {
        alert(`プリセット '${name}' を保存しました。`);
        presetNameInput.value = "";
        loadPresetList();
      } else {
        alert(`保存に失敗しました: ${response.message}`);
      }
    } catch (err) {
      alert(`保存エラー: ${err}`);
    }
  });

  // プリセット読み込みボタンの処理
  loadPresetBtn.addEventListener("click", async () => {
    const key = presetSelect.value;
    if (!key) {
      alert("読み込むプリセットを選択してください。");
      return;
    }

    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.load_preset) {
      alert("APIが利用できません。");
      return;
    }

    try {
      const response = await pywebview.api.load_preset(key);
      if (response.status === "success") {
        const params = response.params;
        
        // パラメータをUIに復元
        promptInput.value = params.description || "";
        
        tempoSlider.value = params.tempo || 80;
        tempoValue.textContent = params.tempo || 80;
        
        durationSlider.value = params.duration || 1.0;
        durationValue.textContent = parseFloat(params.duration || 1.0).toFixed(1);
        
        brightnessSlider.value = params.brightness !== undefined ? params.brightness : 0.5;
        brightnessValue.textContent = parseFloat(params.brightness !== undefined ? params.brightness : 0.5).toFixed(1);
        
        energySlider.value = params.energy !== undefined ? params.energy : 0.5;
        energyValue.textContent = parseFloat(params.energy !== undefined ? params.energy : 0.5).toFixed(1);
        
        densitySlider.value = params.density !== undefined ? params.density : 0.5;
        densityValue.textContent = parseFloat(params.density !== undefined ? params.density : 0.5).toFixed(1);
        
        reverbSlider.value = params.reverb_space !== undefined ? params.reverb_space : 0.5;
        reverbValue.textContent = parseFloat(params.reverb_space !== undefined ? params.reverb_space : 0.5).toFixed(1);
        
        keyMode = params.key_mode || "major";
        if (keyMode === "major") {
          keyMajorBtn.classList.add("active");
          keyMinorBtn.classList.remove("active");
        } else {
          keyMinorBtn.classList.add("active");
          keyMajorBtn.classList.remove("active");
        }
        
        // 楽器バランスの復元
        if (params.instruments) {
          const inst = params.instruments;
          instPiano.value = inst.piano !== undefined ? inst.piano : 0.8;
          instPianoValue.textContent = parseFloat(instPiano.value).toFixed(1);
          
          instGuitar.value = inst.guitar !== undefined ? inst.guitar : 0.0;
          instGuitarValue.textContent = parseFloat(instGuitar.value).toFixed(1);
          
          instDrums.value = inst.drums !== undefined ? inst.drums : 0.5;
          instDrumsValue.textContent = parseFloat(instDrums.value).toFixed(1);
          
          instPad.value = inst.pad !== undefined ? inst.pad : 0.2;
          instPadValue.textContent = parseFloat(instPad.value).toFixed(1);
          
          instBass.value = inst.bass !== undefined ? inst.bass : 0.4;
          instBassValue.textContent = parseFloat(instBass.value).toFixed(1);
        }

        // トラックリストの読み込み
        statusPlaceholder.classList.add("hidden");
        statusContent.classList.remove("hidden");
        resTempo.textContent = `${params.tempo || 80} BPM`;
        resKey.textContent = keyMode === "major" ? "Major (明るい)" : "Minor (切ない)";
        resDuration.textContent = `${params.duration || 1.0} 分`;

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

        // プレビュー音声のロードと再生
        const cacheBuster = `?t=${Date.now()}`;
        audioPreview.src = response.audio_url + cacheBuster;
        audioPreview.load();
        audioPreview.play().catch(e => console.log("Autoplay prevented:", e));

        alert(`プリセット '${response.name}' をロードし、プレビューを読み込みました。`);
      } else {
        alert(`プリセットの読み込みに失敗しました: ${response.message}`);
      }
    } catch (err) {
      alert(`ロードエラー: ${err}`);
    }
  });

  // プリセット削除ボタンの処理
  deletePresetBtn.addEventListener("click", async () => {
    const key = presetSelect.value;
    if (!key) {
      alert("削除するプリセットを選択してください。");
      return;
    }

    if (confirm("選択したプリセットを完全に削除してよろしいですか？")) {
      try {
        const response = await pywebview.api.delete_preset(key);
        if (response.status === "success") {
          alert("プリセットを削除しました。");
          loadPresetList();
        } else {
          alert(`削除に失敗しました: ${response.message}`);
        }
      } catch (err) {
        alert(`削除エラー: ${err}`);
      }
    }
  });

  // Ollama モデルおよび接続管理
  let ollamaConnected = false;
  let ollamaInstalledModels = [];

  async function checkOllamaStatus() {
    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.check_ollama_status) {
      window.addEventListener("pywebviewready", checkOllamaStatus, { once: true });
      return;
    }

    try {
      const status = await pywebview.api.check_ollama_status();
      const selectedModel = ollamaModelSelect.value;

      if (!status.running) {
        ollamaConnected = false;
        ollamaIndicator.textContent = "🔴";
        ollamaStatusText.textContent = "Ollamaが起動していません。";
        modelSelectionRow.classList.add("hidden");
        modelDownloadBar.classList.add("hidden");
        modelDownloadBtn.classList.add("hidden");
        
        composeBtn.disabled = true;
        composeBtn.classList.add("btn-disabled");
        composeBtn.querySelector(".btn-text").textContent = "❌ Ollama未起動のため作曲不可";
      } else {
        ollamaConnected = true;
        ollamaIndicator.textContent = "🟢";
        ollamaInstalledModels = status.models;
        modelSelectionRow.classList.remove("hidden");

        const isInstalled = ollamaInstalledModels.includes(selectedModel) || 
                            ollamaInstalledModels.includes(selectedModel + ":latest") ||
                            ollamaInstalledModels.some(m => m.startsWith(selectedModel));

        if (isInstalled) {
          ollamaStatusText.textContent = "Ollama 接続完了 / モデル準備OK";
          modelDownloadBar.classList.add("hidden");
          modelDownloadBtn.classList.add("hidden");
          
          composeBtn.disabled = false;
          composeBtn.classList.remove("btn-disabled");
          composeBtn.querySelector(".btn-text").textContent = "🎵 作曲してプレビューを生成 (Phase 1)";
        } else {
          ollamaStatusText.textContent = `モデル '${selectedModel}' が未インストールです。`;
          modelDownloadBtn.classList.remove("hidden");
          modelDownloadBar.classList.add("hidden");
          
          composeBtn.disabled = true;
          composeBtn.classList.add("btn-disabled");
          composeBtn.querySelector(".btn-text").textContent = "❌ モデル未ダウンロードのため作曲不可";
        }
      }
    } catch (err) {
      console.error("Failed to check Ollama status:", err);
    }
  }

  // モデルの選択変更イベント
  ollamaModelSelect.addEventListener("change", async () => {
    const val = ollamaModelSelect.value;
    if (typeof pywebview !== "undefined" && pywebview.api && pywebview.api.set_ollama_model) {
      await pywebview.api.set_ollama_model(val);
    }
    checkOllamaStatus();
  });

  // Ollama モデルダウンロードボタンの処理
  modelDownloadBtn.addEventListener("click", async () => {
    const selectedModel = ollamaModelSelect.value;
    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.start_ollama_model_download) {
      alert("APIが利用できません。");
      return;
    }

    try {
      modelDownloadBtn.classList.add("hidden");
      modelDownloadBar.classList.remove("hidden");
      ollamaModelSelect.disabled = true;
      modelDownloadFill.style.width = "0%";
      modelDownloadStatus.textContent = "ダウンロード開始中...";
      
      await pywebview.api.start_ollama_model_download(selectedModel);
    } catch (err) {
      alert(`ダウンロード開始エラー: ${err}`);
      modelDownloadBtn.classList.remove("hidden");
      modelDownloadBar.classList.add("hidden");
      ollamaModelSelect.disabled = false;
    }
  });

  // Ollamaモデルダウンロードのコールバック
  window.onOllamaDownloadProgress = (modelName, percent, status) => {
    const roundedPercent = Math.round(percent * 100);
    modelDownloadFill.style.width = roundedPercent + "%";
    modelDownloadStatus.textContent = `${status} (${roundedPercent}%)`;
  };

  window.onOllamaDownloadComplete = (modelName, success) => {
    ollamaModelSelect.disabled = false;
    modelDownloadBar.classList.add("hidden");
    
    if (success) {
      alert(`モデル '${modelName}' のダウンロードが完了しました！`);
    } else {
      alert(`モデル '${modelName}' のダウンロードに失敗しました。Ollamaのログを確認してください。`);
    }
    checkOllamaStatus();
  };

  // 定期的なOllamaステータス確認 (10秒ごと)
  setInterval(checkOllamaStatus, 10000);
  
  // 起動時のチェック
  checkOllamaStatus();

  // 初期ロード呼び出し
  loadPresetList();

  // アプリ起動時にスペック検出を実行
  initHardwareSpecs();
});

