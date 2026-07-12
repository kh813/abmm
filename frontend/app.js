document.addEventListener("DOMContentLoaded", () => {
  // UI要素の取得
  const promptInput = document.getElementById("prompt-input");
  const tempoSlider = document.getElementById("tempo-slider");
  const tempoValue = document.getElementById("tempo-value");
  const durationSlider = document.getElementById("duration-slider");
  const durationValue = document.getElementById("duration-value");
  
  const keyMajorBtn = document.getElementById("key-major-btn");
  const keyMinorBtn = document.getElementById("key-minor-btn");
  
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
      // Python側の API を呼び出す
      const response = await pywebview.api.compose_and_preview(description, tempo, keyMode, duration);
      
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
});
