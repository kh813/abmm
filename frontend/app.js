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

  // Phase 2 Export elements
  const exportCard = document.getElementById("export-card");
  const exportDuration = document.getElementById("export-duration");
  const exportDurationValue = document.getElementById("export-duration-value");
  const exportFormat = document.getElementById("export-format");
  const exportModelTier = document.getElementById("export-model-tier");
  const exportBtn = document.getElementById("export-btn");

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
      if (exportCard) {
        exportCard.classList.remove("hidden");
      }
      const exportMidiBtn = document.getElementById("export-midi-btn");
      if (exportMidiBtn) {
        exportMidiBtn.disabled = false;
      }
      
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
    if (exportDuration) {
      exportDuration.max = maxDur;
    }
    
    // 現在値が上限を超えている場合は強制調整
    if (parseFloat(durationSlider.value) > maxDur) {
      durationSlider.value = maxDur;
      durationValue.textContent = parseFloat(maxDur).toFixed(1);
    }
    if (exportDuration && parseFloat(exportDuration.value) > maxDur) {
      exportDuration.value = maxDur;
      exportDurationValue.textContent = Math.round(maxDur);
    }
    
    // PCスペックに応じて推奨マーク付きのモデルドロップダウンを構築・再構築する
    populateOllamaModelSelect();
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

        if (exportCard) {
          exportCard.classList.remove("hidden");
        }
        const exportMidiBtn = document.getElementById("export-midi-btn");
        if (exportMidiBtn) {
          exportMidiBtn.disabled = false;
        }

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
  let ollamaDropdownPopulated = false;

  async function populateOllamaModelSelect() {
    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.get_ollama_candidates) {
      return;
    }
    try {
      const candidates = await pywebview.api.get_ollama_candidates();
      const currentVal = ollamaModelSelect.value;
      ollamaModelSelect.innerHTML = "";
      
      candidates.forEach(cand => {
        const opt = document.createElement("option");
        opt.value = cand.name;
        opt.textContent = cand.label;
        if (cand.disabled) {
          opt.disabled = true;
        }
        if (cand.name === currentVal) {
          opt.selected = true;
        }
        ollamaModelSelect.appendChild(opt);
      });
      
      if (!ollamaModelSelect.value && candidates.length > 0) {
        const recommended = candidates.find(c => c.is_recommended);
        if (recommended) {
          ollamaModelSelect.value = recommended.name;
        } else {
          ollamaModelSelect.value = candidates[0].name;
        }
        if (pywebview.api.set_ollama_model) {
          await pywebview.api.set_ollama_model(ollamaModelSelect.value);
        }
      }
      ollamaDropdownPopulated = true;
    } catch (err) {
      console.error("Failed to populate Ollama candidates select:", err);
    }
  }

  async function checkOllamaStatus() {
    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.check_ollama_status) {
      window.addEventListener("pywebviewready", checkOllamaStatus, { once: true });
      return;
    }

    if (!ollamaDropdownPopulated) {
      await populateOllamaModelSelect();
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
      // モーダルダイアログの表示と設定
      cancelRenderBtn.classList.add("hidden"); // ダウンロード中はキャンセルできないように隠す
      progressStatusText.textContent = `モデル '${selectedModel}' をダウンロード中...`;
      progressBarFill.style.width = "0%";
      progressPercent.textContent = "0%";
      progressCard.classList.remove("hidden");

      ollamaModelSelect.disabled = true;
      await pywebview.api.start_ollama_model_download(selectedModel);
    } catch (err) {
      alert(`ダウンロード開始エラー: ${err}`);
      progressCard.classList.add("hidden");
      ollamaModelSelect.disabled = false;
    }
  });

  // Ollamaモデルダウンロードのコールバック
  window.onOllamaDownloadProgress = (modelName, percent, status) => {
    const roundedPercent = Math.round(percent * 100);
    progressBarFill.style.width = roundedPercent + "%";
    progressPercent.textContent = roundedPercent + "%";
    progressStatusText.textContent = `モデル '${modelName}' をダウンロード中: ${status}`;
  };

  window.onOllamaDownloadComplete = (modelName, success) => {
    ollamaModelSelect.disabled = false;
    progressCard.classList.add("hidden");
    cancelRenderBtn.classList.remove("hidden"); // キャンセルボタンを元に戻す
    
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

  // 書き出し時間スライダーの値更新のリスナー
  if (exportDuration) {
    exportDuration.addEventListener("input", (e) => {
      exportDurationValue.textContent = e.target.value;
    });
  }

  // 書き出しボタンのリスナー
  if (exportBtn) {
    exportBtn.addEventListener("click", async () => {
      if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.select_export_file || !pywebview.api.start_export_async) {
        alert("APIが利用できません。");
        return;
      }
      
      const format = exportFormat.value;
      const durationVal = parseFloat(exportDuration.value);
      const tier = exportModelTier.value;
      
      // 1. ファイル選択ダイアログを表示
      const exportPath = await pywebview.api.select_export_file(format);
      if (!exportPath) {
        return; // ユーザーキャンセル
      }
      
      // 2. モーダル表示
      cancelRenderBtn.classList.remove("hidden");
      progressStatusText.textContent = "書き出しファイルを生成中...";
      progressBarFill.style.width = "0%";
      progressPercent.textContent = "0%";
      progressCard.classList.remove("hidden");
      
      const exportSeamlessLoop = document.getElementById("export-seamless-loop");
      const seamlessLoopVal = exportSeamlessLoop ? exportSeamlessLoop.checked : false;

      const params = {
        export_path: exportPath,
        export_duration: durationVal,
        export_format: format,
        model_tier: tier,
        seamless_loop: seamlessLoopVal
      };
      
      const response = await pywebview.api.start_export_async(params);
      if (response.status !== "success") {
        alert(`書き出し開始エラー: ${response.message}`);
        progressCard.classList.add("hidden");
        cancelRenderBtn.classList.remove("hidden");
      }
    });
  }

  // 音声書き出し完了・エラーのコールバック
  window.onExportComplete = (response) => {
    progressCard.classList.add("hidden");
    cancelRenderBtn.classList.remove("hidden");
    alert(`本番用BGMの書き出しが完了しました！\n保存先: ${response.export_path}`);
  };

  window.onExportError = (err) => {
    progressCard.classList.add("hidden");
    cancelRenderBtn.classList.remove("hidden");
    alert(`書き出しエラーが発生しました:\n${err}`);
  };

  // --- 設定＆モデル管理モーダル機能 ---
  const settingsModal = document.getElementById("settings-modal");
  const settingsToggleBtn = document.getElementById("settings-toggle-btn");
  const settingsCloseBtn = document.getElementById("settings-close-btn");
  const diskFreeVal = document.getElementById("disk-free-val");
  const diskTotalVal = document.getElementById("disk-total-val");
  const diskProgressFill = document.getElementById("disk-progress-fill");
  const modelsList = document.getElementById("models-list");
  const settingAutoUpdate = document.getElementById("setting-auto-update");

  if (settingsToggleBtn && settingsModal) {
    settingsToggleBtn.addEventListener("click", async () => {
      await loadSettingsAndDiskInfo();
      settingsModal.classList.remove("hidden");
    });
  }

  if (settingsCloseBtn && settingsModal) {
    settingsCloseBtn.addEventListener("click", () => {
      settingsModal.classList.add("hidden");
    });
  }

  async function loadSettingsAndDiskInfo() {
    if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.get_models_disk_info) return;
    
    try {
      // 1. 設定データの取得
      const settings = await pywebview.api.get_app_settings();
      if (settingAutoUpdate) {
        settingAutoUpdate.checked = settings.auto_update_check !== false;
      }
      
      // 2. ディスク・モデル情報の取得
      const info = await pywebview.api.get_models_disk_info();
      if (diskFreeVal) diskFreeVal.textContent = info.disk_free_gb;
      if (diskTotalVal) diskTotalVal.textContent = info.disk_total_gb;
      
      if (diskProgressFill && info.disk_total_gb > 0) {
        const percent = ((info.disk_total_gb - info.disk_free_gb) / info.disk_total_gb) * 100;
        diskProgressFill.style.width = `${percent}%`;
      }
      
      // 3. モデル一覧の構築
      if (modelsList) {
        modelsList.innerHTML = "";
        info.models.forEach(model => {
          const li = document.createElement("li");
          
          const infoDiv = document.createElement("div");
          infoDiv.className = "model-info";
          
          const nameSpan = document.createElement("span");
          nameSpan.className = "model-name";
          nameSpan.textContent = model.name;
          
          const sizeSpan = document.createElement("span");
          sizeSpan.className = "model-size";
          sizeSpan.textContent = model.downloaded ? `使用中: ${model.size_mb} MB` : "未ダウンロード";
          
          infoDiv.appendChild(nameSpan);
          infoDiv.appendChild(sizeSpan);
          
          const actionsDiv = document.createElement("div");
          actionsDiv.className = "model-actions";
          
          if (model.downloaded) {
            const delBtn = document.createElement("button");
            delBtn.className = "delete-btn";
            delBtn.textContent = "削除";
            delBtn.addEventListener("click", async () => {
              if (confirm(`本当にモデル '${model.name}' を削除しますか？\n削除すると、そのティアで本番書き出しを行う際に再ダウンロードが必要になります。`)) {
                try {
                  const target = model.type === "phase2" ? model.tier : model.model_name;
                  const res = await pywebview.api.delete_model(model.type, target);
                  if (res.status === "success") {
                    alert("モデルを削除しました。");
                    await loadSettingsAndDiskInfo();
                    checkOllamaStatus();
                  } else {
                    alert(`削除に失敗しました: ${res.message}`);
                  }
                } catch (e) {
                  alert(`エラー: ${e}`);
                }
              }
            });
            actionsDiv.appendChild(delBtn);
          } else {
            if (model.type === "phase2") {
              const dlBtn = document.createElement("button");
              dlBtn.className = "secondary-btn";
              dlBtn.textContent = "DL";
              dlBtn.addEventListener("click", async () => {
                try {
                  cancelRenderBtn.classList.remove("hidden");
                  progressStatusText.textContent = `モデル '${model.name}' をダウンロード中...`;
                  progressBarFill.style.width = "0%";
                  progressPercent.textContent = "0%";
                  progressCard.classList.remove("hidden");
                  
                  const res = await pywebview.api.start_model_download(model.tier);
                  if (res.status === "error") {
                    alert(res.message);
                    progressCard.classList.add("hidden");
                    cancelRenderBtn.classList.remove("hidden");
                  }
                } catch (e) {
                  alert(`エラー: ${e}`);
                  progressCard.classList.add("hidden");
                  cancelRenderBtn.classList.remove("hidden");
                }
              });
              actionsDiv.appendChild(dlBtn);
            } else {
              const statusSpan = document.createElement("span");
              statusSpan.style.color = "var(--text-secondary)";
              statusSpan.style.fontSize = "0.75rem";
              statusSpan.textContent = "未取得";
              actionsDiv.appendChild(statusSpan);
            }
          }
          
          li.appendChild(infoDiv);
          li.appendChild(actionsDiv);
          modelsList.appendChild(li);
        });
      }
    } catch (err) {
      console.error("Failed to load settings & disk info:", err);
    }
  }

  if (settingAutoUpdate) {
    settingAutoUpdate.addEventListener("change", async () => {
      if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.save_app_settings) return;
      const settings = {
        auto_update_check: settingAutoUpdate.checked
      };
      await pywebview.api.save_app_settings(settings);
    });
  }

  // --- Phase 2 モデルダウンロード用コールバックの紐付け ---
  window.onDownloadProgress = (tier, percent) => {
    const roundedPercent = Math.round(percent * 100);
    progressBarFill.style.width = roundedPercent + "%";
    progressPercent.textContent = roundedPercent + "%";
    progressStatusText.textContent = `モデル '${tier}' をダウンロード中...`;
  };

  window.onDownloadComplete = (tier, success) => {
    progressCard.classList.add("hidden");
    cancelRenderBtn.classList.remove("hidden");
    
    if (success) {
      alert(`モデル '${tier}' のダウンロードが完了しました！`);
    } else {
      alert(`モデル '${tier}' のダウンロードに失敗しました。`);
    }
    if (settingsModal && !settingsModal.classList.contains("hidden")) {
      loadSettingsAndDiskInfo();
    }
  };

  // --- MIDIインポート/エクスポート機能 ---
  const importMidiBtn = document.getElementById("import-midi-btn");
  const exportMidiBtn = document.getElementById("export-midi-btn");

  if (importMidiBtn) {
    importMidiBtn.addEventListener("click", async () => {
      if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.import_midi_file) {
        alert("APIが利用できません。");
        return;
      }
      try {
        const response = await pywebview.api.import_midi_file();
        if (response.status === "cancelled") {
          return;
        }
        if (response.status === "success") {
          statusPlaceholder.classList.add("hidden");
          statusContent.classList.remove("hidden");
          if (exportCard) {
            exportCard.classList.remove("hidden");
          }
          if (exportMidiBtn) {
            exportMidiBtn.disabled = false;
          }
          
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
          
          alert("MIDIファイルのインポートが完了しました。");
        } else {
          alert(`インポートに失敗しました: ${response.message}`);
        }
      } catch (err) {
        alert(`インポートエラー: ${err}`);
      }
    });
  }

  if (exportMidiBtn) {
    exportMidiBtn.addEventListener("click", async () => {
      if (typeof pywebview === "undefined" || !pywebview.api || !pywebview.api.export_midi_file) {
        alert("APIが利用できません。");
        return;
      }
      try {
        const response = await pywebview.api.export_midi_file();
        if (response.status === "cancelled") {
          return;
        }
        if (response.status === "success") {
          alert(`MIDIファイルをエクスポートしました。\n保存先: ${response.file_path}`);
        } else {
          alert(`エクスポートに失敗しました: ${response.message}`);
        }
      } catch (err) {
        alert(`エクスポートエラー: ${err}`);
      }
    });
  }

  // 初期ロード呼び出し
  loadPresetList();

  // アプリ起動時にスペック検出を実行
  initHardwareSpecs();
});

