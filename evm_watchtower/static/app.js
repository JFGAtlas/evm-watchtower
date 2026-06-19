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

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function connectWallet() {
  if (!window.ethereum) {
    alert("请先安装 MetaMask 或兼容 EVM 钱包。");
    return;
  }
  const provider = new ethers.BrowserProvider(window.ethereum);
  const accounts = await provider.send("eth_requestAccounts", []);
  const address = accounts[0];
  const nonce = await api("/api/auth/nonce", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });
  const signer = await provider.getSigner();
  const signature = await signer.signMessage(nonce.message);
  const verified = await api("/api/auth/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, signature }),
  });
  token = verified.token;
  localStorage.setItem("watchtower_token", token);
  $("wallet").textContent = `已登录 ${short(verified.wallet)}`;
  await refresh();
}

async function loadChains() {
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
}

function selectedChains() {
  return [...document.querySelectorAll("#chains input:checked")].map((input) => input.value);
}

async function saveTelegram() {
  await api("/api/telegram", {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify({
      bot_token: $("botToken").value,
      chat_id: $("chatId").value,
      enabled: true,
    }),
  });
  alert("Telegram 已保存。");
}

async function addMonitor() {
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
  await refresh();
}

async function deleteMonitor(id) {
  await api(`/api/monitors/${id}`, { method: "DELETE", headers: headers() });
  await refresh();
}

async function refresh() {
  if (!token) return;
  const monitors = await api("/api/monitors", { headers: headers() });
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

  const events = await api("/api/events", { headers: headers() });
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
}

$("connect").addEventListener("click", connectWallet);
$("saveTelegram").addEventListener("click", saveTelegram);
$("addMonitor").addEventListener("click", addMonitor);

loadChains();
refresh();
setInterval(refresh, 8000);

