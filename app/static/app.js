const $ = (s) => document.querySelector(s);
const drop = $("#drop"), input = $("#file-input"), list = $("#list"),
      convertBtn = $("#convert"), statusEl = $("#status");
const ACCEPT = /\.(jpe?g|png|webp|bmp|tiff?)$/i;

let items = [];   // { file, url }
let dragIdx = null;

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

function addFiles(files) {
  const skipped = [];
  for (const f of files) {
    if (ACCEPT.test(f.name)) items.push({ file: f, url: URL.createObjectURL(f) });
    else skipped.push(f.name);
  }
  setStatus(skipped.length ? `Skipped unsupported: ${skipped.join(", ")}` : "", skipped.length > 0);
  render();
}

function removeAt(i) {
  URL.revokeObjectURL(items[i].url);
  items.splice(i, 1);
  render();
}

function render() {
  list.innerHTML = "";
  items.forEach((it, i) => {
    const li = document.createElement("li");
    li.className = "item";
    li.draggable = true;
    li.innerHTML = `<img class="thumb" alt=""><span class="num">${i + 1}</span>
      <button class="rm" type="button" title="Remove">×</button><div class="name"></div>`;
    li.querySelector(".thumb").src = it.url;   // TIFF may not preview; conversion still works
    li.querySelector(".name").textContent = it.file.name;
    li.querySelector(".name").title = it.file.name;
    li.querySelector(".rm").onclick = () => removeAt(i);

    li.addEventListener("dragstart", () => { dragIdx = i; li.classList.add("dragging"); });
    li.addEventListener("dragend", () => li.classList.remove("dragging"));
    li.addEventListener("dragover", (e) => e.preventDefault());
    li.addEventListener("drop", (e) => {
      e.preventDefault();
      if (dragIdx === null || dragIdx === i) return;
      items.splice(i, 0, items.splice(dragIdx, 1)[0]);
      dragIdx = null;
      render();
    });
    list.appendChild(li);
  });
  const n = items.length;
  $("#toolbar").hidden = $("#hint").hidden = n === 0;
  $("#count").textContent = `${n} image${n === 1 ? "" : "s"}`;
  convertBtn.disabled = n === 0;
}

// Add files: click / drag onto the dropzone
input.onchange = () => { addFiles(input.files); input.value = ""; };
["dragenter", "dragover"].forEach((ev) =>
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) =>
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

$("#sort").onclick = () => {
  items.sort((a, b) => a.file.name.localeCompare(b.file.name, undefined, { numeric: true }));
  render();
};
$("#clear").onclick = () => { items.forEach((it) => URL.revokeObjectURL(it.url)); items = []; setStatus(""); render(); };

convertBtn.onclick = async () => {
  const fd = new FormData();
  items.forEach((it) => fd.append("files", it.file));
  fd.append("mode", document.querySelector("input[name=mode]:checked").value);
  fd.append("page", document.querySelector("input[name=page]:checked").value);

  convertBtn.disabled = true;
  setStatus("Converting…");
  try {
    const res = await fetch("/api/convert", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === "string" ? err.detail : `Server error (${res.status})`);
    }
    const blob = await res.blob();
    const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "images.pdf";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(`Done — downloaded ${name} (${(blob.size / 1048576).toFixed(1)} MB)`);
  } catch (e) {
    setStatus(e.message, true);
  } finally {
    convertBtn.disabled = items.length === 0;
  }
};
