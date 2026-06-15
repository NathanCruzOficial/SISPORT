/* ───────────────────────────────────────────────────────────────
   Dashboard - Lógica de gráficos, modal e impressão
   ─────────────────────────────────────────────────────────────── */

(function () {
  "use strict";

  // ─────────────────────────────────────────────────────────────
  // 1. Constantes visuais
  // ─────────────────────────────────────────────────────────────
  const COLORS = {
    olive: "#556B2F",
    oliveDark: "#3F5222",
    green: "#198754",
    blue: "#0d6efd",
    yellow: "#ffc107",
    gray: "#6c757d"
  };

  const WEEKDAY_NAMES = [
    "Segunda",
    "Terça",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sábado",
    "Domingo"
  ];

  const CATEGORY_LABEL_MAP = {
    "civil": "Civil",
    "militar": "Militar",
    "ex-militar": "Ex-Militar"
  };

  // ─────────────────────────────────────────────────────────────
  // 2. Carrega dados injetados pelo Jinja
  // ─────────────────────────────────────────────────────────────
  const dataElement = document.getElementById("dashboardData");

  if (!dataElement) {
    console.error("Dashboard: dados não encontrados.");
    return;
  }

  const DATA = JSON.parse(dataElement.textContent);

  // ─────────────────────────────────────────────────────────────
  // 3. Configurações globais do Chart.js
  // ─────────────────────────────────────────────────────────────
  Chart.defaults.font.family = "Arial, Helvetica, sans-serif";
  Chart.defaults.color = "#333";

  // ─────────────────────────────────────────────────────────────
  // 4. Plugin: mostra valores acima das colunas/pontos
  // ─────────────────────────────────────────────────────────────
  const chartValueLabelPlugin = {
  id: "chartValueLabelPlugin",

  afterDatasetsDraw(chart) {
    const { ctx } = chart;

    // Se o gráfico pediu para não mostrar rótulos, ignora
    const pluginOptions = chart.options.plugins.chartValueLabelPlugin || {};
    if (pluginOptions.enabled === false) {
      return;
    }

    ctx.save();

    chart.data.datasets.forEach(function (dataset, datasetIndex) {
      const meta = chart.getDatasetMeta(datasetIndex);
      if (meta.hidden) return;

      // ── Doughnut / Pie: rótulos externos ─────────────────────
      if (chart.config.type === "doughnut" || chart.config.type === "pie") {
        const centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
        const centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;

        meta.data.forEach(function (arc, index) {
          const value = dataset.data[index];
          if (!value) return;

          const angle = (arc.startAngle + arc.endAngle) / 2;
          const outerRadius = arc.outerRadius + 18;

          const x = centerX + Math.cos(angle) * outerRadius;
          const y = centerY + Math.sin(angle) * outerRadius;

          ctx.font = "bold 11px Arial";
          ctx.fillStyle = "#333";
          ctx.textAlign = x > centerX ? "left" : "right";
          ctx.textBaseline = "middle";

          // Linha do arco até o rótulo
          const lineStartX = centerX + Math.cos(angle) * (arc.outerRadius + 2);
          const lineStartY = centerY + Math.sin(angle) * (arc.outerRadius + 2);

          ctx.beginPath();
          ctx.moveTo(lineStartX, lineStartY);
          ctx.lineTo(x - (x > centerX ? 4 : -4), y);
          ctx.strokeStyle = "rgba(0,0,0,.4)";
          ctx.lineWidth = 1;
          ctx.stroke();

          ctx.fillText(value, x, y);
        });

        return;
      }

      // ── Bar / Line: rótulos comuns ───────────────────────────
      meta.data.forEach(function (element, index) {
        const value = dataset.data[index];
        if (value === null || value === undefined || Number(value) === 0) return;

        ctx.font = "bold 11px Arial";
        ctx.fillStyle = "#333";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";

        const position = element.tooltipPosition();

        if (chart.config.type === "bar" && chart.options.indexAxis === "y") {
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          ctx.fillText(value, position.x + 8, position.y);
          return;
        }

        ctx.fillText(value, position.x, position.y - 6);
      });
    });

    ctx.restore();
  }
};

Chart.register(chartValueLabelPlugin);


  // ─────────────────────────────────────────────────────────────
  // 5. Utilitários
  // ─────────────────────────────────────────────────────────────
  function normalizeText(value) {
    return String(value || "").trim().toUpperCase();
  }

  function getCategoryLabel(category) {
    return CATEGORY_LABEL_MAP[category] || category || "Não informado";
  }

  function parseLocalDateTime(value) {
    if (!value) return null;
    return new Date(value);
  }

  // ─────────────────────────────────────────────────────────────
  // 6. Modal de detalhes
  // ─────────────────────────────────────────────────────────────
    // Guarda dados do último detalhamento exibido (para impressão do anexo)
    let lastDetailContext = {
    title: "",
    subtitle: "",
    contextText: "",
    rows: []
    };

  function openDashboardDetails(title, subtitle, contextText, rows) {
  const modalTitle = document.getElementById("dashboardDetailModalLabel");
  const modalSubtitle = document.getElementById("dashboardDetailModalSubtitle");
  const modalContext = document.getElementById("dashboardDetailModalContext");
  const tableBody = document.getElementById("dashboardDetailTableBody");
  const emptyBox = document.getElementById("dashboardDetailEmpty");

  modalTitle.textContent = title;
  modalSubtitle.textContent = subtitle;
  modalContext.innerHTML = contextText
    ? '<i class="bi bi-info-circle me-1"></i>' + contextText
    : "";

  tableBody.innerHTML = "";

  if (!rows || rows.length === 0) {
    emptyBox.classList.remove("d-none");
  } else {
    emptyBox.classList.add("d-none");

    rows.forEach(function (row) {
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td class="fw-semibold">${row.id}</td>
        <td>${row.visitor_name}</td>
        <td>${getCategoryLabel(row.category)}</td>
        <td>${row.destination}</td>
        <td>${row.check_in}</td>
        <td>${row.check_out}</td>
        <td>${row.duration}</td>
      `;

      tableBody.appendChild(tr);
    });
  }

  // Guarda contexto para o botão "Imprimir anexo"
  lastDetailContext = {
    title: title,
    subtitle: subtitle,
    contextText: contextText,
    rows: rows || []
  };

  const modalElement = document.getElementById("dashboardDetailModal");
  const modal = new bootstrap.Modal(modalElement);
  modal.show();
}

  // ─────────────────────────────────────────────────────────────
  // 7. Filtros de detalhamento
  // ─────────────────────────────────────────────────────────────
  function buildPeriodSuffix() {
  if (DATA.selectedMonth && DATA.selectedMonth !== 0) {
    return " no mês de " + DATA.selectedMonthName + "/" + DATA.selectedYear;
  }
  return " no ano de " + DATA.selectedYear;
}

function detailsByMonth(monthNumber, monthName) {
  const rows = DATA.visitDetails.filter(function (item) {
    return Number(item.month) === Number(monthNumber);
  });

  openDashboardDetails(
    "Visitas em " + monthName,
    rows.length + " visita(s) encontrada(s).",
    "Visitantes do mês de " + monthName + "/" + DATA.selectedYear,
    rows
  );
}

function detailsByDay(dayNumber) {
  const rows = DATA.visitDetails.filter(function (item) {
    if (!item.check_in_iso) return false;
    const d = new Date(item.check_in_iso);
    return d.getDate() === Number(dayNumber)
        && (d.getMonth() + 1) === Number(DATA.selectedMonth);
  });

  const dayLabel = String(dayNumber).padStart(2, "0")
    + "/" + String(DATA.selectedMonth).padStart(2, "0")
    + "/" + DATA.selectedYear;

  openDashboardDetails(
    "Visitas em " + dayLabel,
    rows.length + " visita(s) encontrada(s) no dia.",
    "Visitantes do dia " + dayLabel,
    rows
  );
}

function detailsByWeekday(weekdayIndex, weekdayName) {
  const rows = DATA.visitDetails.filter(function (item) {
    return Number(item.weekday) === Number(weekdayIndex);
  });

  openDashboardDetails(
    "Visitas em " + weekdayName,
    rows.length + " visita(s) encontrada(s) neste dia da semana.",
    "Visitantes de " + weekdayName + buildPeriodSuffix(),
    rows
  );
}

function detailsByDestination(destination) {
  const normalizedDestination = normalizeText(destination);

  const rows = DATA.visitDetails.filter(function (item) {
    return normalizeText(item.destination) === normalizedDestination;
  });

  openDashboardDetails(
    "Visitas ao destino " + destination,
    rows.length + " visita(s) encontrada(s) para este destino.",
    "Visitantes que foram para " + destination + buildPeriodSuffix(),
    rows
  );
}

function detailsByCategory(categoryLabel) {
  const normalizedLabel = normalizeText(categoryLabel);

  const rows = DATA.visitDetails.filter(function (item) {
    const itemLabel = normalizeText(getCategoryLabel(item.category));
    return itemLabel === normalizedLabel;
  });

  openDashboardDetails(
    "Visitas da categoria " + categoryLabel,
    rows.length + " visita(s) encontrada(s) nesta categoria.",
    "Visitantes da categoria " + categoryLabel + buildPeriodSuffix(),
    rows
  );
}

function detailsByPresenceHour(hourLabel) {
  const hour = Number(String(hourLabel).split(":")[0]);

  const rows = DATA.visitDetails.filter(function (item) {
    const checkIn = parseLocalDateTime(item.check_in_iso);
    const checkOut = parseLocalDateTime(item.check_out_iso) || new Date();

    if (!checkIn || checkOut <= checkIn) return false;

    const slotStart = new Date(checkIn);
    slotStart.setHours(hour, 0, 0, 0);

    const slotEnd = new Date(checkIn);
    slotEnd.setHours(hour, 59, 59, 999);

    return checkIn <= slotEnd && checkOut >= slotStart;
  });

  const hourEnd = String(hour).padStart(2, "0") + ":59";

  openDashboardDetails(
    "Pessoas presentes entre " + hourLabel + " e " + hourEnd,
    rows.length + " visita(s) relacionada(s) a esta faixa horária.",
    "Visitantes presentes entre " + hourLabel + " e " + hourEnd + buildPeriodSuffix(),
    rows
  );
}

  // ─────────────────────────────────────────────────────────────
  // 8. Gráficos
  // ─────────────────────────────────────────────────────────────

  // 8.1 Visitas por mês (filtro anual) ou por dia (mês específico)
if (DATA.selectedMonth === 0) {
  // ── Gráfico de visitas por mês ─────────────────────────────
  const ctxMonth = document.getElementById("chartVisitsByMonth");

  if (ctxMonth) {
    new Chart(ctxMonth, {
      type: "bar",
      data: {
        labels: DATA.visitsByMonthLabels,
        datasets: [{
          label: "Visitas",
          data: DATA.visitsByMonthValues,
          backgroundColor: COLORS.olive,
          borderRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,

        onClick: function (event, elements) {
          if (!elements.length) return;
          const index = elements[0].index;
          detailsByMonth(index + 1, DATA.visitsByMonthLabels[index]);
        },

        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (context) {
                return " " + context.parsed.y + " visita(s)";
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 }
          }
        },
        layout: { padding: { top: 20 } }
      }
    });
  }
} else {
  // ── Gráfico de visitas por dia (ondas) ─────────────────────
  const ctxDay = document.getElementById("chartVisitsByDay");

  if (ctxDay) {
    new Chart(ctxDay, {
      type: "line",
      data: {
        labels: DATA.visitsByDayLabels,
        datasets: [{
          label: "Visitas",
          data: DATA.visitsByDayValues,
          borderColor: COLORS.olive,
          backgroundColor: "rgba(85, 107, 47, .22)",
          borderWidth: 3,
          tension: .45,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 7,
          pointBackgroundColor: "#fff",
          pointBorderColor: COLORS.olive,
          pointBorderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,

        onClick: function (event, elements) {
          if (!elements.length) return;
          const index = elements[0].index;
          const dayNumber = Number(DATA.visitsByDayLabels[index]);
          detailsByDay(dayNumber);
        },

        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (context) {
                return " " + context.parsed.y + " visita(s) no dia " + context.label;
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: "Dia do mês"
            }
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0 }
          }
        },
        layout: { padding: { top: 20 } }
      }
    });
  }
}


  // 8.2 Visitas por dia da semana
  new Chart(document.getElementById("chartVisitsByWeekday"), {
    type: "bar",
    data: {
      labels: DATA.visitsByWeekdayLabels,
      datasets: [{
        label: "Visitas",
        data: DATA.visitsByWeekdayValues,
        backgroundColor: COLORS.olive,
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,

      onClick: function (event, elements) {
        if (!elements.length) return;

        const index = elements[0].index;
        detailsByWeekday(index, DATA.visitsByWeekdayLabels[index]);
      },

      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0 }
        }
      },
      layout: {
        padding: { top: 20 }
      }
    }
  });

  // 8.3 Destinos / Unidades
  new Chart(document.getElementById("chartTopDestinations"), {
    type: "bar",
    data: {
      labels: DATA.topDestinationLabels,
      datasets: [{
        label: "Visitas",
        data: DATA.topDestinationValues,
        backgroundColor: COLORS.oliveDark,
        borderRadius: 8
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,

      onClick: function (event, elements) {
        if (!elements.length) return;

        const index = elements[0].index;
        detailsByDestination(DATA.topDestinationLabels[index]);
      },

      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { precision: 0 }
        }
      },
      layout: {
        padding: { right: 30 }
      }
    }
  });

// 8.4 Categorias (rosca com rótulos externos)
new Chart(document.getElementById("chartCategories"), {
  type: "doughnut",
  data: {
    labels: DATA.categoryLabels,
    datasets: [{
      data: DATA.categoryValues,
      backgroundColor: [
        COLORS.blue,
        COLORS.olive,
        COLORS.yellow,
        COLORS.gray
      ],
      borderWidth: 2,
      borderColor: "#fff"
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "60%",

    layout: {
      padding: { top: 20, bottom: 20, left: 30, right: 30 }
    },

    onClick: function (event, elements) {
      if (!elements.length) return;
      const index = elements[0].index;
      detailsByCategory(DATA.categoryLabels[index]);
    },

    plugins: {
      legend: { position: "bottom" },
      tooltip: {
        callbacks: {
          label: function (context) {
            return " " + context.label + ": " + context.parsed;
          }
        }
      }
    }
  }
});


// 8.5 Média de pessoas presentes por horário (6am a 18pm, sem números)
const fullPresenceLabels = DATA.presenceByHourLabels;
const fullPresenceValues = DATA.presenceByHourValues;

const filteredPresenceLabels = [];
const filteredPresenceValues = [];
const originalHourMap = []; // Para mapear o índice filtrado → horário original

// Função para formatar "06:00" → "6am" / "13:00" → "1pm"
function formatHourLabel(label) {
  const hour = Number(String(label).split(":")[0]);

  if (hour === 0)  return "12am";
  if (hour === 12) return "12pm";
  if (hour < 12)   return hour + "am";
  return (hour - 12) + "pm";
}

fullPresenceLabels.forEach(function (label, idx) {
  const hour = Number(String(label).split(":")[0]);

  if (hour >= 6 && hour <= 18) {
    filteredPresenceLabels.push(formatHourLabel(label));
    filteredPresenceValues.push(fullPresenceValues[idx]);
    originalHourMap.push(label); // Guarda o original ("06:00") para o detalhamento
  }
});


new Chart(document.getElementById("chartPresenceByHour"), {
  type: "line",
  data: {
    labels: filteredPresenceLabels,
    datasets: [{
      label: "Média de pessoas presentes",
      data: filteredPresenceValues,
      borderColor: COLORS.green,
      backgroundColor: "rgba(25, 135, 84, .22)",
      borderWidth: 3,
      tension: .45,
      fill: true,
      pointRadius: 3,
      pointHoverRadius: 7,
      pointBackgroundColor: "#fff",
      pointBorderColor: COLORS.green,
      pointBorderWidth: 2
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,

    onClick: function (event, elements) {
      if (!elements.length) return;
      const index = elements[0].index;
      detailsByPresenceHour(filteredPresenceLabels[index]);
    },

    plugins: {
      // Desliga o plugin de números para este gráfico
      chartValueLabelPlugin: { enabled: false },

      legend: { display: false },
      tooltip: {
        callbacks: {
            title: function (context) {
            return "Horário: " + context[0].label;
            },
            label: function (context) {
            return " Média: " + context.parsed.y + " pessoa(s)";
            }
        }
      }
    },
    scales: {
      x: {
        ticks: {
          autoSkip: false,
          maxRotation: 0,
          minRotation: 0
        },
        title: {
          display: true,
          text: "Horário"
        }
      },
      y: {
        beginAtZero: true,
        ticks: { precision: 0 },
        title: {
          display: true,
          text: "Média de pessoas"
        }
      }
    },
    layout: { padding: { top: 10 } }
  }
});


  // ─────────────────────────────────────────────────────────────
  // 9. Impressão via iframe oculto
  // ─────────────────────────────────────────────────────────────
  const btnPrint = document.getElementById("btnPrintDashboard");

  if (btnPrint) {
    btnPrint.addEventListener("click", function () {
      const iframe = document.getElementById("dashboardPrintFrame");

      if (!iframe) {
        alert("Não foi possível preparar a impressão do Dashboard.");
        return;
      }

      const printUrl = btnPrint.dataset.printUrl;
      const separator = printUrl.includes("?") ? "&" : "?";

      iframe.onload = function () {
        setTimeout(function () {
          try {
            iframe.contentWindow.focus();
            iframe.contentWindow.print();
          } catch (error) {
            console.error("Erro ao imprimir Dashboard:", error);
            alert("Não foi possível iniciar a impressão do Dashboard.");
          }
        }, 700);
      };

      iframe.src = printUrl + separator + "_print_ts=" + new Date().getTime();
    });
  }

// ─────────────────────────────────────────────────────────────
// 10. Impressão do anexo (modal de detalhamento)
// ─────────────────────────────────────────────────────────────
function buildDetailPrintHtml() {
  const ctx = lastDetailContext;

  const rowsHtml = ctx.rows.map(function (row) {
    return `
      <tr>
        <td>${row.id}</td>
        <td>${row.visitor_name}</td>
        <td>${getCategoryLabel(row.category)}</td>
        <td>${row.destination}</td>
        <td>${row.check_in}</td>
        <td>${row.check_out}</td>
        <td>${row.duration}</td>
      </tr>
    `;
  }).join("");

  const emptyHtml = ctx.rows.length === 0
    ? '<div style="text-align:center;padding:30px;color:#666;">Nenhuma visita encontrada.</div>'
    : "";

  return `<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Anexo - ${ctx.title}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: Arial, Helvetica, sans-serif;
      margin: 24px;
      color: #222;
    }
    .header {
      border-bottom: 2px solid #556B2F;
      padding-bottom: 10px;
      margin-bottom: 16px;
    }
    .header h1 {
      margin: 0 0 4px;
      font-size: 18px;
      color: #3F5222;
    }
    .header .subtitle {
      color: #555;
      font-size: 13px;
    }
    .header .context {
      margin-top: 4px;
      font-size: 13px;
      color: #333;
      font-weight: bold;
    }
    .meta {
      font-size: 12px;
      color: #666;
      margin-bottom: 12px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      border: 1px solid #ccc;
      padding: 6px 8px;
      text-align: left;
    }
    thead th {
      background: #f1f3f5;
    }
    tfoot td {
      font-weight: bold;
      background: #fafafa;
    }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      background: #556B2F;
      color: #fff;
      border-radius: 10px;
      font-size: 11px;
    }
    @page {
      size: A4;
      margin: 15mm;
    }
  </style>
</head>
<body>

  <div class="header">
    <h1>Anexo do Dashboard - ${ctx.title}</h1>
    <div class="subtitle">${ctx.subtitle}</div>
    <div class="context">${ctx.contextText || ""}</div>
  </div>

  <div class="meta">
    Total: <span class="badge">${ctx.rows.length} visita(s)</span>
    &nbsp;·&nbsp; Gerado em ${new Date().toLocaleString("pt-BR")}
  </div>

  <table>
    <thead>
      <tr>
        <th style="width:50px;">ID</th>
        <th>Visitante</th>
        <th style="width:90px;">Categoria</th>
        <th>Destino</th>
        <th style="width:120px;">Entrada</th>
        <th style="width:120px;">Saída</th>
        <th style="width:90px;">Permanência</th>
      </tr>
    </thead>
    <tbody>
      ${rowsHtml}
    </tbody>
  </table>

  ${emptyHtml}

</body>
</html>`;
}

const btnPrintDetail = document.getElementById("btnPrintDashboardDetail");

if (btnPrintDetail) {
  btnPrintDetail.addEventListener("click", function () {
    if (!lastDetailContext || !lastDetailContext.title) {
      alert("Abra um detalhamento antes de imprimir.");
      return;
    }

    // Cria iframe oculto exclusivo para o anexo
    let iframe = document.getElementById("dashboardDetailPrintFrame");

    if (!iframe) {
      iframe = document.createElement("iframe");
      iframe.id = "dashboardDetailPrintFrame";
      iframe.className = "dashboard-detail-print";
      iframe.title = "Impressão do Anexo";
      document.body.appendChild(iframe);
    }

    const html = buildDetailPrintHtml();

    const doc = iframe.contentDocument || iframe.contentWindow.document;
    doc.open();
    doc.write(html);
    doc.close();

    setTimeout(function () {
      try {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
      } catch (error) {
        console.error("Erro ao imprimir anexo:", error);
        alert("Não foi possível iniciar a impressão do anexo.");
      }
    }, 400);
  });
}

})();
