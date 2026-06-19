let token = localStorage.getItem("watchtower_token") || "";
let chains = [];

function $(id) {
  return document.getElementById(id);
}

function headers() {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

function short(address) {
  return address ? `${address.slice(0, 6)}...${address.slice(-4)}` : "";
}

function setStatus(message, type = "") {
  $("status").textContent = message;
  $("status").className = `status ${type}`.trim();
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = await response.text();
    try {
      message = JSON.parse(message).detail || message;
    } catch {
      // Keep raw text.
    }
    throw new Error(message);
  }
  return response.json();
}

async function connectWallet() {
  $("connect").disabled = true;
  try {
    if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
      setStatus("当前页面不是安全上下文，部分钱包不会注入。请使用 HTTPS 地址打开。", "error");
      return;
    }
    if (!window.ethers) {
      setStatus("ethers.js 没有加载成功，请刷新页面或检查浏览器网络。", "error");
      return;
    }
    if (!window.ethereum) {
      setStatus("没有检测到 EVM 钱包。请用 MetaMask/OKX/Rabby 钱包浏览器打开，或安装浏览器插件。", "error");
      return;
    }
    setStatus("正在请求钱包授权...");
    const provider = new ethers.BrowserProvider(window.ethereum);
    const accounts = await provider.send("eth_requestAccounts", []);
    const address = accounts[0];
    setStatus("正在生成登录签名...");
    const nonce = await api("/api/auth/nonce", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    });
    const signer = await provider.getSigner();
    const signature = await signer.signMessage(nonce.message);
    setStatus("正在验证签名...");
    const verified = await api("/api/auth/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address, signature }),
    });
    token = verified.token;
    localStorage.setItem("watchtower_token", token);
    $("wallet").textContent = `已登录 ${short(verified.wallet)}`;
    setStatus("钱包登录成功。", "ok");
    await refresh();
  } catch (error) {
    setStatus(`登录失败：${error.message || error}`, "error");
  } finally {
    $("connect").disabled = false;
  }
}

async function loadChains() {
  try {
    chains = await api("/api/chains");
    $("chains").innerHTML = chains
      .map(
        (chain) => `
        <label class="chain">
          <input type="checkbox" value="${chain.key}" checked />
          ${chain.name}
        </label>`
      )
      .join("");
  } catch (error) {
    setStatus(`链配置加载失败：${error.message || error}`, "error");
  }
}

function selectedChains() {
  return [...document.querySelectorAll("#chains input:checked")].map((input) => input.value);
}

async function saveTelegram() {
  if (!token) {
    setStatus("请先连接钱包登录，再保存 Telegram。", "error");
    return;
  }
  try {
    await api("/api/telegram", {
      method: "PUT",
      headers: headers(),
      body: JSON.stringify({
        bot_token: $("botToken").value,
        chat_id: $("chatId").value,
        enabled: true,
      }),
    });
    setStatus("Telegram 已保存。", "ok");
  } catch (error) {
    setStatus(`Telegram 保存失败：${error.message || error}`, "error");
  }
}

async function addMonitor() {
  if (!token) {
    setStatus("请先连接钱包登录，再添加监控地址。", "error");
    return;
  }
  try {
    await api("/api/monitors", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        address: $("address").value,
        label: $("label").value,
        chains: selectedChains(),
      }),
    });
    $("address").value = "";
    $("label").value = "";
    setStatus("监控地址已添加。", "ok");
    await refresh();
  } catch (error) {
    setStatus(`添加失败：${error.message || error}`, "error");
  }
}

async function deleteMonitor(id) {
  try {
    await api(`/api/monitors/${id}`, { method: "DELETE", headers: headers() });
    setStatus("监控地址已删除。", "ok");
    await refresh();
  } catch (error) {
    setStatus(`删除失败：${error.message || error}`, "error");
  }
}

async function refresh() {
  if (!token) return;
  let monitors = [];
  let events = [];
  try {
    monitors = await api("/api/monitors", { headers: headers() });
    events = await api("/api/events", { headers: headers() });
  } catch (error) {
    setStatus(`刷新失败：${error.message || error}`, "error");
    return;
  }
  $("monitors").innerHTML = monitors.length
    ? monitors
        .map(
          (monitor) => `
        <div class="item">
          <div class="row">
            <div>
              <b>${monitor.label || short(monitor.address)}</b>
              <p>${monitor.address}</p>
              <p>${monitor.chains.map((chain) => `<span class="tag">${chain}</span>`).join("")}</p>
            </div>
            <button class="danger" onclick="deleteMonitor(${monitor.id})">删除</button>
          </div>
        </div>`
        )
        .join("")
    : `<div class="item">暂无监控地址。</div>`;
  $("monitorCount").textContent = String(monitors.length);

  $("events").innerHTML = events.length
    ? events
        .map(
          (event) => `
        <div class="item">
          <p><span class="tag">${event.chain_key}</span><span class="tag">${event.action}</span>${event.summary}</p>
          <p><a href="${event.details.explorer}" target="_blank" rel="noreferrer">${short(event.tx_hash)}</a></p>
        </div>`
        )
        .join("")
    : `<div class="item">还没有捕获到链上活动。</div>`;
  $("eventCount").textContent = String(events.length);
}

$("connect").addEventListener("click", connectWallet);
$("saveTelegram").addEventListener("click", saveTelegram);
$("addMonitor").addEventListener("click", addMonitor);

loadChains();
refresh();
setInterval(refresh, 8000);
if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
  setStatus("当前是 HTTP 页面，钱包可能不注入。建议使用 HTTPS 入口。", "error");
}
