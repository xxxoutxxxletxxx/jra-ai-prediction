/* RACEVERSE prediction page. */

(function () {
  "use strict";

  var data;
  var selectedDate;
  var selectedTrack;
  var paceLabels = ["超ハイ", "ハイ", "ミドル", "スロー", "超スロー"];
  var goingColumns = [
    { key: "good", label: "良", code: 1 },
    { key: "yielding", label: "稍重", code: 2 },
    { key: "soft", label: "重", code: 3 },
    { key: "heavy", label: "不良", code: 4 }
  ];

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function percent(value) {
    var number = Number(value);
    return isFinite(number) ? (number * 100).toFixed(1) + "%" : "未取得";
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function renderDates() {
    var container = document.getElementById("rvDateTabs");
    clear(container);
    data.dates.forEach(function (dateEntry) {
      var button = element("button", "tab-btn" + (dateEntry.date === selectedDate ? " active" : ""), dateEntry.label);
      button.type = "button";
      button.addEventListener("click", function () {
        selectedDate = dateEntry.date;
        selectedTrack = null;
        render();
      });
      container.appendChild(button);
    });
  }

  function renderTracks(dateEntry) {
    var container = document.getElementById("rvTrackTabs");
    clear(container);
    dateEntry.tracks.forEach(function (track) {
      var button = element("button", "tab-btn" + (track.code === selectedTrack ? " active" : ""), track.name);
      button.type = "button";
      button.addEventListener("click", function () {
        selectedTrack = track.code;
        render();
      });
      container.appendChild(button);
    });
  }

  function addHorseRow(list, horse, rank) {
    var row = element("li", "rv-horse");
    var marks = ["◎", "○", "▲"];
    row.appendChild(element("span", "rv-mark", marks[rank - 1] || String(rank)));
    row.appendChild(element("span", "rv-number", String(horse.umaban)));
    row.appendChild(element("span", "rv-horse-name", horse.name));
    row.appendChild(element("span", "rv-probability", percent(horse.win_probability)));
    list.appendChild(row);
  }

  function renderRace(track, race) {
    var card = element("article", "rv-race-card");
    var heading = element("div", "rv-race-heading");
    heading.appendChild(element("span", "", track.name + " " + race.race_num + "R" +
      (race.race_name ? " " + race.race_name : "")));
    var conditions = race.distance_m ? race.distance_m + "m " + race.surface : "";
    heading.appendChild(element("span", "rv-race-conditions", conditions));
    card.appendChild(heading);

    if (race.going_scenarios) {
      var favoriteNumbers = goingColumns.map(function (column) {
        return race.going_scenarios[column.key].top_umaban;
      });
      var forecast = new Set(favoriteNumbers).size > 1;
      card.appendChild(element(
        "p", "rv-going-status",
        race.published_going
          ? "公表馬場状態: " + (race.going_label || goingColumns.find(function (column) {
              return column.code === race.published_going;
            }).label)
          : "公表馬場状態: 未発表（4条件を独立表示）"
      ));
      if (race.missing_ability_count > 0) {
        card.appendChild(element(
          "p", "rv-data-warning",
          "Ranker能力値未取得: " + race.missing_ability_count + "頭（能力は中立補完）"
        ));
      }
      if (forecast) {
        card.appendChild(element("p", "rv-favorite-change", "馬場状態によって本命馬が変わります。"));
      }
      var wrapper = element("div", "rv-going-table-wrap");
      var table = element("table", "rv-going-table");
      var head = element("thead");
      var headerRow = element("tr");
      ["馬番", "馬名"].concat(goingColumns.map(function (column) { return column.label; })).forEach(function (label, index) {
        var header = element("th", index > 1 && race.published_going === goingColumns[index - 2].code
          ? "rv-going-published" : "", label);
        header.scope = "col";
        headerRow.appendChild(header);
      });
      head.appendChild(headerRow);
      table.appendChild(head);
      var body = element("tbody");
      race.horses.forEach(function (horse) {
        var row = element("tr");
        row.appendChild(element("th", "rv-number", String(horse.umaban)));
        row.lastChild.scope = "row";
        row.appendChild(element("td", "rv-horse-name", horse.name));
        goingColumns.forEach(function (column) {
          var cell = element("td", "rv-going-probability");
          if (race.going_scenarios[column.key].top_umaban === horse.umaban) {
            cell.classList.add("rv-going-top");
          }
          if (race.published_going === column.code) cell.classList.add("rv-going-published");
          cell.textContent = percent(horse.going_probabilities[column.key]);
          row.appendChild(cell);
        });
        body.appendChild(row);
      });
      table.appendChild(body);
      wrapper.appendChild(table);
      card.appendChild(wrapper);
      return card;
    }

    if (race.going_label) {
      heading.appendChild(element("span", "rv-going-status", "実馬場: " + race.going_label));
    }
    var forecastParts = [];
    if (race.pace_label) forecastParts.push("想定ペース: " + race.pace_label);
    if (race.predicted_early_split_mean_sec != null) {
      forecastParts.push("前半" + Math.round(race.early_section_m) + "m " + Number(race.predicted_early_split_mean_sec).toFixed(1) + "秒");
    }
    if (race.expected_winning_time_sec != null) {
      forecastParts.push("決着時計目安 " + Number(race.expected_winning_time_sec).toFixed(1) + "秒");
    }
    card.appendChild(element("p", "rv-race-forecast", forecastParts.join(" ・ ")));

    var top = element("ol", "rv-horses");
    race.horses.slice(0, 3).forEach(function (horse, index) {
      addHorseRow(top, horse, index + 1);
    });
    card.appendChild(top);

    var details = element("details", "rv-all-horses");
    details.appendChild(element("summary", "", "全出走馬の勝率を見る"));
    var all = element("ol", "rv-horses");
    race.horses.forEach(function (horse, index) {
      addHorseRow(all, horse, index + 1);
    });
    details.appendChild(all);
    card.appendChild(details);
    return card;
  }

  function render() {
    var dateEntry = data.dates.find(function (entry) { return entry.date === selectedDate; });
    if (!dateEntry) return;
    if (!selectedTrack || !dateEntry.tracks.some(function (track) { return track.code === selectedTrack; })) {
      selectedTrack = dateEntry.tracks.length ? dateEntry.tracks[0].code : null;
    }
    renderDates();
    renderTracks(dateEntry);

    var list = document.getElementById("rvRaceList");
    clear(list);
    var track = dateEntry.tracks.find(function (entry) { return entry.code === selectedTrack; });
    if (!track) {
      list.appendChild(element("p", "rv-notice", "この日の予測データはありません。"));
      return;
    }
    track.races.forEach(function (race) {
      list.appendChild(renderRace(track, race));
    });
  }

  function showError(error) {
    var notice = document.getElementById("rvNotice");
    clear(notice);
    notice.appendChild(element("p", "", "RACEVERSE予測の読み込みに失敗しました。ページを再読み込みしてください。"));
    console.error("Failed to load RACEVERSE predictions:", error);
  }

  fetch("data/raceverse/latest.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (payload) {
      data = payload;
      if (data.engine !== "RACEVERSE" || !Array.isArray(data.dates) || !data.dates.length) {
        throw new Error("Invalid RACEVERSE site data");
      }
      document.getElementById("rvUpdatedAt").textContent = "最終更新: " + data.generated_at;
      document.getElementById("rvModelDate").textContent = "モデル基準日: " + data.model_as_of +
        (data.training_data_through ? " / 確定結果: " + data.training_data_through : "");
      var notice = document.getElementById("rvNotice");
      clear(notice);
      notice.appendChild(element(
        "p", "",
        "対象レース " + data.predicted_race_count + " / " + data.scheduled_race_count +
          "（能力スコア不足などで " + data.not_predicted_race_count + " レースは対象外）"
      ));
      notice.appendChild(element(
        "p", "",
        "各レース " + Number(data.simulations_per_race).toLocaleString("ja-JP") +
          " 回シミュレーション。勝率は推定値であり、的中や利益を保証しません。"
      ));
      selectedDate = data.dates[0].date;
      render();
    })
    .catch(showError);
})();
