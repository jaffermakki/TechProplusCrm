(function () {
  const input = document.getElementById("global-search");
  if (!input) return;

  let resultsBox = null;
  let debounceTimer = null;

  function closeResults() {
    if (resultsBox) {
      resultsBox.remove();
      resultsBox = null;
    }
  }

  function renderResults(items) {
    closeResults();
    if (!items.length) return;

    resultsBox = document.createElement("div");
    resultsBox.style.position = "absolute";
    resultsBox.style.top = "calc(100% + 6px)";
    resultsBox.style.left = "0";
    resultsBox.style.right = "0";
    resultsBox.style.background = "#fff";
    resultsBox.style.border = "1px solid var(--border)";
    resultsBox.style.borderRadius = "12px";
    resultsBox.style.boxShadow = "var(--shadow)";
    resultsBox.style.zIndex = "200";
    resultsBox.style.maxHeight = "320px";
    resultsBox.style.overflowY = "auto";

    items.forEach((item) => {
      const row = document.createElement("a");
      row.href = item.url;
      row.style.display = "flex";
      row.style.justifyContent = "space-between";
      row.style.padding = "10px 14px";
      row.style.fontSize = "13.5px";
      row.style.color = "var(--ink)";
      row.style.borderBottom = "1px solid var(--border)";
      row.innerHTML = `<span>${item.label}</span><span style="color:var(--ink-faint);font-size:11.5px;text-transform:uppercase">${item.type}</span>`;
      resultsBox.appendChild(row);
    });

    input.parentElement.style.position = "relative";
    input.parentElement.appendChild(resultsBox);
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) {
      closeResults();
      return;
    }
    debounceTimer = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(q)}`)
        .then((r) => r.json())
        .then(renderResults)
        .catch(() => closeResults());
    }, 200);
  });

  document.addEventListener("click", (e) => {
    if (resultsBox && !input.parentElement.contains(e.target)) {
      closeResults();
    }
  });
})();
