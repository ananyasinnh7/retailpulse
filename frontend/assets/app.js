async function load() {
  const [dashboard, recommendations] = await Promise.all([
    fetch('/api/dashboard').then(r => r.json()),
    fetch('/api/recommendations').then(r => r.json())
  ]);
  document.querySelector('#revenue').textContent = '$' + dashboard.revenue.toLocaleString();
  document.querySelector('#profit').textContent = '$' + dashboard.profit.toLocaleString();
  document.querySelector('#margin').textContent = dashboard.margin + '%';
  document.querySelector('#units').textContent = dashboard.units.toLocaleString();
  new Chart(document.querySelector('#revenueChart'), {type:'line', data:{labels:dashboard.daily.map(x=>x.date.slice(5)), datasets:[{data:dashboard.daily.map(x=>x.revenue), borderColor:'#319b68', backgroundColor:'rgba(49,155,104,.12)', fill:true, tension:.35, pointRadius:0}]}, options:{plugins:{legend:{display:false}}, scales:{y:{grid:{color:'#edf1ee'},ticks:{callback:v=>'$'+v}},x:{grid:{display:false}}}}});
  const colors=['#55b980','#83b4a0','#d9ad54','#b6d7c4'];
  new Chart(document.querySelector('#categoryChart'), {type:'doughnut', data:{labels:dashboard.categories.map(x=>x.name), datasets:[{data:dashboard.categories.map(x=>x.revenue), backgroundColor:colors, borderWidth:0}]}, options:{cutout:'70%', plugins:{legend:{display:false}}}});
  document.querySelector('#categoryLegend').innerHTML=dashboard.categories.map(x=>`<span>${x.name} <b>$${x.revenue.toLocaleString()}</b></span>`).join('');
  document.querySelector('#recommendations').innerHTML=recommendations.map(x=>`<tr><td>${x.product}</td><td>${x.category}</td><td>${x.stock}</td><td>${x.forecast_7d} units</td><td><b>${x.order} units</b></td><td><span class="badge ${x.priority}">${x.priority}</span></td></tr>`).join('');
}
load().catch(() => document.querySelector('#recommendations').innerHTML='<tr><td colspan="6">Could not load analytics data.</td></tr>');
