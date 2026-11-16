const state = {
  token: localStorage.getItem('retailpulse_token'),
  register: true,
  charts: {},
};

const $ = selector => document.querySelector(selector);
const money = value => '$' + Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Request failed');
  return body;
};

function showNotice(message, error = false) {
  const notice = $('#notice');
  notice.textContent = message;
  notice.className = `notice ${error ? 'error' : 'success'}`;
  window.clearTimeout(showNotice.timer);
  showNotice.timer = window.setTimeout(() => { notice.textContent = ''; }, 3500);
}

function setBusy(button, busy, label) {
  if (!button) return;
  button.disabled = busy;
  button.dataset.originalLabel ||= button.textContent;
  button.textContent = busy ? label : button.dataset.originalLabel;
}

function setView(view) {
  document.querySelectorAll('.view, #overview').forEach(element => element.classList.add('hidden'));
  $(`#${view}`).classList.remove('hidden');
  document.querySelectorAll('nav a').forEach(link => link.classList.toggle('active', link.dataset.view === view));
  if (view === 'inventory') loadProducts();
  if (view === 'forecast') loadForecast();
  if (view === 'customers') loadCustomers();
  if (view === 'promotions') loadPromotionHistory();
}

function renderChart(key, canvas, config) {
  if (state.charts[key]) state.charts[key].destroy();
  state.charts[key] = new Chart(canvas, config);
}

async function loadDashboard() {
  const [dashboard, recommendations, alerts] = await Promise.all([
    api('/api/dashboard'), api('/api/recommendations'), api('/api/alerts'),
  ]);
  $('#revenue').textContent = money(dashboard.revenue);
  $('#profit').textContent = money(dashboard.profit);
  $('#margin').textContent = `${dashboard.margin}%`;
  $('#units').textContent = Number(dashboard.units).toLocaleString();

  renderChart('revenue', $('#revenueChart'), {
    type: 'line',
    data: { labels: dashboard.daily.map(item => item.date.slice(5)), datasets: [{ data: dashboard.daily.map(item => item.revenue), borderColor: '#198555', backgroundColor: 'rgba(25,133,85,.12)', fill: true, tension: .38, pointRadius: 0, pointHoverRadius: 5 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: '#edf2ee' }, ticks: { callback: value => money(value) } }, x: { grid: { display: false } } } },
  });
  renderChart('category', $('#categoryChart'), {
    type: 'doughnut',
    data: { labels: dashboard.categories.map(item => item.name), datasets: [{ data: dashboard.categories.map(item => item.revenue), backgroundColor: ['#55b980', '#83b4a0', '#d9ad54', '#b6d7c4'], borderWidth: 0 }] },
    options: { responsive: true, cutout: '72%', plugins: { legend: { display: false } } },
  });
  $('#categoryLegend').innerHTML = dashboard.categories.map(item => `<span>${item.name}<b>${money(item.revenue)}</b></span>`).join('');
  $('#recommendations').innerHTML = recommendations.map(item => `<tr><td>${item.product}</td><td>${item.category}</td><td>${item.stock}</td><td>${item.forecast_7d} units</td><td><b>${item.order} units</b></td><td><span class="badge ${item.priority}">${item.priority}</span></td></tr>`).join('');
  $('#alertCount').textContent = `${alerts.length} open`;
  $('#alertsList').innerHTML = alerts.length ? alerts.map(item => `<div class="alert-row"><span class="alert-icon ${item.severity}">!</span><div><b>${item.title}</b><small>${item.detail}</small></div><span class="badge ${item.severity === 'high' ? 'high' : 'medium'}">${item.severity}</span></div>`).join('') : '<p class="muted">No operational alerts. Your store is running smoothly.</p>';
}

async function loadProducts() {
  const products = await api('/api/products');
  $('#products').innerHTML = products.map(product => `<tr><td><b>${product.name}</b></td><td>${product.category}</td><td>${money(product.price)}</td><td>${money(product.cost)}</td><td>${product.stock}</td><td>${product.reorder_level}</td><td><span class="badge ${product.stock <= product.reorder_level ? 'high' : 'healthy'}">${product.stock <= product.reorder_level ? 'Reorder' : 'Healthy'}</span><button class="row-delete" data-product="${product.id}">Delete</button></td></tr>`).join('');
  document.querySelectorAll('.row-delete').forEach(button => {
    button.onclick = async () => {
      if (!confirm('Delete this product?')) return;
      try { await api(`/api/products/${button.dataset.product}`, { method: 'DELETE' }); showNotice('Product deleted'); await loadProducts(); } catch (error) { showNotice(error.message, true); }
    };
  });
}

async function loadForecast() {
  const forecast = await api('/api/forecast');
  $('#forecasts').innerHTML = forecast.slice(0, 35).map(item => `<tr><td>${item.date}</td><td>${item.product}</td><td><b>${item.units}</b></td></tr>`).join('');
}

async function loadCustomers() {
  const customers = await api('/api/customers/segments');
  $('#customersTable').innerHTML = customers.map(item => `<tr><td><b>${item.name}</b><small class="table-sub">${item.email}</small></td><td><span class="badge ${item.segment === 'At risk' ? 'high' : 'healthy'}">${item.segment}</span></td><td>${item.recency_days} days ago</td><td>${item.frequency}</td><td><b>${money(item.monetary)}</b></td></tr>`).join('');
}

async function updateSimulation() {
  const revenue = Number($('#simRevenue').value) || 0;
  const discount = Number($('#simDiscount').value);
  const lift = Number($('#simLift').value);
  $('#discountValue').textContent = `${discount}%`;
  $('#liftValue').textContent = `${lift}%`;
  try {
    const result = await api('/api/promotions/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ weekly_revenue: revenue, discount_percent: discount, expected_volume_lift_percent: lift }) });
    $('#projectedRevenue').textContent = money(result.projected_revenue);
  } catch (error) { showNotice(error.message, true); }
}

async function loadPromotionHistory() {
  const rows = await api('/api/promotions/history');
  $('#promotionHistory').innerHTML = rows.length ? rows.map(item => `<div class="history-row"><span>${item.discount_percent}% off · ${item.expected_volume_lift_percent}% lift</span><b>${money(item.projected_revenue)}</b></div>`).join('') : '<p class="muted">No simulations yet.</p>';
}

async function loadApp() {
  const user = await api('/api/auth/me');
  $('#auth').classList.add('hidden');
  $('#userName').textContent = user.name;
  $('#greeting').textContent = user.name.split(' ')[0];
  $('#userAvatar').textContent = user.name.split(' ').map(part => part[0]).join('').slice(0, 2).toUpperCase();
  await loadDashboard();
}

function closeProductModal() {
  $('#productModal').classList.add('hidden');
  $('#productForm').reset();
  $('#productError').textContent = '';
}

$('#todayLabel').textContent = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).format(new Date()).toUpperCase();
$('#authToggle').onclick = () => {
  state.register = !state.register;
  $('#authName').parentElement.classList.toggle('hidden', !state.register);
  $('#authSubmit').textContent = state.register ? 'Create account' : 'Sign in';
  $('#authToggle').textContent = state.register ? 'Already have an account? Sign in' : 'New here? Create an account';
};
$('#authForm').onsubmit = async event => {
  event.preventDefault();
  $('#authError').textContent = '';
  const button = $('#authSubmit');
  setBusy(button, true, state.register ? 'Creating account…' : 'Signing in…');
  try {
    const payload = { email: $('#authEmail').value.trim(), password: $('#authPassword').value };
    if (state.register) payload.name = $('#authName').value.trim();
    const result = await api(state.register ? '/api/auth/register' : '/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    state.token = result.token;
    localStorage.setItem('retailpulse_token', state.token);
    await loadApp();
  } catch (error) { $('#authError').textContent = error.message; } finally { setBusy(button, false); }
};
$('#logout').onclick = () => { localStorage.removeItem('retailpulse_token'); location.reload(); };
$('#newProduct').onclick = () => $('#productModal').classList.remove('hidden');
$('#closeProduct').onclick = closeProductModal;
$('#cancelProduct').onclick = closeProductModal;
$('#productForm').onsubmit = async event => {
  event.preventDefault();
  $('#productError').textContent = '';
  const payload = { name: $('#productName').value.trim(), category: $('#productCategory').value.trim(), price: Number($('#productPrice').value), cost: Number($('#productCost').value), stock: Number($('#productStock').value), reorder_level: Number($('#productReorder').value) };
  try { await api('/api/products', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); closeProductModal(); showNotice('Product added successfully'); await loadProducts(); } catch (error) { $('#productError').textContent = error.message; }
};
document.querySelectorAll('[data-view]').forEach(element => element.onclick = () => setView(element.dataset.view));
$('#addData').onclick = () => {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = '.csv';
  input.onchange = async () => {
    if (!input.files[0]) return;
    const form = new FormData(); form.append('file', input.files[0]);
    try { const result = await api('/api/import/sales', { method: 'POST', body: form }); showNotice(`${result.imported} sales imported successfully`); await loadDashboard(); } catch (error) { showNotice(error.message, true); }
  };
  input.click();
};
$('#exportSales').onclick = async () => {
  try {
    const response = await fetch('/api/reports/sales.csv', { headers: { Authorization: `Bearer ${state.token}` } });
    if (!response.ok) throw new Error('Could not export sales report');
    const blob = await response.blob(); const link = document.createElement('a');
    link.href = URL.createObjectURL(blob); link.download = 'retailpulse-sales.csv'; link.click(); URL.revokeObjectURL(link.href); showNotice('Sales report downloaded');
  } catch (error) { showNotice(error.message, true); }
};
$('#simDiscount').oninput = updateSimulation;
$('#simLift').oninput = updateSimulation;
$('#simRevenue').oninput = updateSimulation;
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !$('#productModal').classList.contains('hidden')) closeProductModal(); });

if (state.token) loadApp().catch(() => { localStorage.removeItem('retailpulse_token'); $('#auth').classList.remove('hidden'); });
else $('#auth').classList.remove('hidden');
