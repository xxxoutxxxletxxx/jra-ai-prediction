(function () {
  "use strict";

  var selectedTrack;
  var payload;

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function table(headers, rows, rowValues) {
    var wrapper = element("div", "stats-table-wrap");
    var tableNode = element("table", "stats-table");
    var head = element("thead");
    var headerRow = element("tr");
    headers.forEach(function (label) {
      var cell = element("th", "", label);
      cell.scope = "col";
      headerRow.appendChild(cell);
    });
    head.appendChild(headerRow);
    tableNode.appendChild(head);

    var body = element("tbody");
    rows.forEach(function (item) {
      var row = element("tr");
      rowValues(item).forEach(function (value) {
        row.appendChild(element("td", "", value));
      });
      body.appendChild(row);
    });
    tableNode.appendChild(body);
    wrapper.appendChild(tableNode);
    return wrapper;
  }

  function count(value) {
    return Number(value).toLocaleString("ja-JP");
  }

  function roi(value) {
    return value == null ? "—" : Number(value).toFixed(1) + "%";
  }

  function section(title, note, content) {
    var block = element("section", "stats-section");
    block.appendChild(element("h2", "", title));
    if (note) block.appendChild(element("p", "stats-note", note));
    block.appendChild(content);
    return block;
  }

  function render() {
    var track = payload.tracks.find(function (item) { return item.code === selectedTrack; });
    var tabs = document.getElementById("statsTrackTabs");
    var content = document.getElementById("statsContent");
    clear(tabs);
    clear(content);

    payload.tracks.forEach(function (item) {
      var button = element(
        "button",
        "tab-btn" + (item.code === selectedTrack ? " active" : ""),
        item.name
      );
      button.type = "button";
      button.setAttribute("aria-pressed", String(item.code === selectedTrack));
      button.addEventListener("click", function () {
        selectedTrack = item.code;
        render();
      });
      tabs.appendChild(button);
    });

    if (!track) {
      content.appendChild(element("p", "stats-empty", "成績データがありません。"));
      return;
    }

    var overview = element("div", "stats-overview");
    [
      ["購入件数", count(track.overall.bets) + "件"],
      ["的中数", count(track.overall.hits) + "件"],
      ["単勝回収率", roi(track.overall.roi_pct)]
    ].forEach(function (stat) {
      var card = element("div", "stats-card");
      card.appendChild(element("span", "stats-card-label", stat[0]));
      card.appendChild(element("strong", "stats-card-value", stat[1]));
      overview.appendChild(card);
    });
    content.appendChild(overview);

    content.appendChild(section(
      "条件別成績",
      "全条件を掲載。購入件数が少ない条件は結果の振れ幅が大きくなります。",
      table(
        ["クラス", "芝/ダ", "距離", "馬場", "件数", "単勝的中率", "単勝回収率", "複勝回収率"],
        track.conditions,
        function (row) {
          return [
            row.class, row.surface, row.distance, row.going, count(row.bets),
            roi(row.win_hit_rate_pct), roi(row.win_roi_pct), roi(row.place_roi_pct)
          ];
        }
      )
    ));

    content.appendChild(section(
      "年別成績",
      "各年の勝率1位馬をすべて購入した場合の成績です。",
      table(
        ["年", "件数", "的中数", "単勝回収率"],
        track.yearly,
        function (row) {
          return [row.year + "年", count(row.bets), count(row.hits), roi(row.roi_pct)];
        }
      )
    ));

    content.appendChild(section(
      "オッズ帯別成績",
      "確定単勝オッズを帯に分けて集計しています。",
      table(
        ["単勝オッズ", "件数", "的中数", "単勝回収率"],
        track.odds_bands,
        function (row) {
          return [row.label, count(row.bets), count(row.hits), roi(row.roi_pct)];
        }
      )
    ));

    content.appendChild(section(
      "期待値帯別成績",
      "期待値0.0〜2.0は0.1刻み、2.0以上はまとめて表示。件数0の帯も掲載しています。",
      table(
        ["期待値", "件数", "的中数", "平均期待値", "単勝回収率"],
        track.ev_bands,
        function (row) {
          return [
            row.label, count(row.bets), count(row.hits),
            row.mean_ev == null ? "—" : Number(row.mean_ev).toFixed(3), roi(row.roi_pct)
          ];
        }
      )
    ));
  }

  fetch("data/raceverse/ai-stats.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.tracks) || !data.tracks.length) {
        throw new Error("Invalid AI performance data");
      }
      payload = data;
      document.getElementById("statsPeriod").textContent = "評価期間: " + data.evaluation_period;
      selectedTrack = data.tracks[0].code;
      render();
    })
    .catch(function (error) {
      document.getElementById("statsContent").textContent =
        "成績データの読み込みに失敗しました。ページを再読み込みしてください。";
      console.error("Failed to load AI performance data:", error);
    });
})();
