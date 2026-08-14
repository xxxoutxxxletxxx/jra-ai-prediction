/* 競馬AI予想 - 静的サイト用 JS (vanilla JS / フレームワーク不使用) */

var appState = {
  latest: null,          // data/latest.json の中身
  currentDate: null,     // 選択中の日付 "YYYY-MM-DD"
  currentTrack: null,    // 選択中の競馬場コード
  archiveIndex: null,    // data/archive/index.json の中身
  archiveDateData: null, // 選択中の archive 日付データ
  currentArchiveDate: null,
};

function escapeHtml(str) {
  return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function formatScore(score) {
  var n = Number(score);
  if (isNaN(n)) return "-";
  return (n * 100).toFixed(1) + "%";
}

function formatOdds(odds) {
  if (odds === null || odds === undefined) return "未取得";
  var n = Number(odds);
  if (isNaN(n) || n <= 0) return "未取得";
  return n.toFixed(1) + "倍";
}

function formatExpectedValue(ev, odds) {
  if (odds === null || odds === undefined) return "未取得";
  if (ev === null || ev === undefined) return "未取得";
  var n = Number(ev);
  if (isNaN(n)) return "未取得";
  return n.toFixed(2);
}

function markForRank(rank) {
  if (rank === 1) return "◎";
  if (rank === 2) return "○";
  if (rank === 3) return "▲";
  return "";
}

function dateLabelShort(dateStr) {
  // "2026-08-15" -> "8/15"
  var parts = dateStr.split("-");
  if (parts.length !== 3) return dateStr;
  return parseInt(parts[1], 10) + "/" + parseInt(parts[2], 10);
}

function weekdayJp(dateStr) {
  var d = new Date(dateStr + "T00:00:00");
  var w = ["日", "月", "火", "水", "木", "金", "土"];
  return w[d.getDay()];
}

function fetchJSON(url) {
  return fetch(url, { cache: "no-store" }).then(function (res) {
    if (!res.ok) throw new Error("HTTP " + res.status + " for " + url);
    return res.json();
  });
}

/* ==================== 推奨馬カード ==================== */

function renderRecommendCard(containerEl, rec) {
  if (!rec) {
    containerEl.innerHTML = '<div class="empty">推奨馬データがありません</div>';
    return;
  }
  var oddsText = formatOdds(rec.odds);
  var evText = formatExpectedValue(rec.expected_value, rec.odds);

  containerEl.innerHTML =
    '<p class="rc-title">今日のAI推奨馬</p>' +
    '<p class="rc-place">' + escapeHtml(rec.jyo_name) + " " + escapeHtml(rec.race_num) + "R</p>" +
    '<div class="rc-horse">' +
      '<span class="rc-mark">' + markForRank(1) + "</span>" +
      '<span class="rc-umaban">' + escapeHtml(rec.umaban) + "</span>" +
      '<span class="rc-name">' + escapeHtml(rec.bamei) + "</span>" +
    "</div>" +
    '<div class="rc-stats">' +
      '<div class="rc-stat"><span class="label">AIスコア</span><span class="value">' + formatScore(rec.score) + "</span></div>" +
      '<div class="rc-stat"><span class="label">単勝オッズ</span><span class="value' + (rec.odds ? "" : " na") + '">' + oddsText + "</span></div>" +
      '<div class="rc-stat"><span class="label">期待値</span><span class="value' + (rec.odds && rec.expected_value != null ? "" : " na") + '">' + evText + "</span></div>" +
    "</div>";
}

/* ==================== 競馬場タブ ==================== */

function renderTrackTabs(tracksObj, containerEl, selectedCd, onSelect) {
  var codes = Object.keys(tracksObj).sort();
  containerEl.innerHTML = "";
  codes.forEach(function (cd) {
    var btn = document.createElement("button");
    btn.className = "tab-btn" + (cd === selectedCd ? " active" : "");
    btn.textContent = tracksObj[cd].name;
    btn.addEventListener("click", function () {
      onSelect(cd);
    });
    containerEl.appendChild(btn);
  });
}

/* ==================== レース一覧 ==================== */

function renderRaceList(track, containerEl) {
  if (!track) {
    containerEl.innerHTML = '<div class="empty">レースデータがありません</div>';
    return;
  }
  var raceNums = Object.keys(track.races).sort(function (a, b) {
    return parseInt(a, 10) - parseInt(b, 10);
  });

  var html = "";
  raceNums.forEach(function (raceNum) {
    var horses = track.races[raceNum];
    var top3 = horses.slice(0, 3);
    var raceId = track.name + "-" + raceNum;

    html += '<article class="race-card">';
    html += '<div class="race-card-header"><span>' + escapeHtml(track.name) + " " + escapeHtml(raceNum) + "R</span></div>";
    html += '<div class="top3-list">';
    top3.forEach(function (h) {
      html +=
        '<div class="top3-row mark-' + h.rank + '">' +
          '<span class="mark">' + markForRank(h.rank) + "</span>" +
          '<span class="umaban-badge">' + escapeHtml(h.umaban) + "</span>" +
          '<span class="horse-name">' + escapeHtml(h.bamei) + "</span>" +
          '<span class="score">' + formatScore(h.score) + "</span>" +
        "</div>";
    });
    html += "</div>";

    html += '<button class="toggle-all-btn" data-target="all-' + raceId + '">全頭を見る</button>';
    html += '<div class="all-horses" id="all-' + raceId + '">';
    horses.forEach(function (h) {
      html +=
        '<div class="all-horse-row">' +
          '<span class="all-rank">' + (h.rank || "-") + "</span>" +
          '<span class="all-umaban">' + escapeHtml(h.umaban) + "</span>" +
          '<div class="all-horse-main">' +
            '<span class="name-line">' + escapeHtml(h.bamei) + "</span>" +
            '<span class="sub-line">' +
              "騎手コード " + escapeHtml(h.kisyu_code || "-") + " ・ " +
              "AIスコア " + formatScore(h.score) + " ・ " +
              "オッズ " + formatOdds(h.odds) + " ・ " +
              "期待値 " + formatExpectedValue(h.expected_value, h.odds) +
            "</span>" +
          "</div>" +
        "</div>";
    });
    html += "</div>";
    html += "</article>";
  });

  containerEl.innerHTML = html;

  // 全頭を見る トグル
  var buttons = containerEl.querySelectorAll(".toggle-all-btn");
  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = btn.getAttribute("data-target");
      var target = document.getElementById(targetId);
      if (!target) return;
      var isOpen = target.classList.toggle("open");
      btn.textContent = isOpen ? "閉じる" : "全頭を見る";
    });
  });
}

/* ==================== トップページ (latest.json) ==================== */

function selectTrack(cd) {
  appState.currentTrack = cd;
  var dateData = appState.latest.dates[appState.currentDate];
  renderTrackTabs(dateData.tracks, document.getElementById("trackTabs"), cd, selectTrack);
  renderRaceList(dateData.tracks[cd], document.getElementById("raceList"));
}

function selectDate(dateStr) {
  appState.currentDate = dateStr;
  var dateData = appState.latest.dates[dateStr];

  // 日付タブの選択状態を更新
  var tabButtons = document.querySelectorAll("#dateTabs .tab-btn");
  tabButtons.forEach(function (btn) {
    btn.classList.toggle("active", btn.getAttribute("data-date") === dateStr);
  });

  renderRecommendCard(document.getElementById("recommendCard"), dateData.recommendation);

  var trackCodes = Object.keys(dateData.tracks).sort();
  var defaultTrack = trackCodes[0];
  selectTrack(defaultTrack);
}

function loadLatestAndRender() {
  fetchJSON("data/latest.json")
    .then(function (data) {
      appState.latest = data;

      document.getElementById("updatedAt").textContent = "最終更新: " + data.updated_at;

      var dateKeys = Object.keys(data.dates).sort();
      if (dateKeys.length === 0) {
        document.getElementById("targetDates").textContent = "予測対象: データなし";
        document.getElementById("recommendCard").innerHTML = '<div class="empty">予測データがありません</div>';
        return;
      }

      var targetLabels = dateKeys.map(function (d) { return data.dates[d].label; });
      document.getElementById("targetDates").textContent = "予測対象: " + targetLabels.join(" / ");

      var dateTabsEl = document.getElementById("dateTabs");
      dateTabsEl.innerHTML = "";
      dateKeys.forEach(function (dateStr) {
        var btn = document.createElement("button");
        btn.className = "tab-btn";
        btn.setAttribute("data-date", dateStr);
        btn.textContent = dateLabelShort(dateStr) + " " + weekdayJp(dateStr);
        btn.addEventListener("click", function () {
          selectDate(dateStr);
        });
        dateTabsEl.appendChild(btn);
      });

      selectDate(dateKeys[0]);
    })
    .catch(function (err) {
      document.getElementById("recommendCard").innerHTML = '<div class="empty">データ読み込みに失敗しました</div>';
      console.error(err);
    });
}

/* ==================== 過去の予想ページ (archive) ==================== */

function selectArchiveTrack(cd) {
  var dateData = appState.archiveDateData;
  renderTrackTabs(dateData.tracks, document.getElementById("trackTabs"), cd, selectArchiveTrack);
  renderRaceList(dateData.tracks[cd], document.getElementById("raceList"));
}

function selectArchiveDate(dateStr) {
  appState.currentArchiveDate = dateStr;

  var buttons = document.querySelectorAll("#archiveDateList .archive-date-btn");
  buttons.forEach(function (btn) {
    btn.classList.toggle("active", btn.getAttribute("data-date") === dateStr);
  });

  fetchJSON("data/archive/" + dateStr + ".json")
    .then(function (data) {
      appState.archiveDateData = data;
      var trackCodes = Object.keys(data.tracks).sort();
      if (trackCodes.length === 0) {
        document.getElementById("trackTabs").innerHTML = "";
        document.getElementById("raceList").innerHTML = '<div class="empty">レースデータがありません</div>';
        return;
      }
      selectArchiveTrack(trackCodes[0]);
    })
    .catch(function (err) {
      document.getElementById("raceList").innerHTML = '<div class="empty">データ読み込みに失敗しました</div>';
      console.error(err);
    });
}

function loadArchiveAndRender() {
  fetchJSON("data/archive/index.json")
    .then(function (data) {
      appState.archiveIndex = data;
      var listEl = document.getElementById("archiveDateList");

      if (!data.dates || data.dates.length === 0) {
        listEl.innerHTML = '<div class="empty">過去の予想データがありません</div>';
        return;
      }

      listEl.innerHTML = "";
      data.dates.forEach(function (entry) {
        var btn = document.createElement("button");
        btn.className = "archive-date-btn";
        btn.setAttribute("data-date", entry.date);
        btn.innerHTML =
          "<span>" + escapeHtml(entry.label) + "</span>" +
          '<span class="count">' + entry.race_count + "レース / " + entry.horse_count + "頭</span>";
        btn.addEventListener("click", function () {
          selectArchiveDate(entry.date);
        });
        listEl.appendChild(btn);
      });

      selectArchiveDate(data.dates[0].date);
    })
    .catch(function (err) {
      document.getElementById("archiveDateList").innerHTML = '<div class="empty">データ読み込みに失敗しました</div>';
      console.error(err);
    });
}
