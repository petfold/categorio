// Category-name completion for inputs marked data-complete="URL".
// With data-multi, completes the last comma-separated name only.
document.querySelectorAll("input[data-complete]").forEach((input, i) => {
  const list = document.createElement("datalist");
  list.id = "complete-" + i;
  input.after(list);
  input.setAttribute("list", list.id);
  input.autocomplete = "off";
  const multi = input.hasAttribute("data-multi");
  let timer;

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const parts = input.value.split(",");
    const last = parts[parts.length - 1].trim();
    if (last.length < 2) { list.replaceChildren(); return; }
    timer = setTimeout(async () => {
      const res = await fetch(input.dataset.complete + "?q=" + encodeURIComponent(last));
      if (!res.ok) return;
      const { names } = await res.json();
      const head = multi ? parts.slice(0, -1).map(s => s.trim()).filter(Boolean) : [];
      list.replaceChildren(...names.map(n => {
        const option = document.createElement("option");
        option.value = head.concat(n).join(", ");
        return option;
      }));
    }, 150);
  });
});
